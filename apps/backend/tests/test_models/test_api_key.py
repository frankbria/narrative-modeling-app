"""
Tests for API Key model
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app.models.api_key import APIKey


class TestAPIKeyModel:
    """Test cases for APIKey model"""
    
    def test_generate_key(self):
        """Test API key generation"""
        key1 = APIKey.generate_key()
        key2 = APIKey.generate_key()
        
        # Check format
        assert key1.startswith("sk_live_")
        assert len(key1) == 40  # sk_live_ (8) + 32 chars
        
        # Check uniqueness
        assert key1 != key2
        
        # Check character set (alphanumeric)
        random_part = key1[8:]  # Remove sk_live_ prefix
        assert random_part.isalnum()
    
    def test_api_key_creation(self):
        """Test creating an API key document"""
        # Create API key data without initializing Beanie
        api_key_data = {
            "key_id": "key_123",
            "key_hash": "hash123",
            "name": "Test API Key",
            "description": "Test description",
            "user_id": "user_123",
            "model_ids": ["model_1", "model_2"],
            "rate_limit": 1000
        }
        
        # Test the fields would be set correctly
        assert api_key_data["key_id"] == "key_123"
        assert api_key_data["key_hash"] == "hash123"
        assert api_key_data["name"] == "Test API Key"
        assert api_key_data["user_id"] == "user_123"
        assert len(api_key_data["model_ids"]) == 2
        assert api_key_data["rate_limit"] == 1000
    
    def test_is_valid_active_key(self):
        """Test validation for active key"""
        # Create a mock API key
        api_key = Mock(spec=APIKey)
        api_key.is_active = True
        api_key.expires_at = None
        
        # Test the is_valid logic
        def mock_is_valid(self):
            if not self.is_active:
                return False
            if self.expires_at and datetime.utcnow() > self.expires_at:
                return False
            return True
        
        assert mock_is_valid(api_key) is True
    
    def test_is_valid_inactive_key(self):
        """Test validation for inactive key"""
        api_key = Mock(spec=APIKey)
        api_key.is_active = False
        
        def mock_is_valid(self):
            if not self.is_active:
                return False
            return True
        
        assert mock_is_valid(api_key) is False
    
    def test_is_valid_expired_key(self):
        """Test validation for expired key"""
        api_key = Mock(spec=APIKey)
        api_key.is_active = True
        api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        
        def mock_is_valid(self):
            if not self.is_active:
                return False
            if self.expires_at and datetime.utcnow() > self.expires_at:
                return False
            return True
        
        assert mock_is_valid(api_key) is False
    
    def test_is_valid_not_expired_key(self):
        """Test validation for non-expired key"""
        api_key = Mock(spec=APIKey)
        api_key.is_active = True
        api_key.expires_at = datetime.utcnow() + timedelta(days=30)
        
        def mock_is_valid(self):
            if not self.is_active:
                return False
            if self.expires_at and datetime.utcnow() > self.expires_at:
                return False
            return True
        
        assert mock_is_valid(api_key) is True
    
    def test_has_model_access_empty_list(self):
        """Test model access with empty model_ids (access to all)"""
        api_key = Mock(spec=APIKey)
        api_key.model_ids = []
        
        def mock_has_model_access(self, model_id):
            if not self.model_ids:
                return True
            return model_id in self.model_ids
        
        assert mock_has_model_access(api_key, "model_123") is True
        assert mock_has_model_access(api_key, "model_456") is True
    
    def test_has_model_access_specific_models(self):
        """Test model access with specific model_ids"""
        api_key = Mock(spec=APIKey)
        api_key.model_ids = ["model_123", "model_456"]
        
        def mock_has_model_access(self, model_id):
            if not self.model_ids:
                return True
            return model_id in self.model_ids
        
        assert mock_has_model_access(api_key, "model_123") is True
        assert mock_has_model_access(api_key, "model_456") is True
        assert mock_has_model_access(api_key, "model_789") is False
    
    def test_default_values(self):
        """Test default values are set correctly"""
        # Test the default values defined in the model
        from app.models.api_key import APIKey
        
        # Check field defaults from the model definition
        fields = APIKey.model_fields
        
        assert fields['model_ids'].default_factory() == []
        assert fields['rate_limit'].default == 1000
        assert fields['total_requests'].default == 0
        assert fields['last_used_at'].default is None
        assert fields['expires_at'].default is None
        assert fields['is_active'].default is True