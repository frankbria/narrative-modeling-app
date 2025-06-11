"""
Tests for Redis cache service
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import json

from app.services.redis_cache import RedisCacheService, cache_result, cache_service


class TestRedisCacheService:
    """Test cases for RedisCacheService"""
    
    def setup_method(self):
        """Setup for each test"""
        self.cache_service = RedisCacheService()
        
    @pytest.mark.asyncio
    async def test_init_cache_service(self):
        """Test cache service initialization"""
        assert self.cache_service.redis_url == "redis://localhost:6379"
        assert self.cache_service.default_ttl == 3600
        assert self.cache_service.redis_client is None
        
    @pytest.mark.asyncio
    async def test_serialize_deserialize_simple_types(self):
        """Test serialization of simple data types"""
        # Test string
        value = "test_string"
        serialized = self.cache_service._serialize_value(value)
        deserialized = self.cache_service._deserialize_value(serialized)
        assert deserialized == value
        
        # Test integer
        value = 42
        serialized = self.cache_service._serialize_value(value)
        deserialized = self.cache_service._deserialize_value(serialized)
        assert deserialized == value
        
        # Test float
        value = 3.14
        serialized = self.cache_service._serialize_value(value)
        deserialized = self.cache_service._deserialize_value(serialized)
        assert deserialized == value
        
        # Test boolean
        value = True
        serialized = self.cache_service._serialize_value(value)
        deserialized = self.cache_service._deserialize_value(serialized)
        assert deserialized == value
        
    @pytest.mark.asyncio
    async def test_serialize_deserialize_complex_types(self):
        """Test serialization of complex data types"""
        # Test dictionary
        value = {"key": "value", "number": 123, "nested": {"inner": "data"}}
        serialized = self.cache_service._serialize_value(value)
        deserialized = self.cache_service._deserialize_value(serialized)
        assert deserialized == value
        
        # Test list
        value = [1, 2, "three", {"four": 4}]
        serialized = self.cache_service._serialize_value(value)
        deserialized = self.cache_service._deserialize_value(serialized)
        assert deserialized == value
        
    @pytest.mark.asyncio
    async def test_set_get_operations(self):
        """Test basic set/get operations with mocked Redis"""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=b'{"data": "test_value"}')
        
        self.cache_service.redis_client = mock_redis
        
        # Test set operation
        result = await self.cache_service.set("test_key", {"data": "test_value"})
        assert result is True
        mock_redis.setex.assert_called_once()
        
        # Test get operation
        value = await self.cache_service.get("test_key")
        assert value == {"data": "test_value"}
        mock_redis.get.assert_called_once_with("test_key")
        
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test getting a non-existent key"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        
        self.cache_service.redis_client = mock_redis
        
        result = await self.cache_service.get("nonexistent_key")
        assert result is None
        
    @pytest.mark.asyncio
    async def test_delete_operations(self):
        """Test delete operations"""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        
        self.cache_service.redis_client = mock_redis
        
        result = await self.cache_service.delete("test_key")
        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")
        
    @pytest.mark.asyncio
    async def test_delete_pattern(self):
        """Test pattern-based deletion"""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[b"key1", b"key2", b"key3"])
        mock_redis.delete = AsyncMock(return_value=3)
        
        self.cache_service.redis_client = mock_redis
        
        result = await self.cache_service.delete_pattern("test_*")
        assert result == 3
        mock_redis.keys.assert_called_once_with("test_*")
        mock_redis.delete.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_exists_operation(self):
        """Test key existence check"""
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)
        
        self.cache_service.redis_client = mock_redis
        
        result = await self.cache_service.exists("test_key")
        assert result is True
        mock_redis.exists.assert_called_once_with("test_key")
        
    @pytest.mark.asyncio
    async def test_increment_operation(self):
        """Test counter increment"""
        mock_redis = AsyncMock()
        mock_redis.incrby = AsyncMock(return_value=5)
        
        self.cache_service.redis_client = mock_redis
        
        result = await self.cache_service.increment("counter_key", 2)
        assert result == 5
        mock_redis.incrby.assert_called_once_with("counter_key", 2)
        
    @pytest.mark.asyncio
    async def test_hash_operations(self):
        """Test hash set/get operations"""
        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock(return_value=True)
        mock_redis.hgetall = AsyncMock(return_value={
            b"field1": b'"value1"',
            b"field2": b'42'
        })
        mock_redis.expire = AsyncMock(return_value=True)
        
        self.cache_service.redis_client = mock_redis
        
        # Test hash set
        test_data = {"field1": "value1", "field2": 42}
        result = await self.cache_service.set_hash("test_hash", test_data, ttl=300)
        assert result is True
        
        # Test hash get
        retrieved_data = await self.cache_service.get_hash("test_hash")
        assert retrieved_data == test_data
        
    @pytest.mark.asyncio
    async def test_list_operations(self):
        """Test list set/get operations"""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.lpush = AsyncMock(return_value=3)
        mock_redis.lrange = AsyncMock(return_value=[b'"item3"', b'"item2"', b'"item1"'])
        mock_redis.expire = AsyncMock(return_value=True)
        
        self.cache_service.redis_client = mock_redis
        
        # Test list set
        test_list = ["item1", "item2", "item3"]
        result = await self.cache_service.set_list("test_list", test_list, ttl=300)
        assert result is True
        
        # Test list get
        retrieved_list = await self.cache_service.get_list("test_list")
        assert retrieved_list == test_list
        
    @pytest.mark.asyncio
    async def test_user_progress_caching(self):
        """Test user progress specific caching methods"""
        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock(return_value=True)
        mock_redis.hgetall = AsyncMock(return_value={
            b"user_id": b'"test_user"',
            b"progress": b'50'
        })
        mock_redis.expire = AsyncMock(return_value=True)
        
        self.cache_service.redis_client = mock_redis
        
        progress_data = {"user_id": "test_user", "progress": 50}
        
        # Test cache user progress
        result = await self.cache_service.cache_user_progress("test_user", progress_data)
        assert result is True
        
        # Test get user progress
        retrieved_progress = await self.cache_service.get_user_progress("test_user")
        assert retrieved_progress == progress_data
        
    @pytest.mark.asyncio
    async def test_data_stats_caching(self):
        """Test data statistics caching methods"""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=b'{"rows": 1000, "columns": 10}')
        
        self.cache_service.redis_client = mock_redis
        
        stats_data = {"rows": 1000, "columns": 10}
        
        # Test cache data stats
        result = await self.cache_service.cache_data_stats("data_123", stats_data)
        assert result is True
        
        # Test get data stats
        retrieved_stats = await self.cache_service.get_data_stats("data_123")
        assert retrieved_stats == stats_data
        
    @pytest.mark.asyncio
    async def test_model_predictions_caching(self):
        """Test model predictions caching"""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=b'[0.8, 0.2]')
        
        self.cache_service.redis_client = mock_redis
        
        predictions = [0.8, 0.2]
        
        # Test cache predictions
        result = await self.cache_service.cache_model_predictions("model_123", "input_hash", predictions)
        assert result is True
        
        # Test get predictions
        retrieved_predictions = await self.cache_service.get_model_predictions("model_123", "input_hash")
        assert retrieved_predictions == predictions
        
    @pytest.mark.asyncio
    async def test_eda_results_caching(self):
        """Test EDA results caching"""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=b'{"summary": "analysis complete"}')
        
        self.cache_service.redis_client = mock_redis
        
        eda_results = {"summary": "analysis complete"}
        
        # Test cache EDA results
        result = await self.cache_service.cache_eda_results("data_123", eda_results)
        assert result is True
        
        # Test get EDA results
        retrieved_results = await self.cache_service.get_eda_results("data_123")
        assert retrieved_results == eda_results
        
    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Test cache invalidation methods"""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[b"user:test_user:progress", b"data:test_user:stats"])
        mock_redis.delete = AsyncMock(return_value=2)
        
        self.cache_service.redis_client = mock_redis
        
        # Test user cache invalidation
        result = await self.cache_service.invalidate_user_cache("test_user")
        assert result == 2
        
        # Test data cache invalidation
        mock_redis.keys = AsyncMock(side_effect=[
            [b"data_stats:data_123"],
            [b"eda:data_123"],
            [b"predictions:data_123:hash1", b"predictions:data_123:hash2"]
        ])
        mock_redis.delete = AsyncMock(side_effect=[1, 1, 2])
        
        result = await self.cache_service.invalidate_data_cache("data_123")
        assert result == 4  # 1 + 1 + 2
        
    @pytest.mark.asyncio
    async def test_cache_info(self):
        """Test cache information retrieval"""
        mock_redis = AsyncMock()
        mock_redis.info = AsyncMock(return_value={
            "used_memory": 1024000,
            "used_memory_human": "1MB",
            "connected_clients": 5,
            "keyspace_hits": 100,
            "keyspace_misses": 10
        })
        
        self.cache_service.redis_client = mock_redis
        
        info = await self.cache_service.get_cache_info()
        assert info["used_memory"] == 1024000
        assert info["used_memory_human"] == "1MB"
        assert info["connected_clients"] == 5
        
    @pytest.mark.asyncio
    async def test_operations_without_redis_connection(self):
        """Test operations when Redis is not connected"""
        # Redis client is None by default
        
        # All operations should return appropriate defaults
        assert await self.cache_service.set("key", "value") is False
        assert await self.cache_service.get("key") is None
        assert await self.cache_service.delete("key") is False
        assert await self.cache_service.exists("key") is False
        assert await self.cache_service.increment("key") is None
        
    @pytest.mark.asyncio
    async def test_cache_result_decorator(self):
        """Test the cache_result decorator"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # Cache miss
        mock_redis.setex = AsyncMock(return_value=True)
        
        # Mock the global cache service
        with patch('app.services.redis_cache.cache_service') as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)  # Cache miss first
            mock_cache.set = AsyncMock(return_value=True)
            
            @cache_result("test_key_{0}", ttl=300)
            async def test_function(param):
                return f"result_for_{param}"
            
            # First call should execute function and cache result
            result1 = await test_function("param1")
            assert result1 == "result_for_param1"
            mock_cache.get.assert_called_with("test_key_param1")
            mock_cache.set.assert_called_with("test_key_param1", "result_for_param1", 300)
            
            # Second call should return cached result
            mock_cache.get = AsyncMock(return_value="cached_result")
            result2 = await test_function("param1")
            assert result2 == "cached_result"
            
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in cache operations"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        
        self.cache_service.redis_client = mock_redis
        
        # Operations should not raise exceptions, but return appropriate defaults
        result = await self.cache_service.get("test_key")
        assert result is None
        
        result = await self.cache_service.set("test_key", "value")
        assert result is False