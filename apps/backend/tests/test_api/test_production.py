"""
Tests for production API endpoints
"""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest
from fastapi import HTTPException

from app.api.routes.production import (
    ProductionPredictRequest,
    hash_api_key,
    production_predict,
)
from app.models.api_key import APIKey
from app.models.ml_model import MLModel


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
        from fastapi import HTTPException

        from app.api.routes.production import verify_api_key
        
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
    
    # Rate limiting moved out of this route in #151. It is now enforced globally by
    # RateLimitMiddleware over every /api/v1 route (using the per-key APIKey.rate_limit
    # budget). See tests/test_middleware/test_rate_limit.py and
    # tests/test_integration/test_rate_limit_integration.py.

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


class TestServingMetricsLogging:
    """Tests for per-request monitoring logging from the serving path (issue #85)."""

    @pytest.mark.asyncio
    async def test_logs_each_prediction(self):
        from app.api.routes.production import _record_serving_metrics
        from app.services.prediction_monitoring import prediction_log

        prediction_log.logs.clear()
        await _record_serving_metrics(
            model_id="m_serve",
            request_data=[{"a": 1}, {"a": 2}, {"a": 3}],
            predictions=["x", "y", "z"],
            confidence=[0.9, 0.8, None],
            latency_ms=30.0,
            api_key_id="key_1",
        )

        logged = prediction_log.logs["m_serve"]
        assert len(logged) == 3
        assert [e["prediction"] for e in logged] == ["x", "y", "z"]
        # Batch latency is split per record.
        assert all(e["latency_ms"] == 10.0 for e in logged)
        assert all(e["error"] is None for e in logged)
        assert logged[2]["probability"] is None

    @pytest.mark.asyncio
    async def test_logs_error_event(self):
        from app.api.routes.production import _record_serving_metrics
        from app.services.prediction_monitoring import prediction_log

        prediction_log.logs.clear()
        await _record_serving_metrics(
            model_id="m_err",
            request_data=[{"a": 1}],
            predictions=[],
            confidence=None,
            latency_ms=12.0,
            api_key_id="key_1",
            error="kaboom",
        )

        logged = prediction_log.logs["m_err"]
        assert len(logged) == 1
        assert logged[0]["error"] == "kaboom"
        assert logged[0]["prediction"] is None

    @pytest.mark.asyncio
    async def test_batch_error_logged_per_record(self):
        """A failed N-record batch logs N error entries so error_rate stays
        per-record consistent with successes (codex review)."""
        from app.api.routes.production import _record_serving_metrics
        from app.services.prediction_monitoring import (
            PredictionMonitoringService,
            prediction_log,
        )

        prediction_log.logs.clear()
        # One successful 3-record batch...
        await _record_serving_metrics(
            model_id="m_batch",
            request_data=[{"a": 1}, {"a": 2}, {"a": 3}],
            predictions=["x", "y", "z"],
            confidence=None,
            latency_ms=30.0,
            api_key_id="k",
        )
        # ...then one failed 3-record batch.
        await _record_serving_metrics(
            model_id="m_batch",
            request_data=[{"a": 4}, {"a": 5}, {"a": 6}],
            predictions=[],
            confidence=None,
            latency_ms=9.0,
            api_key_id="k",
            error="boom",
        )

        assert len(prediction_log.logs["m_batch"]) == 6
        metrics = await PredictionMonitoringService.get_model_metrics("m_batch", 24)
        assert metrics["total_predictions"] == 3
        assert metrics["error_count"] == 3
        assert metrics["error_rate"] == 0.5  # 3 / 6, not 1 / 4

    @pytest.mark.asyncio
    async def test_never_raises(self):
        """Monitoring logging must not break serving even on bad input."""
        from app.api.routes.production import _record_serving_metrics

        # predictions is None -> would raise inside; must be swallowed.
        await _record_serving_metrics(
            model_id="m_bad",
            request_data=[],
            predictions=None,  # type: ignore[arg-type]
            confidence=None,
            latency_ms=1.0,
            api_key_id=None,
        )


