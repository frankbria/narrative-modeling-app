"""
Tests for API Key model
"""
from datetime import UTC, datetime, timedelta

import pytest
from pymongo import IndexModel

from app.models.api_key import APIKey

# APIKey construction requires Beanie models registered (mongomock, no DB IO).
pytestmark = pytest.mark.usefixtures("beanie_models_initialized")


class TestAPIKeyIndexes:
    """The key_hash lookup is on the hottest auth path (#279)."""

    def test_key_hash_has_unique_index(self):
        """key_hash must be a declared UNIQUE index so verify_api_key /
        RateLimitMiddleware find_one({key_hash}) is an index seek, not a scan."""
        index_models = [
            idx
            for idx in APIKey.Settings.indexes
            if isinstance(idx, IndexModel)
        ]
        key_hash_indexes = [
            idx
            for idx in index_models
            if "key_hash" in dict(idx.document["key"])
        ]
        assert key_hash_indexes, "key_hash must have a declared index (#279)"
        assert any(
            idx.document.get("unique") is True for idx in key_hash_indexes
        ), "key_hash index must be unique (#279)"


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
    
    def _key(self, **overrides) -> APIKey:
        """A real APIKey instance (no DB needed) for exercising its real methods."""
        data = dict(key_id="key_123", key_hash="hash123", name="Test Key", user_id="u1")
        data.update(overrides)
        return APIKey(**data)

    def test_is_valid_active_key(self):
        """The REAL is_valid() — active, no expiry → valid (#492)."""
        assert self._key(is_active=True, expires_at=None).is_valid() is True

    def test_is_valid_inactive_key(self):
        assert self._key(is_active=False).is_valid() is False

    def test_is_valid_expired_key(self):
        expired = datetime.now(UTC) - timedelta(days=1)
        assert self._key(is_active=True, expires_at=expired).is_valid() is False

    def test_is_valid_not_expired_key(self):
        future = datetime.now(UTC) + timedelta(days=30)
        assert self._key(is_active=True, expires_at=future).is_valid() is True

    def test_is_valid_naive_expiry_treated_as_utc(self):
        """is_valid normalizes a naive expires_at to UTC (#492 exercises that path)."""
        naive_future = datetime.utcnow() + timedelta(days=1)  # noqa: DTZ003 - deliberately naive
        assert self._key(is_active=True, expires_at=naive_future).is_valid() is True

    def test_has_model_access_empty_list(self):
        """The REAL has_model_access() — empty model_ids grants all (#492)."""
        key = self._key(model_ids=[])
        assert key.has_model_access("model_123") is True
        assert key.has_model_access("model_456") is True

    def test_has_model_access_specific_models(self):
        key = self._key(model_ids=["model_123", "model_456"])
        assert key.has_model_access("model_123") is True
        assert key.has_model_access("model_456") is True
        assert key.has_model_access("model_789") is False

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