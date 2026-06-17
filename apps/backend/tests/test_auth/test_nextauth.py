"""Tests for NextAuth JWT validation (app/auth/nextauth_auth.py).

Tests the current get_current_user_id contract with real HS256-signed tokens:
- Valid JWT -> user id from `sub` (or `id`) claim
- Malformed/wrongly-signed/expired tokens -> 401
- Token without a user id claim -> 401
- Missing NEXTAUTH_SECRET configuration -> 500
- SKIP_AUTH development mode token mapping

Historical note (issue #160): earlier versions of these tests asserted a
`nextauth-<user_id>` prefix scheme and a MongoDB session fallback that no
longer exist in the implementation.
"""

import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.auth.nextauth_auth import get_current_user_id, get_current_user_id_optional

pytestmark = [pytest.mark.unit, pytest.mark.auth]

TEST_SECRET = "test-secret"
SAMPLE_USER_ID = "user_123"


def make_token(payload: dict, secret: str = TEST_SECRET) -> str:
    """Create a real HS256-signed JWT like NextAuth produces."""
    return jwt.encode(payload, secret, algorithm="HS256")


def bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def mock_env_vars():
    """Configure the auth module with a known secret and auth enabled."""
    with patch.dict("os.environ", {"NEXTAUTH_SECRET": TEST_SECRET, "SKIP_AUTH": "false"}, clear=False):
        # Also patch the module-level variables (read at import time)
        with patch("app.auth.nextauth_auth.NEXTAUTH_SECRET", TEST_SECRET):
            with patch("app.auth.nextauth_auth.SKIP_AUTH", False):
                yield


@pytest.mark.asyncio
async def test_valid_jwt_returns_sub_claim(mock_env_vars):
    """A valid signed JWT yields the user id from the `sub` claim."""
    token = make_token({"sub": SAMPLE_USER_ID, "email": "test@test.com"})

    user_id = await get_current_user_id(bearer(token))
    assert user_id == SAMPLE_USER_ID


@pytest.mark.asyncio
async def test_valid_jwt_falls_back_to_id_claim(mock_env_vars):
    """Without `sub`, the `id` claim is used."""
    token = make_token({"id": SAMPLE_USER_ID})

    user_id = await get_current_user_id(bearer(token))
    assert user_id == SAMPLE_USER_ID


@pytest.mark.asyncio
async def test_malformed_token_rejected(mock_env_vars):
    """A token that is not a JWT at all is rejected with 401."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer("not-a-jwt"))

    assert exc_info.value.status_code == 401
    assert "Invalid token" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_wrong_signature_rejected(mock_env_vars):
    """A JWT signed with a different secret is rejected with 401."""
    token = make_token({"sub": SAMPLE_USER_ID}, secret="some-other-secret")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer(token))

    assert exc_info.value.status_code == 401
    assert "Invalid token" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_expired_token_rejected(mock_env_vars):
    """An expired JWT is rejected with 401 and an expiry message."""
    token = make_token({"sub": SAMPLE_USER_ID, "exp": int(time.time()) - 3600})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer(token))

    assert exc_info.value.status_code == 401
    assert "Token has expired" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_missing_user_id_claim_rejected(mock_env_vars):
    """A valid JWT without `sub`/`id` claims is rejected with 401 (not 500)."""
    token = make_token({"email": "test@test.com"})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer(token))

    assert exc_info.value.status_code == 401
    assert "Invalid authentication token" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_missing_secret_is_configuration_error():
    """Without NEXTAUTH_SECRET (and SKIP_AUTH off), auth fails with 500."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("app.auth.nextauth_auth.NEXTAUTH_SECRET", None):
            with patch("app.auth.nextauth_auth.SKIP_AUTH", False):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_id(bearer("anything"))

                assert exc_info.value.status_code == 500
                assert "Authentication service is not properly configured" in str(
                    exc_info.value.detail
                )


class TestSkipAuthDevelopmentMode:
    """SKIP_AUTH=true bypasses JWT validation with deterministic mapping."""

    @pytest.mark.asyncio
    async def test_dev_prefixed_token_returns_itself(self):
        with patch("app.auth.nextauth_auth.SKIP_AUTH", True):
            user_id = await get_current_user_id(bearer("dev-alice"))
            assert user_id == "dev-alice"

    @pytest.mark.asyncio
    async def test_other_tokens_map_to_default_dev_user(self):
        with patch("app.auth.nextauth_auth.SKIP_AUTH", True):
            user_id = await get_current_user_id(bearer("whatever"))
            assert user_id == "dev-user-default"


class TestOptionalAuthentication:
    """get_current_user_id_optional returns None instead of raising."""

    @pytest.mark.asyncio
    async def test_valid_bearer_header_returns_user_id(self, mock_env_vars):
        token = make_token({"sub": SAMPLE_USER_ID})

        user_id = await get_current_user_id_optional(f"Bearer {token}")
        assert user_id == SAMPLE_USER_ID

    @pytest.mark.asyncio
    async def test_missing_header_returns_none(self, mock_env_vars):
        assert await get_current_user_id_optional(None) is None

    @pytest.mark.asyncio
    async def test_non_bearer_header_returns_none(self, mock_env_vars):
        assert await get_current_user_id_optional("Basic abc123") is None

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self, mock_env_vars):
        assert await get_current_user_id_optional("Bearer not-a-jwt") is None