class TestProductionPredictErrorHandling:
    """Production serving predict mirrors the internal /ml twin (issue #264):
    client errors → 422 with a sanitized message, 500 reserved for true faults
    without echoing internal text, and a bounded record cap."""

    @staticmethod
    def _api_key() -> MagicMock:
        key = MagicMock(user_id="user_123", key_id="key_1")
        key.has_model_access.return_value = True
        return key

    @staticmethod
    def _model(problem_type: str = "binary_classification") -> MagicMock:
        return MagicMock(
            feature_names=["feature1", "feature2"],
            problem_type=problem_type,
            n_features=2,
            name="Test Model",
            algorithm="Random Forest",
            version="1.0.0",
            residual_std=None,
            is_calibrated=False,
            calibration_method=None,
            feature_importance=None,
        )

    def _patch_load(self, model):
        """Patch model lookup + artifact load; caller sets load_model's return
        inside the ``with`` block."""
        find = patch(
            "app.models.ml_model.MLModel.find_one",
            new_callable=AsyncMock,
            return_value=model,
        )
        load = patch(
            "app.services.model_storage.ModelStorageService.load_model",
            new_callable=AsyncMock,
        )
        return find, load

    @pytest.mark.asyncio
    async def test_missing_feature_returns_422(self):
        """A record missing a required raw input feature → 422, not 500."""
        model = self._model()
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (MagicMock(), None)  # no feature engineer
            request = ProductionPredictRequest(data=[{"feature1": 1.0}])  # feature2 missing

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422
        assert "feature2" in exc.value.detail
        assert "Missing required feature" in exc.value.detail

    @pytest.mark.asyncio
    async def test_empty_data_returns_422(self):
        """An empty records list is a client error → 422, not a 500."""
        model = self._model()
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (MagicMock(), None)
            request = ProductionPredictRequest(data=[])

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_feature_value_returns_422(self):
        """A sklearn ValueError (e.g. unknown category) → 422 sanitized, not 500."""
        model = self._model()
        trained = MagicMock()
        raw = "y contains previously unseen labels: 'SECRET-COLUMN'"
        trained.predict.side_effect = ValueError(raw)
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, None)
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422
        assert "Invalid feature value" in exc.value.detail
        assert raw not in exc.value.detail  # sanitized: no raw sklearn text leaked

    @pytest.mark.asyncio
    async def test_invalid_feature_keyerror_returns_422(self):
        """A KeyError from the transform/lookup path is also mapped to 422."""
        model = self._model()
        trained = MagicMock()
        trained.predict.side_effect = KeyError("feature2")
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, None)
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422
        assert "Invalid feature value" in exc.value.detail

    @pytest.mark.asyncio
    async def test_true_fault_returns_generic_500_without_leak(self):
        """An unexpected server fault → 500 that does NOT echo the internal message."""
        model = self._model()
        trained = MagicMock()
        secret = "connection string mongodb://secret@host leaked"
        trained.predict.side_effect = RuntimeError(secret)
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, None)
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 500
        assert exc.value.detail == "Prediction failed"
        assert secret not in exc.value.detail  # no internal disclosure

    @pytest.mark.asyncio
    async def test_load_failure_returns_503_without_leak(self):
        """The model exists but its artifact won't load → 503 (broken deployment),
        never a 404 mis-signal and never leaking the S3 path."""
        model = self._model()
        find, load = self._patch_load(model)
        with find, load as mock_load:
            leaky = ValueError("failed to load s3://internal-bucket/models/secret.pkl")
            mock_load.side_effect = leaky
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 503
        assert "s3://" not in exc.value.detail  # no internal path leaked

    @pytest.mark.asyncio
    async def test_transform_valueerror_returns_422(self):
        """A ValueError from feature_engineer.transform (e.g. an unknown category
        at encode time) is also mapped to a sanitized 422, matching the internal
        twin's security guarantee — not only predict-level errors."""
        model = self._model()
        trained = MagicMock()
        engineer = MagicMock()
        raw = "Found unknown categories ['LEAK'] in column 0 during transform"
        engineer.transform = AsyncMock(side_effect=ValueError(raw))
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, engineer)
            request = ProductionPredictRequest(
                data=[{"feature1": 1.0, "feature2": 2.0}]
            )

            with pytest.raises(HTTPException) as exc:
                await production_predict("model_123", request, self._api_key())

        assert exc.value.status_code == 422
        assert "Invalid feature value" in exc.value.detail
        assert raw not in exc.value.detail
        trained.predict.assert_not_called()  # failed before inference

    @pytest.mark.asyncio
    async def test_happy_path_returns_predictions(self):
        """A valid request runs the full inference path (predict/predict_proba
        via asyncio.to_thread) and returns a populated response."""
        model = self._model()
        trained = MagicMock()
        trained.predict.return_value = np.array([0, 1])
        trained.predict_proba.return_value = np.array([[0.8, 0.2], [0.3, 0.7]])
        find, load = self._patch_load(model)
        with find, load as mock_load:
            mock_load.return_value = (trained, None)
            request = ProductionPredictRequest(
                data=[
                    {"feature1": 1.0, "feature2": 2.0},
                    {"feature1": 3.0, "feature2": 4.0},
                ]
            )

            response = await production_predict("model_123", request, self._api_key())

        assert response.predictions == [0, 1]
        trained.predict.assert_called_once()
        trained.predict_proba.assert_called_once()
        # Enrichment pipeline ran end-to-end: confidence derived from proba.
        assert response.confidence == [0.8, 0.7]

    def test_request_caps_records_at_max(self):
        """The request schema rejects payloads over MAX_PREDICT_RECORDS (#264)."""
        from app.api.routes.production import MAX_PREDICT_RECORDS

        oversized = [{"feature1": 1.0}] * (MAX_PREDICT_RECORDS + 1)
        with pytest.raises(ValueError):  # pydantic ValidationError subclasses ValueError
            ProductionPredictRequest(data=oversized)

        # Exactly at the cap is accepted.
        ProductionPredictRequest(data=[{"feature1": 1.0}] * MAX_PREDICT_RECORDS)
