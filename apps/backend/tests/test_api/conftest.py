"""
Test configuration for API tests
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData


@pytest.fixture
def mock_app():
    """Create a mock FastAPI app for testing without database"""
    app = FastAPI()
    
    # Mock auth dependency
    async def fake_get_current_user_id() -> str:
        return "test_user_123"
    
    app.dependency_overrides[get_current_user_id] = fake_get_current_user_id
    
    # Import and include routes after overriding dependencies
    from app.api.routes import secure_upload, health
    
    app.include_router(
        secure_upload.router,
        prefix="/api/upload",
        tags=["secure_upload"],
    )
    app.include_router(
        health.router,
        prefix="/api/health",
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
        mock.return_value = "s3://test-bucket/test-file.csv"
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
def mock_monitoring():
    """Mock monitoring service"""
    with patch('app.services.monitoring.monitor') as mock:
        mock.get_health_metrics.return_value = {
            "status": "healthy",
            "api": {"total_requests": 0}
        }
        mock.get_security_summary.return_value = {
            "total_events": 0
        }
        yield mock


@pytest.fixture
def mock_ai_summary():
    """Mock AI summary generation"""
    with patch('app.api.routes.secure_upload.generate_ai_summary_safe') as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_upload_handler():
    """Mock upload handler to avoid file system operations"""
    with patch('app.api.routes.secure_upload.upload_handler') as mock:
        # Mock the upload handler methods
        def mock_init_upload(filename, file_size, file_hash=None):
            # Simulate file size limit check
            if file_size > 100 * 1024 * 1024 * 1024:  # 100GB limit
                from fastapi import HTTPException
                raise HTTPException(status_code=413, detail="File too large")
            return {
                "session_id": "test_session_123",
                "chunk_size": 5242880,
                "total_chunks": 1,
                "expires_at": "2024-01-01T12:00:00"
            }
        mock.init_upload = AsyncMock(side_effect=mock_init_upload)
        mock.upload_chunk = AsyncMock(return_value={
            "chunk_number": 0,
            "status": "uploaded",
            "progress": 100.0,
            "complete": True
        })
        mock.resume_upload = AsyncMock(return_value={
            "session_id": "test_session_123",
            "filename": "test.csv",
            "file_size": 1024,
            "chunk_size": 5242880,
            "total_chunks": 1,
            "uploaded_chunks": 1,
            "missing_chunks": [],
            "progress": 100.0,
            "expires_at": "2024-01-01T12:00:00"
        })
        # Mock file reading by patching open
        import tempfile
        from pathlib import Path
        test_csv_content = b"product_id,price\n1001,19.99"
        
        # Create a real temporary file for the test
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        temp_file.write(test_csv_content)
        temp_file.close()
        
        mock.complete_upload = AsyncMock(return_value=Path(temp_file.name))
        mock._get_session = MagicMock(return_value={
            "filename": "test.csv",
            "file_size": 1024,
            "status": "complete"
        })
        yield mock