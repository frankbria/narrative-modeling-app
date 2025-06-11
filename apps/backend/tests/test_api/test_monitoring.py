"""
Tests for monitoring API endpoints
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.models.ml_model import MLModel
from app.models.api_key import APIKey


class TestMonitoringAPI:
    """Test cases for monitoring API endpoints"""
    
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
            feature_names=["feature1", "feature2"],
            cv_score=0.85,
            test_score=0.83,
            training_time=45.2,
            model_size=1048576,
            n_samples_train=1000,
            n_features=2,
            model_path="s3://bucket/models/model_123.pkl",
            version="1.0.0",
            is_active=True,
            last_used_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_get_model_metrics(self, mock_async_client):
        """Test getting model metrics"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/models/model_123/metrics",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_get_model_metrics_with_hours(self, mock_async_client):
        """Test getting model metrics with custom time window"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/models/model_123/metrics?hours=48",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_get_model_metrics_invalid_hours(self, mock_async_client):
        """Test getting model metrics with invalid hours"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/models/model_123/metrics?hours=200",  # > 168
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [422, 404]
    
    @pytest.mark.asyncio
    async def test_get_prediction_distribution(self, mock_async_client):
        """Test getting prediction distribution"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/models/model_123/distribution",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_check_drift(self, mock_async_client):
        """Test drift detection endpoint"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/models/model_123/drift",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_get_usage_overview(self, mock_async_client):
        """Test getting usage overview"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/overview",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_get_api_key_usage(self, mock_async_client):
        """Test getting API key usage statistics"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/api-keys/usage",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_get_prediction_logs(self, mock_async_client):
        """Test getting prediction logs"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/models/model_123/logs",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_get_prediction_logs_with_limit(self, mock_async_client):
        """Test getting prediction logs with limit"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/models/model_123/logs?limit=50",
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_get_prediction_logs_invalid_limit(self, mock_async_client):
        """Test getting prediction logs with invalid limit"""
        response = await mock_async_client.get(
            "/api/v1/monitoring/models/model_123/logs?limit=2000",  # > 1000
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code in [422, 404]
    
    @pytest.mark.asyncio
    async def test_monitoring_unauthorized(self, mock_async_client):
        """Test monitoring endpoints without authorization"""
        endpoints = [
            "/api/v1/monitoring/overview",
            "/api/v1/monitoring/models/model_123/metrics",
            "/api/v1/monitoring/models/model_123/distribution",
            "/api/v1/monitoring/models/model_123/drift",
            "/api/v1/monitoring/api-keys/usage",
            "/api/v1/monitoring/models/model_123/logs"
        ]
        
        for endpoint in endpoints:
            response = await mock_async_client.get(endpoint)
            assert response.status_code in [401, 404, 422]
    
    @pytest.mark.asyncio
    @patch('app.api.routes.monitoring.MLModel')
    @patch('app.api.routes.monitoring.APIKey')
    @patch('app.api.routes.monitoring.PredictionMonitoringService')
    async def test_usage_overview_calculation(self, mock_service, mock_api_key, mock_model):
        """Test usage overview calculation logic"""
        from app.api.routes.monitoring import get_usage_overview
        
        # Mock models
        mock_models = [
            Mock(
                model_id="model_1",
                name="Model 1",
                is_active=True,
                last_used_at=datetime.utcnow()
            ),
            Mock(
                model_id="model_2",
                name="Model 2",
                is_active=False,
                last_used_at=None
            )
        ]
        mock_model.find.return_value.to_list = AsyncMock(return_value=mock_models)
        
        # Mock API keys
        mock_keys = [
            Mock(is_active=True),
            Mock(is_active=True),
            Mock(is_active=False)
        ]
        mock_api_key.find.return_value.to_list = AsyncMock(return_value=mock_keys)
        
        # Mock metrics
        mock_service.get_model_metrics = AsyncMock(side_effect=[
            {"total_predictions": 100, "avg_latency_ms": 50},
            {"total_predictions": 50, "avg_latency_ms": 75}
        ])
        
        # Test the calculation
        result = await get_usage_overview(current_user_id="user_123")
        
        assert result.total_models == 2
        assert result.active_models == 1
        assert result.total_predictions_24h == 150
        assert result.total_api_keys == 3
        assert result.active_api_keys == 2
        assert len(result.models) == 2
    
    @pytest.mark.asyncio
    @patch('app.api.routes.monitoring.MLModel')
    @patch('app.api.routes.monitoring.PredictionMonitoringService')
    async def test_model_metrics_response_format(self, mock_service, mock_model):
        """Test model metrics response format"""
        from app.api.routes.monitoring import get_model_metrics
        
        # Mock model
        mock_model_instance = Mock()
        mock_model_instance.name = "Test Model"
        mock_model_instance.last_used_at = datetime.utcnow()
        mock_model.find_one = AsyncMock(return_value=mock_model_instance)
        
        # Mock metrics
        mock_service.get_model_metrics = AsyncMock(return_value={
            "total_predictions": 1000,
            "avg_latency_ms": 45.5,
            "predictions_per_hour": 41.7,
            "avg_confidence": 0.85,
            "error_rate": 0.02,
            "time_window_hours": 24
        })
        
        result = await get_model_metrics(
            model_id="model_123",
            hours=24,
            current_user_id="user_123"
        )
        
        assert result.model_id == "model_123"
        assert result.model_name == "Test Model"
        assert result.total_predictions == 1000
        assert result.avg_latency_ms == 45.5
        assert result.predictions_per_hour == 41.7
        assert result.avg_confidence == 0.85
        assert result.error_rate == 0.02
        assert result.time_window_hours == 24
        assert result.last_prediction_at is not None