"""
Redis caching service for improved performance
"""
import json
import logging
import os
import pickle
from collections.abc import Awaitable
from typing import Any, cast

import redis.asyncio as redis
from redis.asyncio import Redis

from app.utils.artifact_signing import sign_bytes, verify_bytes

logger = logging.getLogger(__name__)

# Prefix marking an HMAC-signed pickle blob (issue #266). JSON output never
# starts with a NUL byte, so this can't collide with the JSON path. Layout:
#   _SIGNED_PICKLE_PREFIX + <64-hex-char signature> + b":" + <pickle bytes>
_SIGNED_PICKLE_PREFIX = b"\x00SPKL:"
_SIG_HEX_LEN = 64  # sha256 hex digest length


# The cache key families scoped to exactly one user — what DELETE
# /api/v1/cache/me purges. Everything else the app caches is keyed by
# dataset/model/content hash. Rate-limit buckets ("ratelimit:") are
# deliberately absent: a purge must never reset a limiter (issue #452).
#
# Patterns are anchored to a literal namespace prefix so they cannot widen past
# their own family, and the id is glob-escaped before interpolation.
_USER_SCOPED_KEYS = ("user_progress:{user_id}",)
_USER_SCOPED_PATTERNS = ("feature_selection:*:{user_id}:*",)

# Redis glob metacharacters, escaped with a backslash.
_GLOB_ESCAPES = str.maketrans({char: "\\" + char for char in "*?[]\\"})

# SCAN COUNT hint (#570): how many keys Redis examines per cursor step. A larger
# value means fewer round-trips but more work per step; 500 keeps each step cheap
# while still draining these small, scoped key families in one or two pages.
_SCAN_COUNT = 500


