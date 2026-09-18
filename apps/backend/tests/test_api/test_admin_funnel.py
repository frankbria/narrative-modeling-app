"""Admin funnel readout (#769 AC2): behind the ADMIN_EMAILS allowlist, 404 for all else."""

from unittest.mock import patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.main import app
from app.services import product_events

FUNNEL = "/api/v1/admin/funnel"
ADMIN = "ops@example.com"
_SECRET = "test-secret"


def _bearer(email: str | None) -> dict[str, str]:
    claims = {"sub": "u1", **({"email": email} if email else {})}
    return {"Authorization": f"Bearer {jwt.encode(claims, _SECRET, algorithm='HS256')}"}


@pytest.fixture
async def client(setup_database):
    with patch("app.auth.nextauth_auth.NEXTAUTH_SECRET", _SECRET), \
         patch("app.auth.nextauth_auth.SKIP_AUTH", False), \
         patch.dict("os.environ", {"ADMIN_EMAILS": ADMIN}):
        async with LifespanManager(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                yield c


@pytest.mark.parametrize(
    "headers",
    [{}, _bearer("tenant@example.com"), {"Authorization": "Bearer not-a-jwt"}],
    ids=["anonymous", "non-admin", "forged"],
)
async def test_everyone_but_an_admin_gets_404(client, headers):
    assert (await client.get(FUNNEL, headers=headers)).status_code == 404


async def test_the_admin_gets_the_numbers(client):
    await product_events.record("a", product_events.ACCOUNT_CREATED, once="account_created")
    await product_events.record("a", product_events.CHECKOUT_STARTED, tier="pro")

    response = await client.get(FUNNEL, params={"days": 7}, headers=_bearer(ADMIN))

    assert response.status_code == 200
    body = response.json()
    assert body["days"] == 7
    assert body["signups"] == 1
    assert body["checkout_started"] == 1


async def test_the_window_is_bounded(client):
    response = await client.get(FUNNEL, params={"days": 10_000}, headers=_bearer(ADMIN))
    assert response.status_code == 422
