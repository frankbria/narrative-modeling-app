import pytest
from jose import jwt
import base64
import json
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.auth.nextauth_auth import get_current_user_id

# Sample test data
SAMPLE_USER_ID = "user_123"
SAMPLE_TOKEN = "Bearer nextauth-user_123"
SAMPLE_JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsImVtYWlsIjoidGVzdEB0ZXN0LmNvbSIsImlhdCI6MTYwOTQ1OTIwMCwiZXhwIjoxNjA5NTQ1NjAwfQ.signature"


@pytest.fixture
def mock_env_vars():
    """Fixture to set up mock environment variables."""
    with patch.dict("os.environ", {"NEXTAUTH_SECRET": "test-secret", "SKIP_AUTH": "false"}, clear=False):
        # Also patch the module-level variables
        with patch("app.auth.nextauth_auth.NEXTAUTH_SECRET", "test-secret"):
            with patch("app.auth.nextauth_auth.SKIP_AUTH", False):
                yield


@pytest.fixture
def mock_mongodb_client():
    """Fixture to create a mock MongoDB client."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_collection
    return mock_client


@pytest.mark.asyncio
async def test_get_current_user_id_nextauth_token(mock_env_vars):
    """Test user ID extraction from NextAuth-style token."""
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="nextauth-user_123"
    )
    
    user_id = await get_current_user_id(credentials)
    assert user_id == "user_123"


@pytest.mark.asyncio
async def test_get_current_user_id_jwt_token(mock_env_vars):
    """Test user ID extraction from JWT token."""
    # Mock the jwt.decode function
    with patch("jose.jwt.decode", return_value={"sub": SAMPLE_USER_ID, "email": "test@test.com"}):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=SAMPLE_JWT_TOKEN
        )
        
        user_id = await get_current_user_id(credentials)
        assert user_id == SAMPLE_USER_ID


@pytest.mark.asyncio
async def test_get_current_user_id_mongodb_fallback(mock_env_vars, mock_mongodb_client):
    """Test user ID extraction from MongoDB when JWT fails."""
    # Mock jwt.decode to fail
    with patch("jose.jwt.decode", side_effect=jwt.JWTError()):
        # Mock MongoDB to return a session
        mock_collection = mock_mongodb_client["auth"]["sessions"]
        mock_collection.find_one.return_value = {
            "sessionToken": "invalid-token",
            "userId": SAMPLE_USER_ID,
            "expires": "2024-12-31T23:59:59.999Z"
        }
        
        with patch("app.auth.nextauth.mongodb_client", mock_mongodb_client):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="invalid-token"
            )
            
            user_id = await get_current_user_id(credentials)
            assert user_id == SAMPLE_USER_ID


@pytest.mark.asyncio
async def test_get_current_user_id_missing_env_vars():
    """Test user ID extraction with missing environment variables."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("app.auth.nextauth_auth.NEXTAUTH_SECRET", None):
            with patch("app.auth.nextauth_auth.SKIP_AUTH", False):
                credentials = HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials=SAMPLE_TOKEN
                )

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_id(credentials)

                assert exc_info.value.status_code == 500
                assert "Authentication service is not properly configured" in str(
                    exc_info.value.detail
                )


@pytest.mark.asyncio
async def test_get_current_user_id_invalid_format(mock_env_vars):
    """Test user ID extraction with invalid token format."""
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="invalid-format"
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(credentials)

    assert exc_info.value.status_code == 401
    assert "Invalid authentication token" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_id_invalid_jwt(mock_env_vars, mock_mongodb_client):
    """Test user ID extraction with invalid JWT and no MongoDB session."""
    # Mock jwt.decode to fail
    with patch("jose.jwt.decode", side_effect=jwt.JWTError()):
        # Mock MongoDB to return no session
        mock_collection = mock_mongodb_client["auth"]["sessions"]
        mock_collection.find_one.return_value = None
        
        with patch("app.auth.nextauth.mongodb_client", mock_mongodb_client):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="invalid.jwt.token"
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(credentials)

            assert exc_info.value.status_code == 401
            assert "Invalid authentication token" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_id_expired_token(mock_env_vars):
    """Test user ID extraction with expired token."""
    # Mock the jwt.decode function to raise an expired token error
    with patch("jose.jwt.decode", side_effect=jwt.ExpiredSignatureError()):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=SAMPLE_JWT_TOKEN
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(credentials)

        assert exc_info.value.status_code == 401
        assert "Token has expired" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_id_missing_user_id(mock_env_vars):
    """Test user ID extraction with token missing user ID."""
    # Mock the jwt.decode function to return a payload without 'sub'
    with patch("jose.jwt.decode", return_value={"email": "test@test.com"}):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=SAMPLE_JWT_TOKEN
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(credentials)

        assert exc_info.value.status_code == 401
        assert "No user ID found in token" in str(exc_info.value.detail)
