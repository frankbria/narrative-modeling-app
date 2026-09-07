"""
Test configuration for API tests
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.auth.nextauth_auth import get_current_user_id


@pytest.fixture
def mock_app():
    """Create a mock FastAPI app for testing without database"""
    app = FastAPI()
    
    # Mock auth dependency
    async def fake_get_current_user_id() -> str:
        return "test_user_123"
    
    app.dependency_overrides[get_current_user_id] = fake_get_current_user_id
    
    # Import and include routes after overriding dependencies
    from app.api.routes import health, secure_upload
    
    app.include_router(
        secure_upload.router,
        prefix="/api/v1/upload",
        tags=["secure_upload"],
    )
    app.include_router(
        health.router,
        prefix="/api/v1/health",
        tags=["health"],
    )
    
    return app


@pytest_asyncio.fixture
async def mock_async_client(mock_app) -> AsyncClient:
    """Create async test client with mocked app"""
    transport = ASGITransport(app=mock_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_user_data():
    """Mock UserData model"""
    with patch('app.api.routes.secure_upload.UserData') as mock:
        instance = AsyncMock()
        instance.insert = AsyncMock()
        instance.id = "507f1f77bcf86cd799439011"  # Mock ObjectId
        mock.return_value = instance
        yield mock


@pytest.fixture
def mock_s3_upload():
    """Mock S3 upload function"""
    with patch('app.api.routes.secure_upload.upload_file_to_s3') as mock:
        # upload_file_to_s3 returns Tuple[bool, Optional[str]]
        mock.return_value = (True, "s3://test-bucket/test-file.csv")
        yield mock


@pytest.fixture
def mock_schema_inference():
    """Mock schema inference"""
    with patch('app.api.routes.secure_upload.infer_schema') as mock:
        mock.return_value = [
            {"name": "column1", "type": "string"},
            {"name": "column2", "type": "integer"}
        ]
        yield mock


@pytest.fixture
def mock_ai_summary():
    """Mock AI summary generation"""
    with patch('app.api.routes.secure_upload.generate_ai_summary_safe') as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_upload_handler():
    """Patch the module-level upload handler.

    Only ``cleanup_expired_sessions`` is stubbed. This used to carry a full set
    of chunked-flow stubs, which is what let the old route tests assert 200
    against a handler and a model that were both patched out. Those tests now
    run the real handler in tests/test_api/test_chunked_upload_flow.py, and the
    stubs left behind had already drifted off the real signatures — dead, and
    misleading to the next caller who reached for them.
    """
    with patch('app.api.routes.secure_upload.upload_handler') as mock:
        yield mock
