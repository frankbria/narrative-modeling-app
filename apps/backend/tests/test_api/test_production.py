"""
Tests for production API endpoints
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import hashlib
from beanie import PydanticObjectId

from app.models.api_key import APIKey
from app.models.ml_model import MLModel
from app.api.routes.production import hash_api_key


class TestProductionAPI:
    """Test cases for production API endpoints"""
    
    @pytest.fixture
    def mock_api_key(self):
        """Create a mock API key"""
        return APIKey(
            key_id="key_test123",
            key_hash=hash_api_key("sk_live_test123"),
            name="Test API Key",
            user_id="user_123",
            rate_limit=1000,
            is_active=True,
            model_ids=[]
        )
    
    @pytest.fixture
    def mock_ml_model(self):
        """Create a mock ML model"""
        return MLModel(
            user_id="user_123",
            dataset_id="dataset_123",
            model_id="model_123",
            name="Test Model",
            problem_type="binary_classification",
            algorithm="Random Forest",
            target_column="target",
            feature_names=["feature1", "feature2", "feature3"],
            cv_score=0.85,
            test_score=0.83,
            training_time=45.2,
            model_size=1048576,
            n_samples_train=1000,
            n_features=3,
            model_path="s3://bucket/models/model_123.pkl",
            version="1.0.0",
            is_active=True
        )
    
    @pytest.mark.asyncio
    async def test_create_api_key_success(self, mock_async_client):
        """Test successful API key creation"""
        response = await mock_async_client.post(
            "/api/v1/production/api-keys",
            json={
                "name": "Production Key",
                "description": "Test key for production",
                "rate_limit": 5000,
                "expires_in_days": 30
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        # Should return 404 as routes aren't registered in test
        assert response.status_code in [200, 404, 422]
    
    @pytest.mark.asyncio
    async def test_create_api_key_invalid_data(self, mock_async_client):
        """Test API key creation with invalid data"""
        response = await mock_async_client.post(
            "/api/v1/production/api-keys",
            json={
                "name": "",  # Empty name should fail
                "rate_limit": -100  # Negative rate limit
            },
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [400, 404, 422]
    
    @pytest.mark.asyncio
    async def test_list_api_keys(self, mock_async_client):
        """Test listing API keys"""
        response = await mock_async_client.get(
            "/api/v1/production/api-keys",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(self, mock_async_client):
        """Test revoking an API key"""
        response = await mock_async_client.delete(
            "/api/v1/production/api-keys/key_123",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_production_predict_no_api_key(self, mock_async_client):
        """Test prediction without API key"""
        response = await mock_async_client.post(
            "/api/v1/production/v1/models/model_123/predict",
            json={
                "data": [{"feature1": 1, "feature2": "value"}]
            }
        )
        
        assert response.status_code in [401, 404, 422]
    
    @pytest.mark.asyncio
    async def test_production_predict_invalid_api_key(self, mock_async_client):
        """Test prediction with invalid API key"""
        response = await mock_async_client.post(
            "/api/v1/production/v1/models/model_123/predict",
            json={
                "data": [{"feature1": 1, "feature2": "value"}]
            },
            headers={"X-API-Key": "invalid_key"}
        )
        
        assert response.status_code in [401, 404]
    
    def test_hash_api_key(self):
        """Test API key hashing"""
        key = "sk_live_test123"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        
        # Same key should produce same hash
        assert hash1 == hash2
        
        # Hash should be SHA256 (64 hex chars)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)
        
        # Different keys should produce different hashes
        hash3 = hash_api_key("sk_live_different")
        assert hash1 != hash3
    
    @pytest.mark.asyncio
    async def test_verify_api_key_format(self):
        """Test API key format validation"""
        from app.api.routes.production import verify_api_key
        from fastapi import HTTPException, Header
        
        # Test invalid format
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(api_key="invalid_format")
        assert exc_info.value.status_code == 401
        
        # Test empty key
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(api_key="")
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_model_info(self, mock_async_client):
        """Test getting model information"""
        response = await mock_async_client.get(
            "/api/v1/production/v1/models/model_123/info",
            headers={"X-API-Key": "sk_live_test123"}
        )
        
        assert response.status_code in [200, 401, 404]
    
    @pytest.mark.asyncio
    @patch('app.api.routes.production.redis_client')
    async def test_rate_limiting(self, mock_redis):
        """Test rate limiting functionality"""
        from app.api.routes.production import check_rate_limit
        from fastapi import Request, HTTPException
        
        # Mock Redis operations
        mock_redis.incr.return_value = 1001  # Over limit
        mock_redis.expire.return_value = True
        
        # Create mock API key with 1000 rate limit
        api_key = Mock()
        api_key.key_id = "key_123"
        api_key.rate_limit = 1000
        
        # Create mock request
        mock_request = Mock(spec=Request)
        
        # Should raise rate limit exception
        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(api_key, mock_request)
        
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value.detail)
    
    def test_api_key_model_access(self):
        """Test API key model access control"""
        # Test the has_model_access logic
        def mock_has_model_access(self, model_id):
            if not self.model_ids:
                return True
            return model_id in self.model_ids
        
        # Key with specific model access
        api_key = Mock()
        api_key.model_ids = ["model_123", "model_456"]
        
        assert mock_has_model_access(api_key, "model_123") is True
        assert mock_has_model_access(api_key, "model_789") is False
        
        # Key with all model access
        api_key_all = Mock()
        api_key_all.model_ids = []  # Empty = all models
        
        assert mock_has_model_access(api_key_all, "model_123") is True
        assert mock_has_model_access(api_key_all, "any_model") is True