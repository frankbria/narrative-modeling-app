import pytest
import jwt
import base64
import json
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.auth.clerk_auth import get_unverified_header, get_current_user_id

# Sample test data
SAMPLE_USER_ID = "user_123"
SAMPLE_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InRlc3Rfa2lkIn0.eyJzdWIiOiJ1c2VyXzEyMyIsImlzcyI6Imh0dHBzOi8vdGVzdC5jbGVyay5jb20iLCJhdWQiOiJodHRwczovL3Rlc3QuY2xlcmsuY29tIn0.signature"
SAMPLE_JWKS = {
    "keys": [
        {
            "kid": "test_kid",
            "kty": "RSA",
            "n": "test_n",
            "e": "test_e",
            "alg": "RS256",
            "use": "sig",
        }
    ]
}


@pytest.fixture
def mock_env_vars():
    """Fixture to set up mock environment variables."""
    with patch.dict("os.environ", {"CLERK_ISSUER": "https://test.clerk.com"}):
        yield


@pytest.fixture
def mock_httpx_client():
    """Fixture to create a mock httpx client."""
    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    return mock_client


def test_get_unverified_header():
    """Test extracting header from JWT token."""
    # Create a test token with known header
    header = {"alg": "RS256", "typ": "JWT", "kid": "test_kid"}
    header_b64 = (
        base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    )
    token = f"{header_b64}.eyJzdWIiOiJ0ZXN0In0.signature"

    result = get_unverified_header(token)

    assert result == header


def test_get_unverified_header_invalid_token():
    """Test extracting header from invalid JWT token."""
    with pytest.raises(Exception):
        get_unverified_header("invalid.token.format")


@pytest.mark.asyncio
async def test_get_current_user_id_success(mock_env_vars, mock_httpx_client):
    """Test successful user ID extraction from valid token."""
    # Mock the httpx client response
    mock_httpx_client.get.return_value = MagicMock(
        is_success=True, json=lambda: SAMPLE_JWKS
    )

    # Mock the jwt.decode function
    with patch("jose.jwt.decode", return_value={"sub": SAMPLE_USER_ID}):
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=SAMPLE_TOKEN
            )
            user_id = await get_current_user_id(credentials)

            assert user_id == SAMPLE_USER_ID


@pytest.mark.asyncio
async def test_get_current_user_id_missing_env_vars():
    """Test user ID extraction with missing environment variables."""
    with patch.dict("os.environ", {}, clear=True):
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
async def test_get_current_user_id_jwks_fetch_error(mock_env_vars, mock_httpx_client):
    """Test user ID extraction when JWKS fetch fails."""
    # Mock the httpx client to return an error
    mock_httpx_client.get.return_value = MagicMock(
        is_success=False, status_code=404, text="Not Found"
    )

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=SAMPLE_TOKEN
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(credentials)

        assert exc_info.value.status_code == 500
        assert "Failed to fetch JWKS" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_id_invalid_jwks_response(
    mock_env_vars, mock_httpx_client
):
    """Test user ID extraction with invalid JWKS response."""
    # Mock the httpx client to return invalid JSON
    mock_httpx_client.get.return_value = MagicMock(
        is_success=True, json=lambda: "invalid json"
    )

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=SAMPLE_TOKEN
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(credentials)

        assert exc_info.value.status_code == 500
        assert "Invalid JWKS response format" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_id_invalid_token(mock_env_vars, mock_httpx_client):
    """Test user ID extraction with invalid token."""
    # Mock the httpx client response
    mock_httpx_client.get.return_value = MagicMock(
        is_success=True, json=lambda: SAMPLE_JWKS
    )

    # Mock the jwt.decode function to raise an error
    with patch("jose.jwt.decode", side_effect=jwt.InvalidTokenError()):
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="invalid.token"
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(credentials)

            assert exc_info.value.status_code == 401
            assert "Invalid token" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_id_expired_token(mock_env_vars, mock_httpx_client):
    """Test user ID extraction with expired token."""
    # Mock the httpx client response
    mock_httpx_client.get.return_value = MagicMock(
        is_success=True, json=lambda: SAMPLE_JWKS
    )

    # Mock the jwt.decode function to raise an expired token error
    with patch("jose.jwt.decode", side_effect=jwt.ExpiredSignatureError()):
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=SAMPLE_TOKEN
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(credentials)

            assert exc_info.value.status_code == 401
            assert "Token has expired" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_id_missing_user_id(mock_env_vars, mock_httpx_client):
    """Test user ID extraction with token missing user ID."""
    # Mock the httpx client response
    mock_httpx_client.get.return_value = MagicMock(
        is_success=True, json=lambda: SAMPLE_JWKS
    )

    # Mock the jwt.decode function to return a payload without 'sub'
    with patch("jose.jwt.decode", return_value={"other": "claim"}):
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=SAMPLE_TOKEN
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(credentials)

            assert exc_info.value.status_code == 401
            assert "No user ID found in token" in str(exc_info.value.detail)
