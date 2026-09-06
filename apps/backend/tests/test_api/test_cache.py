"""Tests for the cache management API surface (issue #452).

The router used to expose Redis stats, arbitrary key delete/probe and a
glob-backed dataset purge to every authenticated user. Those routes are gone;
what remains is a single self-scoped purge. These tests run against a real
``RedisCacheService`` backed by an in-memory fake so tenant isolation is
observed on actual keys rather than asserted against a mock.
"""
import re

import pytest
from httpx import AsyncClient

from app.services.redis_cache import cache_service

CALLER = "test_user_123"  # what async_authorized_client authenticates as
OTHER_TENANT = "other_tenant_456"


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a Redis glob, honouring backslash-escaped metacharacters."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        out.append({"*": ".*", "?": "."}.get(char, re.escape(char)))
        i += 1
    return re.compile("".join(out) + r"\Z")


class FakeRedis:
    """Minimal async Redis stand-in over a dict.

    ``keys()`` rejects a pattern that is not anchored to a literal namespace
    prefix. An unanchored glob is exactly what let a purge reach another
    tenant's entries and the rate-limit buckets (issue #452), so a regression
    that reintroduces one fails here rather than silently matching too much.
    """

    def __init__(self, store: dict[str, bytes]):
        self.store = dict(store)

    async def keys(self, pattern):
        namespace = pattern.split(":", 1)[0]
        assert namespace and not set(namespace) & set("*?["), (
            f"cache purge issued an unanchored Redis glob: {pattern!r}"
        )
        matcher = _glob_to_regex(pattern)
        return [key.encode() for key in self.store if matcher.match(key)]

    async def delete(self, *names):
        keys = [n.decode() if isinstance(n, bytes) else n for n in names]
        return sum(1 for key in keys if self.store.pop(key, None) is not None)

    async def get(self, name):
        return self.store.get(name)


def _seed(caller: str = CALLER) -> dict[str, bytes]:
    return {
        f"user_progress:{caller}": b'"caller"',
        f"feature_selection:ds1:{caller}:mutual_info:abc123": b"{}",
        f"user_progress:{OTHER_TENANT}": b'"other"',
        f"feature_selection:ds1:{OTHER_TENANT}:mutual_info:abc123": b"{}",
        # Rate-limit buckets share the Redis instance; a purge must not touch
        # them, or a tenant can reset its own limiter (issue #452 AC3).
        f"ratelimit:user:{caller}": b"7",
        f"ratelimit:user:{OTHER_TENANT}": b"7",
        "data_stats:someones_dataset": b"{}",
    }


@pytest.fixture
def fake_redis():
    """Point the global cache service at an in-memory Redis for one test."""
    original = cache_service.redis_client
    fake = FakeRedis(_seed())
    cache_service.redis_client = fake
    yield fake
    cache_service.redis_client = original


class TestCachePurgeSelf:
    """DELETE /api/v1/cache/me — the only remaining cache route."""

    @pytest.mark.asyncio
    async def test_purges_only_the_callers_own_entries(
        self, async_authorized_client: AsyncClient, fake_redis: FakeRedis
    ):
        response = await async_authorized_client.delete("/api/v1/cache/me")

        assert response.status_code == 200
        assert response.json() == {"success": True, "deleted_entries": 2}
        assert set(fake_redis.store) == {
            f"user_progress:{OTHER_TENANT}",
            f"feature_selection:ds1:{OTHER_TENANT}:mutual_info:abc123",
            f"ratelimit:user:{CALLER}",
            f"ratelimit:user:{OTHER_TENANT}",
            "data_stats:someones_dataset",
        }

    @pytest.mark.asyncio
    async def test_never_evicts_a_rate_limit_bucket(
        self, async_authorized_client: AsyncClient, fake_redis: FakeRedis
    ):
        await async_authorized_client.delete("/api/v1/cache/me")

        assert f"ratelimit:user:{CALLER}" in fake_redis.store
        assert f"ratelimit:user:{OTHER_TENANT}" in fake_redis.store

    @pytest.mark.asyncio
    async def test_succeeds_when_nothing_is_cached(
        self, async_authorized_client: AsyncClient, fake_redis: FakeRedis
    ):
        fake_redis.store.clear()

        response = await async_authorized_client.delete("/api/v1/cache/me")

        assert response.status_code == 200
        assert response.json()["deleted_entries"] == 0

    @pytest.mark.asyncio
    async def test_reports_failure_when_redis_is_down(
        self, async_authorized_client: AsyncClient
    ):
        original = cache_service.redis_client
        cache_service.redis_client = None
        try:
            response = await async_authorized_client.delete("/api/v1/cache/me")
        finally:
            cache_service.redis_client = original

        assert response.status_code == 503


class TestRemovedCacheRoutes:
    """The pre-#452 surface is gone, not merely guarded."""

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/v1/cache/info"),
            ("DELETE", f"/api/v1/cache/user/{OTHER_TENANT}"),
            ("DELETE", f"/api/v1/cache/user/{CALLER}"),
            ("DELETE", "/api/v1/cache/data/*"),
            ("DELETE", "/api/v1/cache/data/someones_dataset"),
            ("DELETE", "/api/v1/cache/key/ratelimit:user:test_user_123"),
            ("GET", "/api/v1/cache/key/ratelimit:user:test_user_123/exists"),
            ("POST", f"/api/v1/cache/warmup/user/{CALLER}"),
        ],
    )
    @pytest.mark.asyncio
    async def test_route_no_longer_exists(
        self,
        async_authorized_client: AsyncClient,
        fake_redis: FakeRedis,
        method: str,
        path: str,
    ):
        response = await async_authorized_client.request(method, path)

        assert response.status_code in (404, 405)
        # Nothing was evicted on the way to the 404.
        assert fake_redis.store == _seed()
