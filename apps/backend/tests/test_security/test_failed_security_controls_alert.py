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
from app.services.rate_limit import RedisRateLimitStore

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


class _FlakyRedis:
    """eval() fails, fails, answers, fails: two outages with a recovery between."""

    def __init__(self):
        self.calls = 0

    async def eval(self, *args):
        self.calls += 1
        if self.calls == 3:
            return [1, 60]
        raise ConnectionError("redis://:secret@cache:6379 refused")


async def test_a_redis_outage_is_counted_every_time_and_logged_once_per_outage(caplog):
    # The real store catches a Redis error itself, so the middleware never sees an
    # outage: the store is where it has to be counted.
    store = RedisRateLimitStore("redis://unused", key_prefix="test_590:")
    store._client = _FlakyRedis()
    before = _failures("rate_limit_store")

    with caplog.at_level(logging.ERROR, logger="app.services.rate_limit"):
        results = [await store.hit("caller", limit=5, window_seconds=60) for _ in range(4)]

    assert all(r.allowed for r in results)
    assert [r.limited for r in results] == [False, False, True, False]
    assert _failures("rate_limit_store") == before + 3
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 2  # one per outage, the recovery re-arms it
    assert not any("secret" in m for m in errors)
