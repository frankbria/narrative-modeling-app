"""
Tests for prediction monitoring service
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.services.prediction_monitoring import (
    PredictionLog,
    PredictionMonitoringService,
    prediction_log,
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
    async def test_detect_drift_insufficient_data_is_honest(self):
        """Below the minimum sample count, drift is reported as NOT assessed (#274)."""
        prediction_log.logs.clear()
        for i in range(5):  # < DRIFT_MIN_TOTAL
            await prediction_log.log_prediction(
                model_id="drift_model",
                prediction_id=f"pred_{i}",
                input_data={"x": float(i)},
                prediction="a",
            )

        result = await PredictionMonitoringService.detect_drift("drift_model")

        assert result["assessed"] is False
        assert result["reason"] == "insufficient_data"
        assert result["sample_size"] == 5
        assert result["drift_detected"] is False
        assert "insufficient" in result["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_detect_drift_flags_shifted_feature(self):
        """A feature whose distribution shifts across the window is flagged (#274)."""
        prediction_log.logs.clear()
        # Older half: x ~ 0; recent half: x ~ 100 → large standardized shift.
        for i in range(15):
            await prediction_log.log_prediction(
                model_id="drift_model", prediction_id=f"old_{i}",
                input_data={"x": float(i % 3)}, prediction="a",
            )
        for i in range(15):
            await prediction_log.log_prediction(
                model_id="drift_model", prediction_id=f"new_{i}",
                input_data={"x": 100.0 + (i % 3)}, prediction="a",
            )

        result = await PredictionMonitoringService.detect_drift("drift_model")

        assert result["assessed"] is True
        assert result["drift_detected"] is True
        assert "x" in result["features_with_drift"]
        assert result["drift_score"] > 0

    @pytest.mark.asyncio
    async def test_detect_drift_stable_feature_not_flagged(self):
        """A stable feature distribution is not flagged as drift (#274)."""
        prediction_log.logs.clear()
        for i in range(40):
            await prediction_log.log_prediction(
                model_id="drift_model", prediction_id=f"pred_{i}",
                input_data={"x": float(i % 5)}, prediction="a",
            )

        result = await PredictionMonitoringService.detect_drift("drift_model")

        assert result["assessed"] is True
        assert result["reason"] == "assessed"
        assert result["drift_detected"] is False
        assert result["features_with_drift"] == []

    @pytest.mark.asyncio
    async def test_detect_drift_tolerates_sparse_feature(self):
        """A feature with occasional None/non-numeric values is still scored —
        bad values are dropped individually, not the whole feature (review #328)."""
        prediction_log.logs.clear()
        # Every 4th record has a missing/non-numeric x, but each window still has
        # well over DRIFT_MIN_FEATURE_SAMPLES numeric values, and x shifts.
        for i in range(16):
            x = None if i % 4 == 0 else float(i % 3)
            await prediction_log.log_prediction(
                model_id="drift_model", prediction_id=f"old_{i}",
                input_data={"x": x}, prediction="a",
            )
        for i in range(16):
            x = None if i % 4 == 0 else 100.0 + (i % 3)
            await prediction_log.log_prediction(
                model_id="drift_model", prediction_id=f"new_{i}",
                input_data={"x": x}, prediction="a",
            )

        result = await PredictionMonitoringService.detect_drift("drift_model")

        assert result["assessed"] is True
        assert result["reason"] == "assessed"
        assert "x" in result["features_with_drift"]

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
    async def test_metrics_error_rate_and_percentiles(self):
        """error_rate counts errors / total; percentiles over successes (issue #85)"""
        prediction_log.logs.clear()

        # 8 successes with latencies 10..80, 2 errors.
        for i in range(8):
            await prediction_log.log_prediction(
                model_id="model_e",
                prediction_id=f"ok_{i}",
                input_data={},
                prediction="class_a",
                latency_ms=(i + 1) * 10,
            )
        for i in range(2):
            await prediction_log.log_prediction(
                model_id="model_e",
                prediction_id=f"err_{i}",
                input_data={},
                prediction=None,
                latency_ms=5,
                error="boom",
            )

        metrics = await PredictionMonitoringService.get_model_metrics("model_e", 24)

        assert metrics["total_predictions"] == 8  # successes only
        assert metrics["error_count"] == 2
        assert metrics["error_rate"] == 0.2  # 2 / 10
        # Error latency (5ms) must not pollute success percentiles.
        assert metrics["latency_percentiles"]["p50"] == 45.0
        assert metrics["latency_percentiles"]["p99"] >= metrics["latency_percentiles"]["p50"]

    @pytest.mark.asyncio
    async def test_metrics_all_errors(self):
        """All-error window: error_rate 1.0, no successful latency stats"""
        prediction_log.logs.clear()
        for i in range(3):
            await prediction_log.log_prediction(
                model_id="model_ae",
                prediction_id=f"err_{i}",
                input_data={},
                prediction=None,
                error="boom",
            )

        metrics = await PredictionMonitoringService.get_model_metrics("model_ae", 24)
        assert metrics["total_predictions"] == 0
        assert metrics["error_count"] == 3
        assert metrics["error_rate"] == 1.0
        assert metrics["avg_latency_ms"] == 0

    @pytest.mark.asyncio
    async def test_distribution_excludes_errors(self):
        """Failed-request markers are excluded from the value distribution"""
        prediction_log.logs.clear()
        for i in range(4):
            await prediction_log.log_prediction(
                model_id="model_d", prediction_id=f"ok_{i}",
                input_data={}, prediction="class_a",
            )
        await prediction_log.log_prediction(
            model_id="model_d", prediction_id="err",
            input_data={}, prediction=None, error="boom",
        )

        dist = await PredictionMonitoringService.get_prediction_distribution("model_d", 24)
        assert dist["total"] == 4
        assert dist["distribution"] == {"class_a": 4}
        assert "None" not in dist["distribution"]

    @pytest.mark.asyncio
    async def test_usage_timeline_buckets(self):
        """Timeline returns bucketed requests/errors/latency spanning the window"""
        prediction_log.logs.clear()
        for i in range(5):
            await prediction_log.log_prediction(
                model_id="model_t", prediction_id=f"ok_{i}",
                input_data={}, prediction="a", latency_ms=20,
            )
        await prediction_log.log_prediction(
            model_id="model_t", prediction_id="err",
            input_data={}, prediction=None, error="boom",
        )

        timeline = await PredictionMonitoringService.get_usage_timeline(
            "model_t", hours=24, bucket_minutes=60
        )
        assert timeline["bucket_minutes"] == 60
        assert len(timeline["buckets"]) >= 1
        # All events fall within the window, in the most-recent bucket(s).
        assert sum(b["requests"] for b in timeline["buckets"]) == 6
        assert sum(b["errors"] for b in timeline["buckets"]) == 1
        recent = [b for b in timeline["buckets"] if b["requests"] > 0][-1]
        assert recent["avg_latency_ms"] == 20.0
        # Buckets carry ISO timestamps for charting.
        assert all(isinstance(b["timestamp"], str) for b in timeline["buckets"])

    @pytest.mark.asyncio
    async def test_health_healthy(self):
        """Low error/latency → healthy, no alerts"""
        prediction_log.logs.clear()
        for i in range(20):
            await prediction_log.log_prediction(
                model_id="model_h", prediction_id=f"ok_{i}",
                input_data={}, prediction="a", latency_ms=30,
            )
        health = await PredictionMonitoringService.get_health("model_h", 24)
        assert health["status"] == "healthy"
        assert health["alerts"] == []
        assert health["last_request_at"] is not None

    @pytest.mark.asyncio
    async def test_health_unhealthy_error_alert(self):
        """High error rate → unhealthy with a critical error_rate alert"""
        prediction_log.logs.clear()
        for i in range(5):
            await prediction_log.log_prediction(
                model_id="model_u", prediction_id=f"ok_{i}",
                input_data={}, prediction="a", latency_ms=30,
            )
        for i in range(5):
            await prediction_log.log_prediction(
                model_id="model_u", prediction_id=f"err_{i}",
                input_data={}, prediction=None, error="boom",
            )
        health = await PredictionMonitoringService.get_health("model_u", 24)
        assert health["status"] == "unhealthy"
        assert any(a["type"] == "error_rate" and a["level"] == "critical"
                   for a in health["alerts"])

    @pytest.mark.asyncio
    async def test_health_no_data_unknown(self):
        """No requests → unknown status, no alerts"""
        prediction_log.logs.clear()
        health = await PredictionMonitoringService.get_health("model_none", 24)
        assert health["status"] == "unknown"
        assert health["requests"] == 0
        assert health["last_request_at"] is None

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