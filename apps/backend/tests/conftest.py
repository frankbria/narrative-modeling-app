import pytest
import asyncio
import pytest_asyncio
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.main import app
from app.config import settings
from app.models.user_data import UserData
from app.models.column_stats import ColumnStats
from app.models.visualization_cache import VisualizationCache
from app.models.analytics_result import AnalyticsResult
from app.models.plot import Plot
from app.models.trained_model import TrainedModel
from app.models.ab_test import ABTest
from app.models.batch_job import BatchJob
from app.models.ml_model import MLModel
from app.models.revised_data import RevisedData
from app.auth.nextauth_auth import get_current_user_id
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager


# Use pytest-asyncio's event_loop fixture instead of defining our own
# This avoids conflicts with pytest-asyncio's internal event loop management
@pytest_asyncio.fixture(autouse=True, scope="function")
async def setup_database():
    """Set up test database before each test and clean up after."""
    # Create a test database client
    client = AsyncIOMotorClient(settings.TEST_MONGODB_URI)

    # Initialize Beanie with test database
    await init_beanie(
        database=client[settings.TEST_MONGODB_DB],
        document_models=[
            UserData,
            ColumnStats,
            VisualizationCache,
            AnalyticsResult,
            Plot,
            TrainedModel,
            ABTest,
            BatchJob,
            MLModel,
            RevisedData
        ],
    )

    yield

    # Clean up after tests
    try:
        # Use find().delete() instead of delete_all()
        await UserData.find().delete()
        await ColumnStats.find().delete()
        await VisualizationCache.find().delete()
        await AnalyticsResult.find().delete()
        await Plot.find().delete()
        await TrainedModel.find().delete()
    except Exception as e:
        print(f"Error during cleanup: {e}")
    finally:
        client.close()


@pytest_asyncio.fixture
async def async_test_client() -> AsyncGenerator[AsyncClient, None]:
    """Create a test client for the FastAPI application."""
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# Removed session-scoped auth override in favor of explicit authorized_client fixtures
# @pytest_asyncio.fixture(autouse=True, scope="session")
# async def override_auth_dependency():
#     async def fake_get_current_user_id() -> str:
#         return "test_user_123"
#
#     app.dependency_overrides[get_current_user_id] = fake_get_current_user_id
#     yield
#     app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def mock_user_id() -> str:
    """Return a mock user ID for testing."""
    return "test_user_123"


@pytest.fixture
def mock_dataset_id() -> str:
    """Return a mock dataset ID for testing."""
    return "test_dataset_123"


@pytest.fixture
def authorized_client() -> TestClient:
    """Create an authorized test client for the FastAPI application."""
    # Override the auth dependency to return a test user
    async def override_get_current_user_id() -> str:
        return "test_user_123"
    
    # Clear any existing overrides first
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    
    with TestClient(app) as client:
        yield client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_authorized_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async authorized test client for the FastAPI application."""
    # Override the auth dependency to return a test user
    async def override_get_current_user_id() -> str:
        return "test_user_123"
    
    # Clear any existing overrides first
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    
    # Clean up
    app.dependency_overrides.clear()
    
@pytest_asyncio.fixture
async def async_test_client(async_authorized_client) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI application."""
    return async_authorized_client


@pytest.fixture
def mock_user_data():
    """Create a mock UserData object that matches the current model schema"""
    from app.models.user_data import UserData, SchemaField
    from bson import ObjectId
    from datetime import datetime, timezone
    from unittest.mock import MagicMock
    
    # Create a mock object instead of actual Document to avoid DB operations
    mock = MagicMock(spec=UserData)
    # Use a fixed ID for tests
    mock.id = "test-file-123"
    mock._id = "test-file-123"
    mock.user_id = "test_user_123"
    mock.filename = "test_data.csv"
    mock.original_filename = "test_data.csv"
    mock.s3_url = "s3://test-bucket/test-file-123.csv"
    mock.num_rows = 100
    mock.num_columns = 5
    mock.data_schema = [
        SchemaField(
            field_name="id",
            field_type="numeric",
            data_type="interval",
            inferred_dtype="int64",
            unique_values=100,
            missing_values=0,
            example_values=[1, 2, 3, 4, 5],
            is_constant=False,
            is_high_cardinality=True
        ),
        SchemaField(
            field_name="value",
            field_type="numeric",
            data_type="ratio",
            inferred_dtype="float64",
            unique_values=50,
            missing_values=5,
            example_values=[10.5, 20.3, 30.1],
            is_constant=False,
            is_high_cardinality=False
        ),
        SchemaField(
            field_name="category",
            field_type="categorical",
            data_type="nominal",
            inferred_dtype="object",
            unique_values=4,
            missing_values=2,
            example_values=["A", "B", "C"],
            is_constant=False,
            is_high_cardinality=False
        )
    ]
    mock.created_at = datetime.now(timezone.utc)
    mock.updated_at = datetime.now(timezone.utc)
    mock.aiSummary = None
    
    # Add commonly used computed properties
    mock.file_size = 1024
    mock.file_type = "csv"
    mock.is_processed = True
    
    # For backward compatibility, add these as properties
    mock.file_path = mock.s3_url
    mock.upload_date = mock.created_at
    
    # Schema property for tests expecting old format
    mock.schema = {
        "row_count": mock.num_rows,
        "column_count": mock.num_columns,
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "value", "type": "float"},
            {"name": "category", "type": "string"}
        ]
    }
    
    return mock
