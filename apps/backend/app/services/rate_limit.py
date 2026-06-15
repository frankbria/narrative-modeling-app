"""
Rate-limit storage backends for the API rate-limiting middleware (issue #151).

A store answers one question per request: "has identity ``key`` exceeded ``limit``
requests within the current ``window_seconds`` window?" It returns a
:class:`RateLimitResult` describing the outcome plus the headers the middleware
needs (remaining budget, reset time, retry-after).

Two backends are provided:

- :class:`RedisRateLimitStore` — atomic ``INCR`` + ``EXPIRE`` fixed-window counter
  over async Redis. Correct across multiple workers/instances. **Fails open** on any
  Redis error so a cache outage never takes the API down.
- :class:`InMemoryRateLimitStore` — process-local fixed-window counter. Used by unit
  tests and as a single-instance fallback when no Redis is configured. Not shared
  across workers.

Both implement :class:`RateLimitStore`.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Outcome of a single rate-limit check.

    ``allowed`` is the only field the middleware must act on; the rest populate
    ``X-RateLimit-*`` / ``Retry-After`` headers. A fail-open result is simply an
    ``allowed`` result with ``limited=False`` and full ``remaining``.
    """

    allowed: bool
    limit: int
    remaining: int
    # Seconds until the current window resets (and, when blocked, how long to wait).
    reset_seconds: int
    # True only when this store actually enforced the limit (False = fail-open / disabled).
    limited: bool = True

    @property
    def retry_after(self) -> int:
        """Seconds a blocked caller should wait before retrying (>= 1)."""
        return max(1, self.reset_seconds)


class RateLimitStore(Protocol):
    """Protocol for a fixed-window rate-limit counter."""

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Record one request against ``key`` and report whether it is allowed."""
        ...


def _allow_unlimited(limit: int) -> RateLimitResult:
    """A fail-open / disabled result: always allowed, never reports as limited."""
    return RateLimitResult(
        allowed=True,
        limit=limit,
        remaining=limit,
        reset_seconds=0,
        limited=False,
    )


def _build_result(count: int, limit: int, ttl_seconds: int) -> RateLimitResult:
    """Translate a window count + ttl into a RateLimitResult."""
    remaining = max(0, limit - count)
    reset_seconds = max(0, ttl_seconds)
    return RateLimitResult(
        allowed=count <= limit,
        limit=limit,
        remaining=remaining,
        reset_seconds=reset_seconds,
        limited=True,
    )


class InMemoryRateLimitStore:
    """Process-local fixed-window counter (single instance / tests).

    Keeps a ``{key: (count, window_start_monotonic)}`` map. Thread-safe via a lock
    so it behaves under the threadpool ``TestClient`` uses. Not shared across
    workers — a Redis store is required for correct multi-instance limiting.
    """

    def __init__(self) -> None:
        self._buckets: Dict[str, Tuple[int, float]] = {}
        self._lock = Lock()

    def _now(self) -> float:
        return time.monotonic()

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        if limit <= 0:
            # A non-positive limit means "no enforcement"; never block.
            return _allow_unlimited(limit)

        now = self._now()
        with self._lock:
            count, window_start = self._buckets.get(key, (0, now))
            if now - window_start >= window_seconds:
                # Window expired — start a fresh one.
                count, window_start = 0, now
            count += 1
            self._buckets[key] = (count, window_start)
            ttl = math.ceil(window_seconds - (now - window_start))

        return _build_result(count, limit, ttl)

    def reset(self) -> None:
        """Clear all buckets (test helper)."""
        with self._lock:
            self._buckets.clear()


class RedisRateLimitStore:
    """Async-Redis fixed-window counter. Fails open on any Redis error."""

    def __init__(self, redis_url: str, key_prefix: str = "ratelimit:") -> None:
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._client = None  # lazily created on first hit
        self._failed_open_logged = False

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as redis

            # decode_responses=True so INCR returns ints/strs we can int() directly.
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        if limit <= 0:
            return _allow_unlimited(limit)

        redis_key = f"{self._key_prefix}{key}"
        try:
            client = await self._get_client()
            # Atomic-ish: INCR then, only on the first hit of the window, set the TTL.
            count = int(await client.incr(redis_key))
            if count == 1:
                await client.expire(redis_key, window_seconds)
                ttl = window_seconds
            else:
                ttl = int(await client.ttl(redis_key))
                if ttl < 0:
                    # Key exists without a TTL (e.g. EXPIRE lost to a crash) — repair it.
                    await client.expire(redis_key, window_seconds)
                    ttl = window_seconds
            return _build_result(count, limit, ttl)
        except Exception as exc:  # pragma: no cover - exercised via fail-open test
            # Availability over strict enforcement: never block on a limiter outage.
            if not self._failed_open_logged:
                logger.warning(
                    "Rate-limit Redis unavailable (%s); failing open — requests "
                    "are not being limited.",
                    exc,
                )
                self._failed_open_logged = True
            return _allow_unlimited(limit)

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
            self._client = None


def build_rate_limit_store(
    redis_url: Optional[str], key_prefix: str = "ratelimit:"
) -> RateLimitStore:
    """Pick a store: Redis when a URL is configured, else in-memory fallback."""
    if redis_url:
        logger.info("Rate limiting backed by Redis.")
        return RedisRateLimitStore(redis_url, key_prefix=key_prefix)
    logger.warning(
        "No REDIS_URL configured — rate limiting uses a process-local in-memory "
        "store (not shared across workers)."
    )
    return InMemoryRateLimitStore()
