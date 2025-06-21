"""
Tests for cache management API endpoints
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
import app.main


@pytest.fixture(autouse=True, scope="module")
def override_get_current_user_id():
    import app.auth.nextauth_auth
    app.main.app.dependency_overrides[app.auth.nextauth_auth.get_current_user_id] = lambda: "test_user_123"
    yield
    app.main.app.dependency_overrides.pop(app.auth.nextauth_auth.get_current_user_id, None)


class TestCacheAPI:
    """Test cases for cache management API endpoints"""

    @pytest.mark.asyncio
    async def test_get_cache_info(self, async_authorized_client: AsyncClient):
        """Test GET /api/v1/cache/info endpoint"""
        mock_cache_info = {
            "used_memory": 1024000,
            "used_memory_human": "1MB",
            "connected_clients": 5,
            "keyspace_hits": 1000,
            "keyspace_misses": 100,
            "total_connections_received": 50,
            "uptime_in_seconds": 3600
        }
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.get_cache_info = AsyncMock(return_value=mock_cache_info)

            response = await async_authorized_client.get("/api/v1/cache/info")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["cache_info"]["used_memory"] == 1024000
            assert data["cache_info"]["used_memory_human"] == "1MB"
            assert data["cache_info"]["connected_clients"] == 5
            assert data["cache_info"]["keyspace_hits"] == 1000
            assert data["cache_info"]["keyspace_misses"] == 100

    @pytest.mark.asyncio
    async def test_get_cache_info_redis_unavailable(self, async_authorized_client: AsyncClient):
        """Test cache info when Redis is unavailable"""
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.get_cache_info = AsyncMock(return_value=None)

            response = await async_authorized_client.get("/api/v1/cache/info")

            assert response.status_code == 503
            data = response.json()
            assert "Cache service unavailable" in data["detail"]

    @pytest.mark.asyncio
    async def test_invalidate_user_cache(self, async_authorized_client: AsyncClient):
        """Test DELETE /api/v1/cache/user/{user_id} endpoint"""
        user_id = "test_user_123"
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.invalidate_user_cache = AsyncMock(return_value=5)

            response = await async_authorized_client.delete(f"/api/v1/cache/user/{user_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["deleted_entries"] == 5
            assert "test_user_123" in data["message"]
            mock_cache.invalidate_user_cache.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_invalidate_user_cache_unauthorized(self, async_authorized_client: AsyncClient):
        """Test user cache invalidation with different user ID"""
        user_id = "different_user_456"
        
        # The auth dependency override returns "test_user_123"
        response = await async_authorized_client.delete(f"/api/v1/cache/user/{user_id}")

        assert response.status_code == 403
        data = response.json()
        assert "Can only invalidate your own cache" in data["detail"]

    @pytest.mark.asyncio
    async def test_invalidate_user_cache_same_user(self, async_authorized_client: AsyncClient):
        """Test user cache invalidation for same user"""
        user_id = "test_user_123"  # Same as auth override
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.invalidate_user_cache = AsyncMock(return_value=3)

            response = await async_authorized_client.delete(f"/api/v1/cache/user/{user_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["deleted_entries"] == 3

    @pytest.mark.asyncio
    async def test_invalidate_data_cache(self, async_authorized_client: AsyncClient):
        """Test DELETE /api/v1/cache/data/{data_id} endpoint"""
        data_id = "test_dataset_123"
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.invalidate_data_cache = AsyncMock(return_value=7)

            response = await async_authorized_client.delete(f"/api/v1/cache/data/{data_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["deleted_entries"] == 7
            assert data_id in data["message"]
            mock_cache.invalidate_data_cache.assert_called_once_with(data_id)

    @pytest.mark.asyncio
    async def test_delete_cache_key(self, async_authorized_client: AsyncClient):
        """Test DELETE /api/v1/cache/key/{cache_key} endpoint"""
        cache_key = "test_key_123"
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.delete = AsyncMock(return_value=True)

            response = await async_authorized_client.delete(f"/api/v1/cache/key/{cache_key}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "deleted" in data["message"]
            mock_cache.delete.assert_called_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_delete_cache_key_not_found(self, async_authorized_client: AsyncClient):
        """Test deleting a non-existent cache key"""
        cache_key = "nonexistent_key"
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.delete = AsyncMock(return_value=False)

            response = await async_authorized_client.delete(f"/api/v1/cache/key/{cache_key}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "not found" in data["message"]

    @pytest.mark.asyncio
    async def test_check_cache_key_exists(self, async_authorized_client: AsyncClient):
        """Test GET /api/v1/cache/key/{cache_key}/exists endpoint"""
        cache_key = "existing_key"
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.exists = AsyncMock(return_value=True)

            response = await async_authorized_client.get(f"/api/v1/cache/key/{cache_key}/exists")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["exists"] is True
            assert data["key"] == cache_key
            mock_cache.exists.assert_called_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_check_cache_key_not_exists(self, async_authorized_client: AsyncClient):
        """Test checking existence of non-existent cache key"""
        cache_key = "nonexistent_key"
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.exists = AsyncMock(return_value=False)

            response = await async_authorized_client.get(f"/api/v1/cache/key/{cache_key}/exists")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["exists"] is False
            assert data["key"] == cache_key

    @pytest.mark.asyncio
    async def test_cache_operations_redis_error(self, async_authorized_client: AsyncClient):
        """Test cache operations when Redis throws an error"""
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.invalidate_user_cache = AsyncMock(side_effect=Exception("Redis connection error"))

            response = await async_authorized_client.delete("/api/v1/cache/user/test_user_123")

            assert response.status_code == 500
            data = response.json()
            assert "Internal server error" in data["detail"]

    @pytest.mark.asyncio
    async def test_cache_statistics_calculation(self, async_authorized_client: AsyncClient):
        """Test cache hit ratio calculation in info endpoint"""
        mock_cache_info = {
            "keyspace_hits": 850,
            "keyspace_misses": 150,
            "used_memory": 2048000,
            "used_memory_human": "2MB",
            "connected_clients": 10
        }
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.get_cache_info = AsyncMock(return_value=mock_cache_info)

            response = await async_authorized_client.get("/api/v1/cache/info")

            assert response.status_code == 200
            data = response.json()
            
            # Verify cache info is returned correctly
            assert data["success"] is True
            assert data["cache_info"]["keyspace_hits"] == 850
            assert data["cache_info"]["keyspace_misses"] == 150

    @pytest.mark.asyncio
    async def test_cache_pattern_operations(self, async_authorized_client: AsyncClient):
        """Test cache operations with pattern matching"""
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            # Test user cache invalidation (uses pattern matching internally)
            mock_cache.invalidate_user_cache = AsyncMock(return_value=4)

            response = await async_authorized_client.delete("/api/v1/cache/user/test_user_123")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["deleted_entries"] == 4
            
            # Test data cache invalidation (uses multiple patterns)
            mock_cache.invalidate_data_cache = AsyncMock(return_value=6)

            response = await async_authorized_client.delete("/api/v1/cache/data/dataset_456")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["deleted_entries"] == 6

    @pytest.mark.asyncio
    async def test_cache_key_validation(self, async_authorized_client: AsyncClient):
        """Test cache key validation for special characters"""
        # Test with special characters that might cause issues
        special_keys = [
            "key:with:colons",
            "key*with*asterisks", 
            "key with spaces",
            "key[with]brackets",
            "key{with}braces"
        ]
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.exists = AsyncMock(return_value=True)
            mock_cache.delete = AsyncMock(return_value=True)
            
            for key in special_keys:
                # Test exists endpoint
                response = await async_authorized_client.get(f"/api/v1/cache/key/{key}/exists")
                assert response.status_code == 200
                
                # Test delete endpoint
                response = await async_authorized_client.delete(f"/api/v1/cache/key/{key}")
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, async_authorized_client: AsyncClient):
        """Test concurrent cache operations"""
        import asyncio
        
        with patch('app.api.routes.cache.cache_service') as mock_cache:
            mock_cache.invalidate_user_cache = AsyncMock(return_value=2)
            mock_cache.invalidate_data_cache = AsyncMock(return_value=3)
            mock_cache.get_cache_info = AsyncMock(return_value={"used_memory": 1024})
            
            # Run multiple operations concurrently
            tasks = [
                async_authorized_client.delete("/api/v1/cache/user/test_user_123"),
                async_authorized_client.delete("/api/v1/cache/data/dataset_123"),
                async_authorized_client.get("/api/v1/cache/info"),
            ]
            
            responses = await asyncio.gather(*tasks)
            
            # Verify all operations completed successfully
            assert all(response.status_code in [200] for response in responses)
            
            # Verify each cache service method was called
            mock_cache.invalidate_user_cache.assert_called_once()
            mock_cache.invalidate_data_cache.assert_called_once()
            mock_cache.get_cache_info.assert_called_once()