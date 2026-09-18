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
from app.config import parse_invite_allowlist, resolve_signup_mode, signup_admits

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


class TestResolveSignupMode:
    """SIGNUP_MODE (#768): explicit, and unset fails CLOSED where it matters."""

    def test_explicit_values_win_everywhere(self):
        for prod in (True, False):
            assert resolve_signup_mode("open", set(), prod) == "open"
            assert resolve_signup_mode(" Invite ", set(), prod) == "invite"

    def test_unset_in_production_like_is_invite(self):
        # The fail-open "empty allowlist means everyone" can no longer reach a
        # deployed environment by deleting one variable.
        assert resolve_signup_mode(None, set(), True) == "invite"
        assert resolve_signup_mode("  ", set(), True) == "invite"

    def test_unset_in_dev_keeps_the_legacy_behaviour(self):
        assert resolve_signup_mode(None, set(), False) == "open"
        assert resolve_signup_mode(None, {"a@x.com"}, False) == "invite"

    def test_unknown_value_fails_closed(self):
        assert resolve_signup_mode("opne", set(), False) == "invite"
        assert resolve_signup_mode("opne", set(), True) == "invite"


class TestSignupAdmits:
    LIST = {"alice@example.com", "bob@example.com"}

    def test_invite_admits_listed_email_case_insensitive(self):
        assert signup_admits("alice@example.com", "invite", self.LIST) is True
        assert signup_admits(" ALICE@Example.com", "invite", self.LIST) is True

    def test_invite_denies_unlisted_or_missing_email(self):
        assert signup_admits("eve@evil.com", "invite", self.LIST) is False
        assert signup_admits(None, "invite", self.LIST) is False
        assert signup_admits("", "invite", self.LIST) is False

    def test_invite_with_empty_allowlist_admits_nobody(self):
        # Fails closed, like ADMIN_EMAILS (#477) — not "gate disabled".
        assert signup_admits("eve@evil.com", "invite", set()) is False

    def test_open_admits_anyone(self):
        assert signup_admits("eve@evil.com", "open", set()) is True
        assert signup_admits("eve@evil.com", "open", self.LIST) is True


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
    async def test_dev_with_nothing_set_allows_any_email(self, auth_enabled):
        # Local dev/test: SIGNUP_MODE and the allowlist unset → open (legacy).
        with patch.dict("os.environ", {"INVITE_ALLOWLIST": "", "SIGNUP_MODE": ""}):
            uid = await get_current_user_id(
                _bearer({"sub": "user_3", "email": "eve@evil.com"})
            )
        assert uid == "user_3"

    @pytest.mark.asyncio
    async def test_production_with_nothing_set_denies_403(self, auth_enabled):
        with patch.dict(
            "os.environ",
            {"INVITE_ALLOWLIST": "", "SIGNUP_MODE": "", "ENVIRONMENT": "production"},
        ):
            with pytest.raises(HTTPException) as exc:
                await get_current_user_id(
                    _bearer({"sub": "user_4", "email": "eve@evil.com"})
                )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_open_mode_admits_unlisted_email_even_in_production(self, auth_enabled):
        with patch.dict(
            "os.environ",
            {
                "INVITE_ALLOWLIST": "alice@example.com",
                "SIGNUP_MODE": "open",
                "ENVIRONMENT": "production",
            },
        ):
            uid = await get_current_user_id(
                _bearer({"sub": "user_5", "email": "eve@evil.com"})
            )
        assert uid == "user_5"
