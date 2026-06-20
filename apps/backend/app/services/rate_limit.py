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
from typing import Protocol

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


# Sweep expired buckets once the map grows past this many entries, so a churn of
# one-off identities (e.g. distinct IPs) can't grow the map without bound.
_PRUNE_THRESHOLD = 10_000


class InMemoryRateLimitStore:
    """Process-local fixed-window counter (single instance / tests).

    Keeps a ``{key: (count, window_start_monotonic, window_seconds)}`` map.
    Thread-safe via a lock so it behaves under the threadpool ``TestClient`` uses.
    Not shared across workers — a Redis store is required for correct
    multi-instance limiting.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[int, float, int]] = {}
        self._lock = Lock()

    def _now(self) -> float:
        return time.monotonic()

    def _prune_expired(self, now: float) -> None:
        """Drop buckets whose window has fully elapsed (caller holds the lock)."""
        expired = [
            k for k, (_, start, win) in self._buckets.items() if now - start >= win
        ]
        for k in expired:
            del self._buckets[k]

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        if limit <= 0:
            # A non-positive limit means "no enforcement"; never block.
            return _allow_unlimited(limit)

        now = self._now()
        with self._lock:
            count, window_start, _ = self._buckets.get(key, (0, now, window_seconds))
            if now - window_start >= window_seconds:
                # Window expired — start a fresh one.
                count, window_start = 0, now
            count += 1
            self._buckets[key] = (count, window_start, window_seconds)
            ttl = math.ceil(window_seconds - (now - window_start))
            if len(self._buckets) > _PRUNE_THRESHOLD:
                self._prune_expired(now)

        return _build_result(count, limit, ttl)

    def reset(self) -> None:
        """Clear all buckets (test helper)."""
        with self._lock:
            self._buckets.clear()


# Atomic fixed-window counter: INCR the key and, on the first hit of a window (or
# if the TTL was somehow lost), (re)arm the expiry — all in one round-trip so a
# concurrent caller can never observe a counted-but-unexpiring key. Returns
# {count, ttl_seconds}.
_INCR_WINDOW_LUA = """
local count = redis.call('INCR', KEYS[1])
local ttl
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
    ttl = tonumber(ARGV[1])
else
    ttl = redis.call('TTL', KEYS[1])
    if ttl < 0 then
        redis.call('EXPIRE', KEYS[1], ARGV[1])
        ttl = tonumber(ARGV[1])
    end
end
return {count, ttl}
"""


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
            # One atomic round-trip: increment + (re)arm the window TTL.
            count, ttl = await client.eval(
                _INCR_WINDOW_LUA, 1, redis_key, window_seconds
            )
            return _build_result(int(count), limit, int(ttl))
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
    redis_url: str | None, key_prefix: str = "ratelimit:"
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
