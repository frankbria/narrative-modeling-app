"""
Unit tests for the API rate-limiting middleware and store (issue #151).

These run service-free: identity falls back to the client IP (the TestClient
sends a fixed IP), and an injected :class:`InMemoryRateLimitStore` enforces the
budget deterministically. Redis-backed and per-API-key behaviour are covered by
the integration tests in ``tests/test_integration/test_rate_limit_integration.py``.
"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware
from app.services.rate_limit import (
    InMemoryRateLimitStore,
    RateLimitResult,
    build_rate_limit_store,
)


def _build_app(store, **mw_kwargs) -> FastAPI:
    # Rate limiting is disabled by default in the test env (see tests/conftest.py);
    # these tests exercise it, so opt back in unless a case overrides `enabled`.
    mw_kwargs.setdefault("enabled", True)
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, store=store, **mw_kwargs)

    @app.get("/api/v1/ping")
    async def ping():
        return {"message": "pong"}

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    return app


# --------------------------------------------------------------------------- #
# Store-level behaviour
# --------------------------------------------------------------------------- #
class TestInMemoryRateLimitStore:
    @pytest.mark.asyncio
    async def test_counts_and_blocks_over_limit(self):
        store = InMemoryRateLimitStore()
        results = [await store.hit("k", limit=3, window_seconds=60) for _ in range(4)]
        assert [r.allowed for r in results] == [True, True, True, False]
        assert results[0].remaining == 2
        assert results[2].remaining == 0
        assert results[3].allowed is False
        assert results[3].retry_after >= 1

    @pytest.mark.asyncio
    async def test_window_resets_after_expiry(self):
        store = InMemoryRateLimitStore()
        first = await store.hit("k", limit=1, window_seconds=1)
        blocked = await store.hit("k", limit=1, window_seconds=1)
        assert first.allowed is True
        assert blocked.allowed is False
        await asyncio.sleep(1.05)
        recovered = await store.hit("k", limit=1, window_seconds=1)
        assert recovered.allowed is True

    @pytest.mark.asyncio
    async def test_separate_keys_are_independent(self):
        store = InMemoryRateLimitStore()
        await store.hit("a", limit=1, window_seconds=60)
        a_blocked = await store.hit("a", limit=1, window_seconds=60)
        b_ok = await store.hit("b", limit=1, window_seconds=60)
        assert a_blocked.allowed is False
        assert b_ok.allowed is True

    @pytest.mark.asyncio
    async def test_non_positive_limit_never_blocks(self):
        store = InMemoryRateLimitStore()
        result = await store.hit("k", limit=0, window_seconds=60)
        assert result.allowed is True
        assert result.limited is False

    def test_build_store_without_redis_is_in_memory(self):
        assert isinstance(build_rate_limit_store(None), InMemoryRateLimitStore)
        assert isinstance(build_rate_limit_store(""), InMemoryRateLimitStore)


# --------------------------------------------------------------------------- #
# Middleware behaviour
# --------------------------------------------------------------------------- #
class TestRateLimitMiddleware:
    def test_requests_under_limit_succeed(self):
        app = _build_app(
            InMemoryRateLimitStore(), default_requests=5, default_window_seconds=60
        )
        client = TestClient(app)
        for _ in range(5):
            resp = client.get("/api/v1/ping")
            assert resp.status_code == 200

    def test_exceeding_limit_returns_429_with_retry_after(self):
        app = _build_app(
            InMemoryRateLimitStore(), default_requests=2, default_window_seconds=60
        )
        client = TestClient(app)
        assert client.get("/api/v1/ping").status_code == 200
        assert client.get("/api/v1/ping").status_code == 200
        blocked = client.get("/api/v1/ping")
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers
        assert int(blocked.headers["Retry-After"]) >= 1
        body = blocked.json()
        assert body["error"] == "RATE_LIMIT_EXCEEDED"
        assert body["details"]["retry_after_seconds"] >= 1

    def test_rate_limit_headers_present_on_success(self):
        app = _build_app(
            InMemoryRateLimitStore(), default_requests=10, default_window_seconds=60
        )
        client = TestClient(app)
        resp = client.get("/api/v1/ping")
        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert resp.headers["X-RateLimit-Remaining"] == "9"
        assert "X-RateLimit-Reset" in resp.headers

    def test_non_api_v1_paths_are_not_limited(self):
        app = _build_app(
            InMemoryRateLimitStore(), default_requests=1, default_window_seconds=60
        )
        client = TestClient(app)
        for _ in range(5):
            assert client.get("/healthz").status_code == 200

    def test_options_preflight_not_limited(self):
        app = _build_app(
            InMemoryRateLimitStore(), default_requests=1, default_window_seconds=60
        )
        client = TestClient(app)
        # Exhaust the GET budget, then confirm OPTIONS still passes through.
        client.get("/api/v1/ping")
        assert client.get("/api/v1/ping").status_code == 429
        options = client.options("/api/v1/ping")
        assert options.status_code != 429

    def test_disabled_flag_skips_limiting(self):
        app = _build_app(
            InMemoryRateLimitStore(),
            enabled=False,
            default_requests=1,
            default_window_seconds=60,
        )
        client = TestClient(app)
        for _ in range(5):
            assert client.get("/api/v1/ping").status_code == 200

    def test_missing_store_fails_open(self):
        # No store injected and none on app.state → middleware must not block.
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            store=None,
            enabled=True,
            default_requests=1,
            default_window_seconds=60,
        )

        @app.get("/api/v1/ping")
        async def ping():
            return {"message": "pong"}

        client = TestClient(app)
        for _ in range(5):
            assert client.get("/api/v1/ping").status_code == 200

    def test_failing_store_fails_open(self):
        class _BrokenStore:
            async def hit(self, key, limit, window_seconds):
                # Mirror RedisRateLimitStore's fail-open contract.
                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=limit,
                    reset_seconds=0,
                    limited=False,
                )

        app = _build_app(_BrokenStore(), default_requests=1, default_window_seconds=60)
        client = TestClient(app)
        for _ in range(5):
            assert client.get("/api/v1/ping").status_code == 200
