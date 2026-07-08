"""
Redis caching service for improved performance
"""
import json
import logging
import os
import pickle
from collections.abc import Awaitable
from functools import wraps
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
        """Delete all keys matching pattern"""
        if not self.redis_client:
            return 0
            
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
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
            
    async def increment(self, key: str, amount: int = 1) -> int | None:
        """Increment a counter"""
        if not self.redis_client:
            return None
            
        try:
            return await self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Failed to increment key {key}: {e}")
            return None
            
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
            
    async def get_hash_field(self, key: str, field: str) -> Any | None:
        """Get a specific field from hash"""
        if not self.redis_client:
            return None
            
        try:
            data = await cast(
                Awaitable[bytes | None], self.redis_client.hget(key, field)
            )
            if data is None:
                return None
            return self._deserialize_value(data)
        except ValueError as e:
            logger.warning("Hash field %s.%s treated as miss: %s", key, field, e)
            return None
        except Exception as e:
            logger.error(f"Failed to get hash field {key}.{field}: {e}")
            return None
            
    async def set_list(self, key: str, values: list[Any], ttl: int | None = None) -> bool:
        """Set a list in cache"""
        if not self.redis_client:
            return False
            
        try:
            # Clear existing list and set new values
            await self.redis_client.delete(key)
            if values:
                serialized_values = [self._serialize_value(v) for v in values]
                await cast(
                    Awaitable[int],
                    self.redis_client.lpush(key, *serialized_values),
                )
                
            if ttl:
                await self.redis_client.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"Failed to set list {key}: {e}")
            return False
            
    async def get_list(self, key: str) -> list[Any] | None:
        """Get a list from cache"""
        if not self.redis_client:
            return None
            
        try:
            data = await cast(
                Awaitable[list[Any]], self.redis_client.lrange(key, 0, -1)
            )
            if not data:
                return []
            return [self._deserialize_value(item) for item in reversed(data)]
        except ValueError as e:
            logger.warning("List %s treated as miss: %s", key, e)
            return None
        except Exception as e:
            logger.error(f"Failed to get list {key}: {e}")
            return None
            
    async def cache_user_progress(self, user_id: str, progress_data: dict[str, Any]) -> bool:
        """Cache user onboarding progress"""
        key = f"user_progress:{user_id}"
        return await self.set_hash(key, progress_data, ttl=86400)  # 24 hours
        
    async def get_user_progress(self, user_id: str) -> dict[str, Any] | None:
        """Get cached user progress"""
        key = f"user_progress:{user_id}"
        return await self.get_hash(key)
        
    async def cache_data_stats(self, data_id: str, stats: dict[str, Any]) -> bool:
        """Cache data statistics"""
        key = f"data_stats:{data_id}"
        return await self.set(key, stats, ttl=7200)  # 2 hours
        
    async def get_data_stats(self, data_id: str) -> dict[str, Any] | None:
        """Get cached data statistics"""
        key = f"data_stats:{data_id}"
        return await self.get(key)
        
    async def cache_model_predictions(self, model_id: str, input_hash: str, predictions: Any) -> bool:
        """Cache model predictions"""
        key = f"predictions:{model_id}:{input_hash}"
        return await self.set(key, predictions, ttl=3600)  # 1 hour
        
    async def get_model_predictions(self, model_id: str, input_hash: str) -> Any | None:
        """Get cached predictions"""
        key = f"predictions:{model_id}:{input_hash}"
        return await self.get(key)
        
    async def cache_eda_results(self, data_id: str, eda_results: dict[str, Any]) -> bool:
        """Cache EDA analysis results"""
        key = f"eda:{data_id}"
        return await self.set(key, eda_results, ttl=10800)  # 3 hours
        
    async def get_eda_results(self, data_id: str) -> dict[str, Any] | None:
        """Get cached EDA results"""
        key = f"eda:{data_id}"
        return await self.get(key)
        
    async def invalidate_user_cache(self, user_id: str) -> int:
        """Invalidate all cache entries for a user"""
        pattern = f"*:{user_id}*"
        return await self.delete_pattern(pattern)
        
    async def invalidate_data_cache(self, data_id: str) -> int:
        """Invalidate all cache entries for a dataset"""
        patterns = [
            f"data_stats:{data_id}",
            f"eda:{data_id}",
            f"predictions:{data_id}:*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            total_deleted += await self.delete_pattern(pattern)
        return total_deleted
        
    async def get_cache_info(self) -> dict[str, Any]:
        """Get cache statistics"""
        if not self.redis_client:
            return {"error": "Redis not connected"}
            
        try:
            info = await self.redis_client.info("memory")
            return {
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "connected_clients": info.get("connected_clients", 0),
                "total_connections_received": info.get("total_connections_received", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get cache info: {e}")
            return {"error": str(e)}


# Global cache service instance
cache_service = RedisCacheService()


def cache_result(key_pattern: str, ttl: int | None = None):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from pattern and arguments
            key = key_pattern.format(*args, **kwargs)
            
            # Try to get from cache first
            cached_result = await cache_service.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {key}")
                return cached_result
                
            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await cache_service.set(key, result, ttl)
                logger.debug(f"Cache set for key: {key}")
                
            return result
        return wrapper
    return decorator


async def init_cache():
    """Initialize cache service"""
    await cache_service.connect()


async def cleanup_cache():
    """Cleanup cache service"""
    await cache_service.disconnect()