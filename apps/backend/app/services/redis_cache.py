"""
Redis caching service for improved performance
"""
import json
import pickle
import logging
from typing import Any, Optional, Union, Dict, List
from datetime import timedelta
import asyncio
import redis.asyncio as redis
from redis.asyncio import Redis
import os
from functools import wraps

logger = logging.getLogger(__name__)


class RedisCacheService:
    """Service for Redis caching operations"""
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client: Optional[Redis] = None
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
        """Serialize value for storage"""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value).encode('utf-8')
        else:
            # Use pickle for complex objects
            return pickle.dumps(value)
            
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from storage"""
        try:
            # Try JSON first
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to pickle
            return pickle.loads(data)
            
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
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
            
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        if not self.redis_client:
            return None
            
        try:
            data = await self.redis_client.get(key)
            if data is None:
                return None
            return self._deserialize_value(data)
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
            
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter"""
        if not self.redis_client:
            return None
            
        try:
            return await self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Failed to increment key {key}: {e}")
            return None
            
    async def set_hash(self, key: str, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set a hash in cache"""
        if not self.redis_client:
            return False
            
        try:
            # Serialize hash values
            serialized_mapping = {
                field: self._serialize_value(value)
                for field, value in mapping.items()
            }
            await self.redis_client.hset(key, mapping=serialized_mapping)
            
            if ttl:
                await self.redis_client.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"Failed to set hash {key}: {e}")
            return False
            
    async def get_hash(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a hash from cache"""
        if not self.redis_client:
            return None
            
        try:
            data = await self.redis_client.hgetall(key)
            if not data:
                return None
                
            # Deserialize hash values
            return {
                field.decode('utf-8'): self._deserialize_value(value)
                for field, value in data.items()
            }
        except Exception as e:
            logger.error(f"Failed to get hash {key}: {e}")
            return None
            
    async def get_hash_field(self, key: str, field: str) -> Optional[Any]:
        """Get a specific field from hash"""
        if not self.redis_client:
            return None
            
        try:
            data = await self.redis_client.hget(key, field)
            if data is None:
                return None
            return self._deserialize_value(data)
        except Exception as e:
            logger.error(f"Failed to get hash field {key}.{field}: {e}")
            return None
            
    async def set_list(self, key: str, values: List[Any], ttl: Optional[int] = None) -> bool:
        """Set a list in cache"""
        if not self.redis_client:
            return False
            
        try:
            # Clear existing list and set new values
            await self.redis_client.delete(key)
            if values:
                serialized_values = [self._serialize_value(v) for v in values]
                await self.redis_client.lpush(key, *serialized_values)
                
            if ttl:
                await self.redis_client.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"Failed to set list {key}: {e}")
            return False
            
    async def get_list(self, key: str) -> Optional[List[Any]]:
        """Get a list from cache"""
        if not self.redis_client:
            return None
            
        try:
            data = await self.redis_client.lrange(key, 0, -1)
            if not data:
                return []
            return [self._deserialize_value(item) for item in reversed(data)]
        except Exception as e:
            logger.error(f"Failed to get list {key}: {e}")
            return None
            
    async def cache_user_progress(self, user_id: str, progress_data: Dict[str, Any]) -> bool:
        """Cache user onboarding progress"""
        key = f"user_progress:{user_id}"
        return await self.set_hash(key, progress_data, ttl=86400)  # 24 hours
        
    async def get_user_progress(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user progress"""
        key = f"user_progress:{user_id}"
        return await self.get_hash(key)
        
    async def cache_data_stats(self, data_id: str, stats: Dict[str, Any]) -> bool:
        """Cache data statistics"""
        key = f"data_stats:{data_id}"
        return await self.set(key, stats, ttl=7200)  # 2 hours
        
    async def get_data_stats(self, data_id: str) -> Optional[Dict[str, Any]]:
        """Get cached data statistics"""
        key = f"data_stats:{data_id}"
        return await self.get(key)
        
    async def cache_model_predictions(self, model_id: str, input_hash: str, predictions: Any) -> bool:
        """Cache model predictions"""
        key = f"predictions:{model_id}:{input_hash}"
        return await self.set(key, predictions, ttl=3600)  # 1 hour
        
    async def get_model_predictions(self, model_id: str, input_hash: str) -> Optional[Any]:
        """Get cached predictions"""
        key = f"predictions:{model_id}:{input_hash}"
        return await self.get(key)
        
    async def cache_eda_results(self, data_id: str, eda_results: Dict[str, Any]) -> bool:
        """Cache EDA analysis results"""
        key = f"eda:{data_id}"
        return await self.set(key, eda_results, ttl=10800)  # 3 hours
        
    async def get_eda_results(self, data_id: str) -> Optional[Dict[str, Any]]:
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
        
    async def get_cache_info(self) -> Dict[str, Any]:
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


def cache_result(key_pattern: str, ttl: Optional[int] = None):
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