import pytest
import asyncio
import pytest_asyncio
from typing import AsyncGenerator, Generator, List
from datetime import datetime, timezone

# Lazy imports to avoid app initialization for unit tests
# Only import these when fixtures are actually used


# Use pytest-asyncio's event_loop fixture instead of defining our own
# This avoids conflicts with pytest-asyncio's internal event loop management
@pytest_asyncio.fixture(scope="function")
async def setup_database(request):
    """Set up test database before each test and clean up after.

    Only runs for tests marked with @pytest.mark.integration
    """
    # Skip for unit tests
    if "unit" in request.keywords:
        yield
        return

    # Lazy imports for integration tests
    from motor.motor_asyncio import AsyncIOMotorClient
    from beanie import init_beanie
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
    from app.models.dataset import DatasetMetadata
    from app.models.version import DatasetVersion, TransformationLineage

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
            RevisedData,
            DatasetMetadata,
            DatasetVersion,
            TransformationLineage
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
        await ABTest.find().delete()
        await BatchJob.find().delete()
        await MLModel.find().delete()
        await RevisedData.find().delete()
        await DatasetMetadata.find().delete()
        await DatasetVersion.find().delete()
        await TransformationLineage.find().delete()
    except Exception as e:
        print(f"Error during cleanup: {e}")
    finally:
        client.close()


@pytest_asyncio.fixture
async def mongo_client(setup_database):
    """Provide a MongoDB client for tests."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.config import settings

    client = AsyncIOMotorClient(settings.TEST_MONGODB_URI)
    yield client
    client.close()


@pytest_asyncio.fixture
async def test_user_data(setup_database) -> "UserData":
    """Create and return a test UserData document."""
    from app.models.user_data import UserData, SchemaField

    user_data = UserData(
        user_id="test_user_123",
        filename="integration_test.csv",
        original_filename="integration_test.csv",
        s3_url="s3://test-bucket/integration_test.csv",
        num_rows=100,
        num_columns=3,
        data_schema=[
            SchemaField(
                field_name="id",
                field_type="numeric",
                data_type="interval",
                inferred_dtype="int64",
                unique_values=100,
                missing_values=0,
                example_values=[1, 2, 3],
                is_constant=False,
                is_high_cardinality=True
            ),
            SchemaField(
                field_name="value",
                field_type="numeric",
                data_type="ratio",
                inferred_dtype="float64",
                unique_values=50,
                missing_values=0,
                example_values=[10.5, 20.3, 30.1],
                is_constant=False,
                is_high_cardinality=False
            ),
            SchemaField(
                field_name="category",
                field_type="categorical",
                data_type="nominal",
                inferred_dtype="object",
                unique_values=3,
                missing_values=0,
                example_values=["A", "B", "C"],
                is_constant=False,
                is_high_cardinality=False
            )
        ],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    await user_data.insert()
    yield user_data

    # Cleanup
    try:
        await user_data.delete()
    except Exception:
        pass


@pytest_asyncio.fixture
async def test_trained_model(setup_database, test_user_data) -> "TrainedModel":
    """Create and return a test TrainedModel document."""
    from app.models.trained_model import TrainedModel

    model = TrainedModel(
        userId="test_user_123",
        datasetId=test_user_data.id,  # Use the Link directly
        modelType="classification",
        params={
            "algorithm": "random_forest",
            "target_column": "category",
            "feature_columns": ["id", "value"]
        },
        performance={
            "accuracy": 0.95,
            "precision": 0.94,
            "recall": 0.93,
            "f1_score": 0.935
        },
        modelFileUrl="https://test-bucket.s3.amazonaws.com/models/test_model.pkl"
    )

    await model.insert()
    yield model

    # Cleanup
    try:
        await model.delete()
    except Exception:
        pass


@pytest_asyncio.fixture
async def test_batch_job(setup_database) -> "BatchJob":
    """Create and return a test BatchJob document."""
    from app.models.batch_job import BatchJob, JobType

    job = BatchJob(
        job_id="test_job_123",
        user_id="test_user_123",
        job_type=JobType.MODEL_TRAINING,
        config={"algorithm": "random_forest", "target": "category"}
    )

    await job.insert()
    yield job

    # Cleanup
    try:
        await job.delete()
    except Exception:
        pass


@pytest_asyncio.fixture
async def redis_client(request):
    """Provide a Redis client for tests."""
    # Skip for unit tests
    if "unit" in request.keywords:
        yield None
        return

    # Lazy import
    import redis.asyncio as aioredis
    import os

    # Use test Redis configuration
    redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0")

    try:
        client = await aioredis.from_url(redis_url, decode_responses=True)

        # Test connection
        await client.ping()

        # Clear test database before yielding
        await client.flushdb()

        yield client

        # Cleanup
        await client.flushdb()
        await client.aclose()
    except (ConnectionError, Exception) as e:
        pytest.skip(f"Redis not available: {e}")


@pytest_asyncio.fixture
async def test_redis_job(redis_client):
    """Create a test job in Redis queue."""
    if redis_client is None:
        yield None
        return

    import json
    from datetime import datetime, timezone

    job_data = {
        "job_id": "test_redis_job_123",
        "job_type": "model_training",
        "user_id": "test_user_123",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "algorithm": "random_forest",
            "target": "category"
        }
    }

    # Push job to Redis queue
    job_key = f"job:{job_data['job_id']}"
    await redis_client.set(job_key, json.dumps(job_data))
    await redis_client.lpush("job_queue", job_data["job_id"])

    yield job_data

    # Cleanup
    await redis_client.delete(job_key)


@pytest.fixture
def s3_client(request):
    """Provide an S3 client for tests (LocalStack or real AWS)."""
    # Skip for unit tests
    if "unit" in request.keywords:
        yield None
        return

    import boto3
    import os
    from botocore.exceptions import ClientError, EndpointConnectionError
    from botocore.config import Config

    # Use LocalStack by default for testing
    # Note: LocalStack accepts any credentials - these are local-only placeholders
    endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "test")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    try:
        # Configure with short timeout to fail fast
        config = Config(
            connect_timeout=2,
            read_timeout=2,
            retries={"max_attempts": 1}
        )

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region,
            config=config
        )

        # Test connection
        client.list_buckets()

        yield client
    except (ClientError, EndpointConnectionError, Exception) as e:
        pytest.skip(f"S3/LocalStack not available: {e}")


@pytest.fixture
def test_s3_bucket(s3_client):
    """Create and manage a test S3 bucket."""
    if s3_client is None:
        yield None
        return

    from botocore.exceptions import ClientError

    bucket_name = "test-narrative-bucket"

    # Create bucket
    try:
        s3_client.create_bucket(Bucket=bucket_name)
    except ClientError as e:
        if e.response["Error"]["Code"] != "BucketAlreadyExists":
            raise

    yield bucket_name

    # Cleanup: Delete all objects in bucket, then delete bucket
    try:
        # List and delete all objects
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if "Contents" in response:
            objects = [{"Key": obj["Key"]} for obj in response["Contents"]]
            s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects})

        # Delete bucket
        s3_client.delete_bucket(Bucket=bucket_name)
    except Exception as e:
        print(f"Error cleaning up S3 bucket: {e}")


@pytest.fixture
def test_s3_file(s3_client, test_s3_bucket):
    """Upload a test file to S3 and return its key."""
    if s3_client is None or test_s3_bucket is None:
        yield None
        return

    import io

    # Create test CSV content
    csv_content = """id,value,category