class RedisCacheService:
    """Service for Redis caching operations"""
    
    def __init__(self) -> None:
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client: Redis | None = None
        self.default_ttl = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))  # 1 hour
        
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # We'll handle encoding manually
                max_connections=20
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
            
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage.

        Simple types go out as plain JSON (safe — JSON never executes code).
        Complex objects fall back to pickle, but the blob is HMAC-signed so it
        can be authenticated before ``pickle.loads`` on read (issue #266).
        """
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value).encode('utf-8')
        # Sign the pickle so a Redis tamperer can't turn our loads() into RCE.
        payload = pickle.dumps(value)
        return _SIGNED_PICKLE_PREFIX + sign_bytes(payload).encode('ascii') + b":" + payload

    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from storage.

        A signed-pickle blob is only unpickled after its HMAC verifies; an
        unsigned or tampered pickle raises (the caller treats it as a cache
        miss) rather than executing attacker-controlled bytes (issue #266).
        """
        if data.startswith(_SIGNED_PICKLE_PREFIX):
            body = data[len(_SIGNED_PICKLE_PREFIX):]
            signature = body[:_SIG_HEX_LEN].decode('ascii', errors='replace')
            payload = body[_SIG_HEX_LEN + 1:]  # skip the ":" separator
            if not verify_bytes(payload, signature):
                raise ValueError("Redis pickle signature mismatch; refusing to unpickle")
            return pickle.loads(payload)  # nosec B301 - HMAC-verified above
        try:
            # Try JSON (safe path).
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Unsigned legacy/raw pickle — never unpickle unauthenticated bytes.
            raise ValueError("Unsigned Redis value; refusing to unpickle")
            
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int | None = None
    ) -> bool:
        """Set a value in cache"""
        if not self.redis_client:
            return False
            
        try:
            ttl = ttl or self.default_ttl
            serialized_value = self._serialize_value(value)
            await self.redis_client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {e}")
            return False
            
    async def get(self, key: str) -> Any | None:
        """Get a value from cache"""
        if not self.redis_client:
            return None
            
        try:
            data = await self.redis_client.get(key)
            if data is None:
                return None
            return self._deserialize_value(data)
        except ValueError as e:
            # Expected: an unsigned legacy or tampered blob — treat as a miss.
            # WARNING (not ERROR) so a first-deploy wave of legacy entries aging
            # out of cache doesn't look like an incident (issue #266).
            logger.warning("Cache key %s treated as miss: %s", key, e)
            return None
        except Exception as e:
            logger.error(f"Failed to get cache key {key}: {e}")
            return None
            
    async def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        if not self.redis_client:
            return False
            
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {e}")
            return False
            
    async def delete_pattern(self, pattern: str) -> int:
        """Delete every key matching ``pattern``, scanning incrementally.

        Uses ``SCAN`` (cursor-based, non-blocking) instead of ``KEYS`` (#570):
        ``KEYS`` scans the whole keyspace in one call and blocks the Redis event
        loop while it does — and this shared instance also holds the rate-limit
        buckets, so a slow ``KEYS`` stalls the limiter for every tenant. ``SCAN``
        may return the same key on more than one cursor page, so deletions are
        deduplicated (``seen``); a key removed between the scan and the delete just
        isn't recounted, because ``DELETE`` reports only the keys it actually
        removed. ``MATCH`` uses the same glob grammar as ``KEYS`` (backslash escapes
        included), so every caller's pattern — and the returned count — is unchanged.
        """
        if not self.redis_client:
            return 0

        try:
            deleted = 0
            seen: set = set()
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor, match=pattern, count=_SCAN_COUNT
                )
                batch = [k for k in keys if k not in seen]
                if batch:
                    seen.update(batch)
                    deleted += await self.redis_client.delete(*batch)
                if cursor == 0:
                    break
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete pattern {pattern}: {e}")
            return 0
            
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.redis_client:
            return False
            
        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Failed to check existence of key {key}: {e}")
            return False
            
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        if not self.redis_client:
            return False
            
        try:
            return await self.redis_client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Failed to set expiry for key {key}: {e}")
            return False
            
    async def set_hash(self, key: str, mapping: dict[str, Any], ttl: int | None = None) -> bool:
        """Set a hash in cache"""
        if not self.redis_client:
            return False
            
        try:
            # Serialize hash values
            serialized_mapping = {
                field: self._serialize_value(value)
                for field, value in mapping.items()
            }
            await cast(
                Awaitable[int],
                self.redis_client.hset(key, mapping=serialized_mapping),
            )
            
            if ttl:
                await self.redis_client.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"Failed to set hash {key}: {e}")
            return False
            
    async def get_hash(self, key: str) -> dict[str, Any] | None:
        """Get a hash from cache"""
        if not self.redis_client:
            return None
            
        try:
            data = await cast(
                Awaitable[dict[Any, Any]], self.redis_client.hgetall(key)
            )
            if not data:
                return None
                
            # Deserialize hash values
            return {
                field.decode('utf-8'): self._deserialize_value(value)
                for field, value in data.items()
            }
        except ValueError as e:
            # Expected: an unsigned legacy or tampered field — treat as a miss
            # at WARNING, not ERROR (issue #266; consistent with get()).
            logger.warning("Hash %s treated as miss: %s", key, e)
            return None
        except Exception as e:
            logger.error(f"Failed to get hash {key}: {e}")
            return None
            
    async def cache_user_progress(self, user_id: str, progress_data: dict[str, Any]) -> bool:
        """Cache user onboarding progress"""
        key = f"user_progress:{user_id}"
        return await self.set_hash(key, progress_data, ttl=86400)  # 24 hours
        
    async def get_user_progress(self, user_id: str) -> dict[str, Any] | None:
        """Get cached user progress"""
        key = f"user_progress:{user_id}"
        return await self.get_hash(key)
        
    async def invalidate_user_cache(self, user_id: str) -> int:
        """Delete this user's cache entries across every user-scoped family.

        Each key is either addressed exactly or matched by a pattern anchored
        to its own namespace. The old ``*:{user_id}*`` pattern was anchored to
        nothing, so it also matched the ``ratelimit:`` buckets sharing this
        Redis — letting a user reset their own limiter (issue #452).
        """
        escaped_id = user_id.translate(_GLOB_ESCAPES)
        deleted = 0
        for template in _USER_SCOPED_KEYS:
            if await self.delete(template.format(user_id=user_id)):
                deleted += 1
        for pattern in _USER_SCOPED_PATTERNS:
            deleted += await self.delete_pattern(pattern.format(user_id=escaped_id))
        return deleted


# Global cache service instance
cache_service = RedisCacheService()


async def init_cache():
    """Initialize cache service"""
    await cache_service.connect()


async def cleanup_cache():
    """Cleanup cache service"""
    await cache_service.disconnect()