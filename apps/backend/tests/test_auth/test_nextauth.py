"""Tests for NextAuth JWT validation (app/auth/nextauth_auth.py).

Tests the current get_current_user_id contract with real HS256-signed tokens:
- The token the frontend mints -> user id from its `sub` claim
- Malformed/wrongly-signed/expired tokens -> 401
- A token without `sub` or without `exp`, or under any algorithm but HS256 -> 401
- Missing NEXTAUTH_SECRET configuration -> 500
- SKIP_AUTH development mode token mapping

Historical note (issue #160): earlier versions of these tests asserted a
`nextauth-<user_id>` prefix scheme and a MongoDB session fallback that no
longer exist in the implementation.
"""

import time
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.nextauth_auth import (
    get_current_user_id,
    get_current_user_id_optional,
    require_admin,
)
from tests.api_tokens import mint_api_token

pytestmark = [pytest.mark.unit, pytest.mark.auth]

TEST_SECRET = "test-secret"
SAMPLE_USER_ID = "user_123"


def make_token(payload: dict, secret: str = TEST_SECRET) -> str:
    """An HS256 token with exactly these claims, for shapes the frontend never mints."""
    return jwt.encode(payload, secret, algorithm="HS256")


def in_an_hour() -> int:
    return int(time.time()) + 3600


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
    """The token the frontend mints yields the user id from its `sub` claim."""
    token = mint_api_token(SAMPLE_USER_ID, "test@test.com")

    user_id = await get_current_user_id(bearer(token))
    assert user_id == SAMPLE_USER_ID


@pytest.mark.asyncio
async def test_an_id_claim_does_not_stand_in_for_sub(mock_env_vars):
    """The frontend always mints `sub` (#844); a token carrying only `id` is refused."""
    token = make_token({"id": SAMPLE_USER_ID, "exp": in_an_hour()})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer(token))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_a_token_without_expiry_is_refused(mock_env_vars):
    """A token with no `exp` would be valid forever if it leaked (#844)."""
    token = make_token({"sub": SAMPLE_USER_ID})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer(token))
    assert exc_info.value.status_code == 401


def _unsigned(email: str | None = None) -> str:
    """An `alg: none` token: the frontend's claims, no signature."""
    token = mint_api_token(SAMPLE_USER_ID, email, header={"alg": "none", "typ": "JWT"})
    return token.rsplit(".", 1)[0] + "."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "forge",
    [
        pytest.param(_unsigned, id="alg-none"),
        # Right secret, wrong header: only HS256 is accepted, whatever signs it.
        pytest.param(lambda: mint_api_token(SAMPLE_USER_ID, header={"alg": "RS256", "typ": "JWT"}), id="rs256-header"),
    ],
)
async def test_only_hs256_is_accepted(mock_env_vars, forge):
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer(forge()))
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid authentication token"


@pytest.mark.asyncio
async def test_require_admin_refuses_an_unsigned_token(mock_env_vars):
    """The admin gate verifies like the user gate: an `alg: none` token naming an
    admin email is the same 404 as no token."""
    with patch.dict("os.environ", {"ADMIN_EMAILS": "ops@example.com"}):
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(bearer(_unsigned("ops@example.com")))
        assert exc_info.value.status_code == 404
        # The real token for that admin is admitted, so the refusal is the signature's.
        assert await require_admin(bearer(mint_api_token(SAMPLE_USER_ID, "ops@example.com"))) is None


@pytest.mark.asyncio
async def test_malformed_token_rejected(mock_env_vars):
    """A token that is not a JWT at all is rejected with 401."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer("not-a-jwt"))

    assert exc_info.value.status_code == 401
    # Fixed message, no JWT-library internals leaked (issue #269).
    assert exc_info.value.detail == "Invalid authentication token"


@pytest.mark.asyncio
async def test_legacy_nextauth_prefix_token_rejected(mock_env_vars):
    """The old placeholder credential `nextauth-<user_id>` is not a JWT and
    must be rejected with 401 under SKIP_AUTH=false (issue #251 AC: it can never
    be used to impersonate a user)."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer("nextauth-other_user"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid authentication token"


@pytest.mark.asyncio
async def test_placeholder_default_token_rejected(mock_env_vars):
    """The frontend preview proxy used to send the literal string "default" as the
    bearer when it had no token (#527 AC3). Under a production-like config
    (SKIP_AUTH=false) that must be a 401, never a user."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer("default"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid authentication token"


@pytest.mark.asyncio
async def test_wrong_signature_rejected(mock_env_vars):
    """A JWT signed with a different secret is rejected with 401."""
    token = mint_api_token(SAMPLE_USER_ID, secret="some-other-secret")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer(token))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid authentication token"


@pytest.mark.asyncio
async def test_unexpected_decode_error_is_401_not_500(mock_env_vars):
    """A non-JWT exception during decode is a fixed 401, not a leaky 500
    (issue #269: auth-as-500 pollutes error-rate metrics and leaks internals)."""
    with patch("app.auth.nextauth_auth.jwt.decode", side_effect=Exception("boom internal")):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(bearer("anything"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid authentication token"
    assert "boom internal" not in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_expired_token_rejected(mock_env_vars):
    """An expired JWT is rejected with 401 and an expiry message."""
    token = mint_api_token(SAMPLE_USER_ID, ttl=-3600)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(bearer(token))

    assert exc_info.value.status_code == 401
    assert "Token has expired" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_missing_user_id_claim_rejected(mock_env_vars):
    """A valid JWT without a `sub` claim is rejected with 401 (not 500)."""
    token = make_token({"email": "test@test.com", "exp": in_an_hour()})

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
    """SKIP_AUTH=true bypasses JWT validation, mapping every request to one
    fixed dev identity (issue #272 — no verbatim dev-identity impersonation)."""

    @pytest.mark.asyncio
    async def test_dev_prefixed_token_no_longer_returns_itself(self):
        # Regression (issue #272): a forged "dev-"-prefixed bearer must NOT be
        # honored verbatim as the user id — it maps to the fixed dev user.
        with patch("app.auth.nextauth_auth.SKIP_AUTH", True):
            user_id = await get_current_user_id(bearer("dev-alice"))
            assert user_id == "dev-user-default"

    @pytest.mark.asyncio
    async def test_other_tokens_map_to_default_dev_user(self):
        with patch("app.auth.nextauth_auth.SKIP_AUTH", True):
            user_id = await get_current_user_id(bearer("whatever"))
            assert user_id == "dev-user-default"


class TestOptionalAuthentication:
    """get_current_user_id_optional returns None instead of raising."""

    @pytest.mark.asyncio
    async def test_valid_bearer_header_returns_user_id(self, mock_env_vars):
        token = mint_api_token(SAMPLE_USER_ID)

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


@pytest.mark.asyncio
async def test_require_admin_turns_any_jwt_error_into_404(mock_env_vars):
    """A key error is not an InvalidTokenError; it must still be the plain 404, not a 500."""
    with patch("app.auth.nextauth_auth.jwt.decode", side_effect=jwt.InvalidKeyError("bad key")):
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(bearer(mint_api_token(SAMPLE_USER_ID, "ops@example.com")))
    assert exc_info.value.status_code == 404
