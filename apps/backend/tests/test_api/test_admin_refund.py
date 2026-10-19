"""Admin refund-window readout (#746): any tenant's eligibility, behind ADMIN_EMAILS."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.billing.refunds import REFUND_WINDOW_DAYS
from app.main import app
from app.models.subscription import PlanTier, Subscription, SubscriptionStatus
from tests.api_tokens import mint_api_token

ADMIN = "ops@example.com"
_SECRET = "test-secret"


def _url(user_id: str) -> str:
    return f"/api/v1/admin/billing/{user_id}/refund"


def _bearer(email: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_api_token('u1', email, secret=_SECRET)}"}


@pytest.fixture
async def client(setup_database):
    with patch("app.auth.nextauth_auth.NEXTAUTH_SECRET", _SECRET), \
         patch("app.auth.nextauth_auth.SKIP_AUTH", False), \
         patch.dict("os.environ", {"ADMIN_EMAILS": ADMIN}):
        async with LifespanManager(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                yield c


async def _subscribe(user_id: str, first_paid_at: datetime | None) -> None:
    await Subscription(
        user_id=user_id,
        plan_tier=PlanTier.PRO,
        status=SubscriptionStatus.ACTIVE,
        first_paid_at=first_paid_at,
    ).insert()


@pytest.mark.parametrize(
    "headers",
    [{}, _bearer("tenant@example.com"), {"Authorization": "Bearer not-a-jwt"}],
    ids=["anonymous", "non-admin", "forged"],
)
async def test_everyone_but_an_admin_gets_404(client, headers):
    await _subscribe("tenant-1", datetime.now(UTC))
    assert (await client.get(_url("tenant-1"), headers=headers)).status_code == 404


async def test_inside_the_window_is_eligible(client):
    first_paid = datetime.now(UTC) - timedelta(days=REFUND_WINDOW_DAYS - 2)
    await _subscribe("tenant-1", first_paid)

    response = await client.get(_url("tenant-1"), headers=_bearer(ADMIN))

    assert response.status_code == 200
    body = response.json()
    assert body["refund_eligible"] is True
    assert datetime.fromisoformat(body["first_paid_at"]).date() == first_paid.date()
    assert datetime.fromisoformat(body["refund_window_ends_at"]).date() == (
        first_paid + timedelta(days=REFUND_WINDOW_DAYS)
    ).date()


async def test_outside_the_window_is_not_eligible_but_the_window_is_known(client):
    await _subscribe("tenant-1", datetime.now(UTC) - timedelta(days=REFUND_WINDOW_DAYS + 5))

    body = (await client.get(_url("tenant-1"), headers=_bearer(ADMIN))).json()

    assert body["refund_eligible"] is False
    assert body["refund_window_ends_at"] is not None


async def test_subscribed_but_never_paid_has_no_window(client):
    await _subscribe("tenant-1", None)

    body = (await client.get(_url("tenant-1"), headers=_bearer(ADMIN))).json()

    assert body == {
        "refund_eligible": False,
        "refund_window_ends_at": None,
        "first_paid_at": None,
    }


async def test_a_tenant_with_no_subscription_is_a_clear_404(client):
    response = await client.get(_url("nobody"), headers=_bearer(ADMIN))

    assert response.status_code == 404
    assert "no subscription" in response.json()["detail"]
