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
from app.auth.nextauth_auth import get_current_user_id
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager


# Use pytest-asyncio's event_loop fixture instead of defining our own
# This avoids conflicts with pytest-asyncio's internal event loop management
@pytest_asyncio.fixture(scope="function")
async def setup_database():
    """Set up test database before each test and clean up after."""
    # Create a test database client
    client = AsyncIOMotorClient(settings.MONGODB_URI)

    # Initialize Beanie with test database
    await init_beanie(
        database=client[settings.MONGODB_DB + "_test"],
        document_models=[
            UserData,
            ColumnStats,
            VisualizationCache,
            AnalyticsResult,
            Plot,
            TrainedModel,
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


@pytest_asyncio.fixture(autouse=True, scope="session")
async def override_auth_dependency():
    async def fake_get_current_user_id() -> str:
        return "test_user_123"

    app.dependency_overrides[get_current_user_id] = fake_get_current_user_id
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def mock_user_id() -> str:
    """Return a mock user ID for testing."""
    return "test_user_123"


@pytest.fixture
def mock_dataset_id() -> str:
    """Return a mock dataset ID for testing."""
    return "test_dataset_123"
