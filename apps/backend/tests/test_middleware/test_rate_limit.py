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
from starlette.requests import Request

from app.middleware.rate_limit import RateLimitMiddleware, client_ip
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

    # A bearer-authed production management route (NOT an X-API-Key route).
    @app.get("/api/v1/production/api-keys")
    async def list_keys():
        return {"keys": []}

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

    @pytest.mark.parametrize("trust_proxy", [False, True])
    def test_spoofed_forwarded_for_never_mints_a_bucket(self, trust_proxy):
        # #483: nginx APPENDS to X-Forwarded-For, so element [0] is whatever the
        # client sent — under BOTH flag settings a varying XFF must share one bucket.
        app = _build_app(
            InMemoryRateLimitStore(),
            default_requests=2,
            default_window_seconds=60,
            trust_proxy=trust_proxy,
        )
        client = TestClient(app)
        for spoofed in ("1.1.1.1", "2.2.2.2"):
            assert (
                client.get(
                    "/api/v1/ping", headers={"X-Forwarded-For": spoofed}
                ).status_code
                == 200
            )
        blocked = client.get("/api/v1/ping", headers={"X-Forwarded-For": "3.3.3.3"})
        assert blocked.status_code == 429

    def test_real_ip_honored_when_trusted(self):
        # Behind nginx, X-Real-IP is set from $remote_addr and OVERWRITTEN, so it is
        # authoritative — each distinct real client gets its own bucket.
        app = _build_app(
            InMemoryRateLimitStore(),
            default_requests=1,
            default_window_seconds=60,
            trust_proxy=True,
        )
        client = TestClient(app)
        assert (
            client.get("/api/v1/ping", headers={"X-Real-IP": "1.1.1.1"}).status_code
            == 200
        )
        # Same client → blocked; different client → still allowed.
        assert (
            client.get("/api/v1/ping", headers={"X-Real-IP": "1.1.1.1"}).status_code
            == 429
        )
        assert (
            client.get("/api/v1/ping", headers={"X-Real-IP": "9.9.9.9"}).status_code
            == 200
        )

    def test_api_key_header_ignored_on_non_production_route(self):
        # An X-API-Key on a non-production /api/v1 route must NOT opt into a key
        # bucket — the default per-user/IP budget still applies (no DB touched).
        app = _build_app(
            InMemoryRateLimitStore(), default_requests=2, default_window_seconds=60
        )
        client = TestClient(app)
        headers = {"X-API-Key": "sk_live_whatever"}
        assert client.get("/api/v1/ping", headers=headers).status_code == 200
        assert client.get("/api/v1/ping", headers=headers).status_code == 200
        # 3rd request blocked by the DEFAULT budget, proving the key path was skipped.
        assert client.get("/api/v1/ping", headers=headers).status_code == 429

    def test_api_key_header_ignored_on_bearer_management_route(self):
        # /api/v1/production/api-keys is bearer-authed, not X-API-Key — a key here
        # must not opt into a key bucket. The default budget applies (no DB touched).
        app = _build_app(
            InMemoryRateLimitStore(), default_requests=2, default_window_seconds=60
        )
        client = TestClient(app)
        headers = {"X-API-Key": "sk_live_whatever"}
        path = "/api/v1/production/api-keys"
        assert client.get(path, headers=headers).status_code == 200
        assert client.get(path, headers=headers).status_code == 200
        assert client.get(path, headers=headers).status_code == 429

    def test_store_returning_fail_open_result_is_not_limited(self):
        # A store that returns a fail-open RESULT (e.g. RedisRateLimitStore's
        # internal fail-open) must pass requests through without limiting.
        class _FailOpenStore:
            async def hit(self, key, limit, window_seconds):
                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=limit,
                    reset_seconds=0,
                    limited=False,
                )

        app = _build_app(
            _FailOpenStore(), default_requests=1, default_window_seconds=60
        )
        client = TestClient(app)
        for _ in range(5):
            assert client.get("/api/v1/ping").status_code == 200

    def test_raising_store_fails_open(self):
        # A store that unexpectedly RAISES must not 500 — the middleware catches
        # it and fails open (defence in depth on top of the stores' own handling).
        class _RaisingStore:
            async def hit(self, key, limit, window_seconds):
                raise RuntimeError("backend exploded")

        app = _build_app(_RaisingStore(), default_requests=1, default_window_seconds=60)
        client = TestClient(app)
        for _ in range(5):
            assert client.get("/api/v1/ping").status_code == 200


