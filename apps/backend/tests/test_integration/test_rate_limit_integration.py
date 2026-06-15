"""
Integration tests for the rate-limit store backed by real Redis, and per-API-key
enforcement backed by real MongoDB (issue #151).

Redis tests use the test instance on :6380 (the ``redis_client`` fixture skips when
absent). The API-key override test uses ``setup_database`` and a real :class:`APIKey`
document.
"""

import os

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.rate_limit import RateLimitMiddleware
from app.models.api_key import APIKey
from app.services.rate_limit import RedisRateLimitStore


@pytest.mark.integration
class TestRedisRateLimitStore:
    @pytest.mark.asyncio
    async def test_redis_store_enforces_and_expires(self, redis_client):
        """A Redis-backed counter blocks over budget and resets after the window."""
        redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0")
        store = RedisRateLimitStore(redis_url, key_prefix="test_rl:")
        try:
            key = "user:redis-enforce"
            r1 = await store.hit(key, limit=2, window_seconds=1)
            r2 = await store.hit(key, limit=2, window_seconds=1)
            r3 = await store.hit(key, limit=2, window_seconds=1)
            assert r1.allowed is True
            assert r2.allowed is True
            assert r3.allowed is False
            assert r3.retry_after >= 1

            # Window expires → budget restored.
            import asyncio

            await asyncio.sleep(1.2)
            r4 = await store.hit(key, limit=2, window_seconds=1)
            assert r4.allowed is True
        finally:
            await store.close()


@pytest.mark.integration
class TestApiKeyRateLimitOverride:
    @pytest.mark.asyncio
    async def test_per_api_key_limit_is_honored(self, setup_database, redis_client):
        """A low per-key ``rate_limit`` blocks sooner than the default budget."""
        raw_key = "sk_live_integration_test_key_001"
        api_key = APIKey(
            key_id="rl-int-key-1",
            key_hash=APIKey.hash_key(raw_key),
            name="rate-limit-int-test",
            user_id="rl-int-user",
            rate_limit=2,  # deliberately tiny
        )
        await api_key.insert()

        redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0")
        store = RedisRateLimitStore(redis_url, key_prefix="test_rl_api:")

        app = FastAPI()
        # default budget high so any blocking must come from the per-key override.
        app.add_middleware(
            RateLimitMiddleware,
            store=store,
            enabled=True,
            default_requests=1000,
            default_window_seconds=60,
            apikey_window_seconds=60,
        )

        # The per-key bucket is honoured only on the production (X-API-Key) surface.
        @app.get("/api/v1/production/secured")
        async def secured():
            return {"ok": True}

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                headers = {"X-API-Key": raw_key}
                path = "/api/v1/production/secured"
                assert (await client.get(path, headers=headers)).status_code == 200
                assert (await client.get(path, headers=headers)).status_code == 200
                blocked = await client.get(path, headers=headers)
                assert blocked.status_code == 429
                assert "Retry-After" in blocked.headers
        finally:
            await store.close()
            await api_key.delete()
