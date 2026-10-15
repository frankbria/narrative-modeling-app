"""A best-effort security control that fails is an ERROR and a counted event (#590).

Both controls stay best-effort: the Stripe webhook must not fail over a re-clamp,
and a broken limiter store must not 500 a request. But each one failing removes a
control, so it is logged at ERROR (what an alert keys on) with the repair, and
counted in `security_control_failures_total`.
"""

import logging
from unittest.mock import patch

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.billing.api_keys import reconcile_user_api_keys
from app.billing.plans import PlanTier
from app.middleware.metrics import security_control_failures
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.api_key import APIKey

pytestmark = pytest.mark.asyncio


def _failures(control: str) -> float:
    return security_control_failures.labels(control=control)._value.get()


async def test_a_failed_reclamp_is_an_error_naming_the_repair(caplog):
    before = _failures("api_key_reclamp")

    with patch.object(APIKey, "get_motor_collection", side_effect=RuntimeError("database down")):
        with caplog.at_level(logging.ERROR, logger="app.billing.api_keys"):
            assert await reconcile_user_api_keys("reclamp-590", PlanTier.FREE) == 0

    assert _failures("api_key_reclamp") == before + 1
    assert any(
        r.levelno == logging.ERROR and "fix_api_key_rate_limits.py --apply" in r.getMessage() for r in caplog.records
    )


class _BrokenStore:
    async def hit(self, key, limit, window):
        raise ConnectionError("redis went away")


async def test_a_limiter_store_that_raises_fails_open_and_is_counted(caplog):
    before = _failures("rate_limit_store")
    app = Starlette(routes=[Route("/api/v1/ping", lambda request: PlainTextResponse("pong"))])
    app.add_middleware(RateLimitMiddleware, store=_BrokenStore(), enabled=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        with caplog.at_level(logging.ERROR, logger="app.middleware.rate_limit"):
            response = await client.get("/api/v1/ping")

    assert response.status_code == 200
    assert _failures("rate_limit_store") == before + 1
    assert any(r.levelno == logging.ERROR and "failing open" in r.getMessage() for r in caplog.records)