1,10.5,A
2,20.3,B
3,30.1,C
4,15.7,A
5,25.2,B"""

    file_key = "test-data/test_file.csv"

    # Upload file
    s3_client.put_object(
        Bucket=test_s3_bucket,
        Key=file_key,
        Body=csv_content.encode("utf-8"),
        ContentType="text/csv"
    )

    yield {
        "bucket": test_s3_bucket,
        "key": file_key,
        "s3_url": f"s3://{test_s3_bucket}/{file_key}",
        "content": csv_content
    }

    # Cleanup handled by test_s3_bucket fixture


@pytest.fixture
def mock_openai(monkeypatch):
    """Mock OpenAI API responses for testing."""
    from unittest.mock import AsyncMock, MagicMock
    import openai

    # Mock chat completion response
    mock_chat_response = {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a mocked AI response for testing purposes."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }

    # Create async mock for chat completions
    async_mock = AsyncMock(return_value=MagicMock(**mock_chat_response))

    # Patch OpenAI client methods
    mock_client = MagicMock()
    mock_client.chat.completions.create = async_mock

    # Return mocking utilities
    yield {
        "client": mock_client,
        "response": mock_chat_response,
        "async_mock": async_mock
    }


@pytest.fixture
def test_openai_response():
    """Provide canned OpenAI responses for different scenarios."""
    return {
        "data_summary": {
            "content": """
            This dataset contains customer purchase data with the following insights:
            - 100 records with 5 columns
            - Target variable: 'purchased' (binary classification)
            - Key features: age, income, product_category
            - Recommendation: Use Random Forest or Logistic Regression
            """
        },
        "model_advice": {
            "content": """
            Based on your data characteristics:
            1. Problem type: Binary Classification
            2. Recommended algorithms: Random Forest, XGBoost, Logistic Regression
            3. Feature engineering: Consider creating age bins and income brackets
            4. Expected accuracy: 85-90% with proper feature engineering
            """
        },
        "error_diagnosis": {
            "content": """
            The error indicates missing values in the 'age' column.
            Recommendations:
            1. Use median imputation for missing age values
            2. Alternatively, create a 'missing_age' indicator feature
            3. Consider if missing ages are Missing At Random (MAR) or systematic
            """
        }
    }


@pytest_asyncio.fixture
async def async_test_client() -> AsyncGenerator:
    """Create a test client for the FastAPI application."""
    from httpx import AsyncClient, ASGITransport
    from asgi_lifespan import LifespanManager
    from app.main import app

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
def authorized_client():
    """Create an authorized test client for the FastAPI application."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth.nextauth_auth import get_current_user_id

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
async def async_authorized_client() -> AsyncGenerator:
    """Create an async authorized test client for the FastAPI application."""
    from httpx import AsyncClient, ASGITransport
    from asgi_lifespan import LifespanManager
    from app.main import app
    from app.auth.nextauth_auth import get_current_user_id

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