# --------------------------------------------------------------------------- #
# Per-key budget floor (issue #455)
# --------------------------------------------------------------------------- #
class TestApiKeyLimitFloor:
    """A stored ``APIKey.rate_limit`` of 0 must not mean "unlimited".

    Creation now clamps to the plan ceiling and rejects values < 1, but rows
    written before that (and any future write that bypasses the route) must still
    be limited — the store reads ``limit <= 0`` as "no enforcement", so the
    middleware floors the value it hands over.
    """

    @staticmethod
    def _app_with_key(store, stored_limit: int, monkeypatch):
        from app.models.api_key import APIKey

        raw_key = "sk_live_floor_test_key"
        # model_construct: these tests are service-free, and Document.__init__
        # would demand an initialised Beanie collection.
        key = APIKey.model_construct(
            key_id="key_floor_test",
            key_hash=APIKey.hash_key(raw_key),
            name="legacy",
            user_id="u1",
            rate_limit=stored_limit,
            is_active=True,
            expires_at=None,
        )

        async def _find_one(*_args, **_kwargs):
            return key

        monkeypatch.setattr(APIKey, "find_one", _find_one)

        app = _build_app(
            store,
            default_requests=1000,
            default_window_seconds=60,
            apikey_window_seconds=60,
        )

        @app.get("/api/v1/production/v1/models/m1/predict")
        async def predict():
            return {"ok": True}

        return app, raw_key

    @pytest.mark.parametrize("stored_limit", [0, -1])
    def test_non_positive_stored_limit_is_still_limited(
        self, stored_limit, monkeypatch
    ):
        app, raw_key = self._app_with_key(
            InMemoryRateLimitStore(), stored_limit, monkeypatch
        )
        client = TestClient(app)
        headers = {"X-API-Key": raw_key}
        path = "/api/v1/production/v1/models/m1/predict"
        # Floored to 1 request per window: the first passes, the second does not.
        assert client.get(path, headers=headers).status_code == 200
        assert client.get(path, headers=headers).status_code == 429

    def test_positive_stored_limit_is_untouched(self, monkeypatch):
        app, raw_key = self._app_with_key(InMemoryRateLimitStore(), 3, monkeypatch)
        client = TestClient(app)
        headers = {"X-API-Key": raw_key}
        path = "/api/v1/production/v1/models/m1/predict"
        for _ in range(3):
            assert client.get(path, headers=headers).status_code == 200
        assert client.get(path, headers=headers).status_code == 429


# --------------------------------------------------------------------------- #
# Key derivation, tested directly (#483)
# --------------------------------------------------------------------------- #
def _request(headers: dict[str, str], peer: str = "10.0.0.9") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/ping",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 40000),
    }
    return Request(scope)


class TestClientIp:
    """The limiter is disabled in the test env (CLAUDE.md), so the middleware-level
    tests above opt back in — but the identity rule itself is asserted here directly
    so it cannot pass vacuously through a disabled limiter."""

    @pytest.mark.parametrize("trust_proxy", [False, True])
    def test_forwarded_for_is_never_read(self, trust_proxy):
        req = _request({"X-Forwarded-For": "6.6.6.6, 7.7.7.7"})
        assert client_ip(req, trust_proxy=trust_proxy) == "10.0.0.9"

    def test_real_ip_ignored_when_untrusted(self):
        # Without a proxy in front, X-Real-IP is as spoofable as XFF.
        req = _request({"X-Real-IP": "6.6.6.6"})
        assert client_ip(req, trust_proxy=False) == "10.0.0.9"

    def test_real_ip_used_when_trusted(self):
        req = _request({"X-Real-IP": "6.6.6.6"})
        assert client_ip(req, trust_proxy=True) == "6.6.6.6"

    def test_trusted_but_header_absent_falls_back_to_peer(self):
        assert client_ip(_request({}), trust_proxy=True) == "10.0.0.9"

    def test_no_peer_is_unknown(self):
        req = _request({})
        req.scope["client"] = None
        assert client_ip(req, trust_proxy=False) == "unknown"
