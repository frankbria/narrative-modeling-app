"""
Tests for prediction monitoring service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import numpy as np

from app.services.prediction_monitoring import (
    PredictionLog,
    PredictionMonitoringService,
    prediction_log
)


class TestPredictionLog:
    """Test cases for PredictionLog class"""
    
    @pytest.mark.asyncio
    async def test_log_prediction(self):
        """Test logging a prediction"""
        log = PredictionLog()
        
        await log.log_prediction(
            model_id="model_123",
            prediction_id="pred_123",
            input_data={"feature1": 1, "feature2": "value"},
            prediction="class_a",
            probability=0.85,
            latency_ms=45.5,
            api_key_id="key_123"
        )
        
        # Check prediction was logged
        assert "model_123" in log.logs
        assert len(log.logs["model_123"]) == 1
        
        # Check logged data
        logged = log.logs["model_123"][0]
        assert logged["prediction_id"] == "pred_123"
        assert logged["prediction"] == "class_a"
        assert logged["probability"] == 0.85
        assert logged["latency_ms"] == 45.5
        assert logged["api_key_id"] == "key_123"
        assert isinstance(logged["timestamp"], datetime)
    
    @pytest.mark.asyncio
    async def test_log_multiple_predictions(self):
        """Test logging multiple predictions"""
        log = PredictionLog()
        
        # Log multiple predictions
        for i in range(5):
            await log.log_prediction(
                model_id="model_123",
                prediction_id=f"pred_{i}",
                input_data={"value": i},
                prediction=i,
                latency_ms=10.0 + i
            )
        
        assert len(log.logs["model_123"]) == 5
    
    @pytest.mark.asyncio
    async def test_log_size_limit(self):
        """Test that log size is limited to 10000 entries"""
        log = PredictionLog()
        
        # Log more than 10000 predictions
        for i in range(10005):
            await log.log_prediction(
                model_id="model_123",
                prediction_id=f"pred_{i}",
                input_data={"value": i},
                prediction=i
            )
        
        # Should only keep last 10000
        assert len(log.logs["model_123"]) == 10000
        
        # First prediction should be pred_5
        assert log.logs["model_123"][0]["prediction_id"] == "pred_5"
    
    @pytest.mark.asyncio
    async def test_get_recent_predictions(self):
        """Test getting recent predictions"""
        log = PredictionLog()
        
        # Log 20 predictions
        for i in range(20):
            await log.log_prediction(
                model_id="model_123",
                prediction_id=f"pred_{i}",
                input_data={"value": i},
                prediction=i
            )
        
        # Get last 10
        recent = await log.get_recent_predictions("model_123", limit=10)
        assert len(recent) == 10
        assert recent[0]["prediction_id"] == "pred_10"
        assert recent[-1]["prediction_id"] == "pred_19"
        
        # Get all
        all_preds = await log.get_recent_predictions("model_123", limit=100)
        assert len(all_preds) == 20


class TestPredictionMonitoringService:
    """Test cases for PredictionMonitoringService"""
    
    @pytest.mark.asyncio
    @patch('app.services.prediction_monitoring.MLModel')
    async def test_log_prediction_updates_model(self, mock_model_class):
        """Test that logging prediction updates model last_used_at"""
        # Mock model
        mock_model = AsyncMock()
        mock_model.save = AsyncMock()
        mock_model_class.find_one = AsyncMock(return_value=mock_model)
        
        # Log prediction
        pred_id = await PredictionMonitoringService.log_prediction(
            model_id="model_123",
            input_data={"test": 1},
            prediction="result",
            probability=0.9,
            latency_ms=50.0,
            api_key_id="key_123"
        )
        
        # Check prediction ID format
        assert pred_id.startswith("pred_")
        
        # Check model was updated
        mock_model_class.find_one.assert_called_once()
        assert mock_model.last_used_at is not None
        mock_model.save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_model_metrics_no_data(self):
        """Test getting metrics with no prediction data"""
        # Clear any existing logs
        prediction_log.logs.clear()
        
        metrics = await PredictionMonitoringService.get_model_metrics("model_999", 24)
        
        assert metrics["total_predictions"] == 0
        assert metrics["avg_latency_ms"] == 0
        assert metrics["predictions_per_hour"] == 0
        assert metrics["avg_confidence"] == 0
        assert metrics["error_rate"] == 0
    
    @pytest.mark.asyncio
    async def test_get_model_metrics_with_data(self):
        """Test getting metrics with prediction data"""
        # Clear logs and add test data
        prediction_log.logs.clear()
        
        # Add predictions from last hour
        now = datetime.utcnow()
        for i in range(10):
            await prediction_log.log_prediction(
                model_id="model_123",
                prediction_id=f"pred_{i}",
                input_data={"test": i},
                prediction="class_a",
                probability=0.8 + (i * 0.01),  # 0.8 to 0.89
                latency_ms=40 + i * 2,  # 40 to 58
                api_key_id="key_123"
            )
        
        metrics = await PredictionMonitoringService.get_model_metrics("model_123", 24)
        
        assert metrics["total_predictions"] == 10
        assert metrics["avg_latency_ms"] == 49.0  # Average of 40-58
        assert metrics["predictions_per_hour"] > 0
        assert 0.84 <= metrics["avg_confidence"] <= 0.85  # Average of 0.8-0.89
        assert metrics["time_window_hours"] == 24
    
    @pytest.mark.asyncio
    async def test_get_model_metrics_time_window(self):
        """Test metrics respect time window"""
        prediction_log.logs.clear()
        
        # Add old prediction (25 hours ago)
        old_time = datetime.utcnow() - timedelta(hours=25)
        prediction_log.logs["model_123"] = [{
            "prediction_id": "old_pred",
            "timestamp": old_time,
            "input_data": {},
            "prediction": "old",
            "latency_ms": 100
        }]
        
        # Add recent prediction
        await prediction_log.log_prediction(
            model_id="model_123",
            prediction_id="new_pred",
            input_data={},
            prediction="new",
            latency_ms=50
        )
        
        # 24 hour window should only include recent
        metrics = await PredictionMonitoringService.get_model_metrics("model_123", 24)
        assert metrics["total_predictions"] == 1
        assert metrics["avg_latency_ms"] == 50.0
    
    @pytest.mark.asyncio
    async def test_get_prediction_distribution(self):
        """Test getting prediction distribution"""
        prediction_log.logs.clear()
        
        # Add predictions with different values
        predictions = ["class_a"] * 5 + ["class_b"] * 3 + ["class_c"] * 2
        for i, pred in enumerate(predictions):
            await prediction_log.log_prediction(
                model_id="model_123",
                prediction_id=f"pred_{i}",
                input_data={},
                prediction=pred
            )
        
        dist = await PredictionMonitoringService.get_prediction_distribution("model_123", 24)
        
        assert dist["total"] == 10
        assert dist["unique_values"] == 3
        assert dist["distribution"]["class_a"] == 5
        assert dist["distribution"]["class_b"] == 3
        assert dist["distribution"]["class_c"] == 2
    
    @pytest.mark.asyncio
    @patch('app.services.prediction_monitoring.MLModel')
    async def test_detect_drift(self, mock_model_class):
        """Test drift detection (placeholder)"""
        # Mock model
        mock_model = Mock()
        mock_model_class.find_one = AsyncMock(return_value=mock_model)
        
        result = await PredictionMonitoringService.detect_drift("model_123", {})
        
        assert result["drift_detected"] is False
        assert result["drift_score"] == 0.0
        assert result["features_with_drift"] == []
        assert "recommendation" in result
    
    @pytest.mark.asyncio
    async def test_get_usage_by_api_key(self):
        """Test getting usage grouped by API key"""
        prediction_log.logs.clear()
        
        # Add predictions with different API keys
        api_keys = ["key_1", "key_1", "key_1", "key_2", "key_2", None]
        for i, key in enumerate(api_keys):
            await prediction_log.log_prediction(
                model_id="model_123",
                prediction_id=f"pred_{i}",
                input_data={},
                prediction="result",
                api_key_id=key
            )
        
        usage = await PredictionMonitoringService.get_usage_by_api_key("model_123", 24)
        
        assert usage["key_1"] == 3
        assert usage["key_2"] == 2
        assert usage.get("unknown", 0) == 1 or usage.get(None, 0) == 1  # None handling may vary
    
    @pytest.mark.asyncio
    async def test_concurrent_logging(self):
        """Test concurrent prediction logging"""
        prediction_log.logs.clear()
        
        # Simulate concurrent logging
        import asyncio
        
        async def log_pred(i):
            await prediction_log.log_prediction(
                model_id="model_123",
                prediction_id=f"pred_{i}",
                input_data={"i": i},
                prediction=i
            )
        
        # Log 50 predictions concurrently
        await asyncio.gather(*[log_pred(i) for i in range(50)])
        
        # All should be logged
        assert len(prediction_log.logs["model_123"]) == 50