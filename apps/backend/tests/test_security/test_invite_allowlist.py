"""Invite-only beta gate — allowlist config + backend mirror (issue #261).

The launch is a free, invite-only beta but OAuth signup is open by default. The
primary gate is the NextAuth `signIn` callback (frontend); the backend mirrors
the same INVITE_ALLOWLIST check in ``get_current_user_id`` as defense-in-depth.

Covers the AC directly: a non-allowlisted email is denied and an allowlisted one
is admitted — both at the pure-function layer and through the real JWT path.
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.auth.nextauth_auth import get_current_user_id
from app.config import is_email_allowed, parse_invite_allowlist

pytestmark = [pytest.mark.unit, pytest.mark.security]

TEST_SECRET = "test-secret"


def _bearer(payload: dict) -> HTTPAuthorizationCredentials:
    token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestParseInviteAllowlist:
    def test_unset_or_blank_is_empty(self):
        assert parse_invite_allowlist(None) == set()
        assert parse_invite_allowlist("") == set()
        assert parse_invite_allowlist("   ") == set()

    def test_splits_trims_lowercases_drops_blanks(self):
        assert parse_invite_allowlist(" Alice@Example.com , bob@example.com ,, ") == {
            "alice@example.com",
            "bob@example.com",
        }


class TestIsEmailAllowed:
    LIST = {"alice@example.com", "bob@example.com"}

    def test_admits_listed_email_case_insensitive(self):
        assert is_email_allowed("alice@example.com", self.LIST) is True
        assert is_email_allowed("ALICE@Example.com", self.LIST) is True

    def test_denies_unlisted_email(self):
        assert is_email_allowed("eve@evil.com", self.LIST) is False

    def test_denies_missing_email_when_gate_active(self):
        assert is_email_allowed(None, self.LIST) is False
        assert is_email_allowed("", self.LIST) is False

    def test_empty_allowlist_disables_gate(self):
        assert is_email_allowed("eve@evil.com", set()) is True
        assert is_email_allowed(None, set()) is True


@pytest.fixture
def auth_enabled():
    """Real secret, auth on, SKIP_AUTH off (mirrors test_nextauth.py)."""
    with patch.dict(
        "os.environ", {"NEXTAUTH_SECRET": TEST_SECRET, "SKIP_AUTH": "false"}, clear=False
    ):
        with patch("app.auth.nextauth_auth.NEXTAUTH_SECRET", TEST_SECRET):
            with patch("app.auth.nextauth_auth.SKIP_AUTH", False):
                yield


class TestBackendMirrorEnforcement:
    """get_current_user_id enforces INVITE_ALLOWLIST when configured."""

    @pytest.mark.asyncio
    async def test_allowlisted_email_admitted(self, auth_enabled):
        with patch.dict("os.environ", {"INVITE_ALLOWLIST": "alice@example.com"}):
            uid = await get_current_user_id(
                _bearer({"sub": "user_1", "email": "alice@example.com"})
            )
        assert uid == "user_1"

    @pytest.mark.asyncio
    async def test_non_allowlisted_email_denied_403(self, auth_enabled):
        with patch.dict("os.environ", {"INVITE_ALLOWLIST": "alice@example.com"}):
            with pytest.raises(HTTPException) as exc:
                await get_current_user_id(
                    _bearer({"sub": "user_2", "email": "eve@evil.com"})
                )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_no_email_claim_denied_when_gate_active(self, auth_enabled):
        # A token minted before this PR (no email claim) is rejected while the
        # gate is active. Intentional/fail-closed: the frontend re-mints an
        # email-bearing token on the next session read, so the transition
        # self-heals within the token TTL.
        with patch.dict("os.environ", {"INVITE_ALLOWLIST": "alice@example.com"}):
            with pytest.raises(HTTPException) as exc:
                await get_current_user_id(_bearer({"sub": "user_alice"}))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_gate_off_when_empty_allows_any_email(self, auth_enabled):
        # Empty INVITE_ALLOWLIST → gate disabled → any signed token passes.
        with patch.dict("os.environ", {"INVITE_ALLOWLIST": ""}):
            uid = await get_current_user_id(
                _bearer({"sub": "user_3", "email": "eve@evil.com"})
            )
        assert uid == "user_3"
