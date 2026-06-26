"""
Prediction monitoring and analytics service
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from beanie import PydanticObjectId

from app.models.ml_model import MLModel

logger = logging.getLogger(__name__)

# Health/alert thresholds (issue #85). Error-rate alerts are threshold-based; an
# alert-rule CRUD subsystem is deliberately out of scope for beta.
DEGRADED_ERROR_RATE = 0.05
UNHEALTHY_ERROR_RATE = 0.20
DEGRADED_LATENCY_MS = 1000.0
UNHEALTHY_LATENCY_MS = 5000.0


class PredictionLog:
    """In-memory prediction log.

    ponytail: in-memory, process-local — metrics reset on restart. Beta relies on
    basic logging (issue #85 header). Upgrade path: swap for a Beanie time-series
    collection behind this same interface if cross-restart durability is needed.
    """
    def __init__(self):
        self.logs = defaultdict(list)
        self.lock = asyncio.Lock()

    async def log_prediction(
        self,
        model_id: str,
        prediction_id: str,
        input_data: dict[str, Any],
        prediction: Any,
        probability: float | None = None,
        latency_ms: float = 0,
        api_key_id: str | None = None,
        error: str | None = None,
    ):
        """Log a prediction (or, when ``error`` is set, a failed-request) event"""
        async with self.lock:
            self.logs[model_id].append({
                "prediction_id": prediction_id,
                "timestamp": datetime.utcnow(),
                "input_data": input_data,
                "prediction": prediction,
                "probability": probability,
                "latency_ms": latency_ms,
                "api_key_id": api_key_id,
                "error": error,
            })
            
            # Keep only last 10000 predictions per model
            if len(self.logs[model_id]) > 10000:
                self.logs[model_id] = self.logs[model_id][-10000:]
    
    async def get_recent_predictions(
        self,
        model_id: str,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get recent predictions for a model"""
        async with self.lock:
            return self.logs[model_id][-limit:]


# Global prediction log instance
prediction_log = PredictionLog()


class PredictionMonitoringService:
    """Service for monitoring model predictions and performance"""
    
    @staticmethod
    async def log_prediction(
        model_id: str,
        input_data: dict[str, Any],
        prediction: Any,
        probability: float | None = None,
        latency_ms: float = 0,
        api_key_id: str | None = None,
        error: str | None = None,
    ) -> str:
        """Log a prediction (or failed-request, when ``error`` is set) for monitoring"""
        prediction_id = f"pred_{PydanticObjectId()}"

        # Log to in-memory store
        await prediction_log.log_prediction(
            model_id=model_id,
            prediction_id=prediction_id,
            input_data=input_data,
            prediction=prediction,
            probability=probability,
            latency_ms=latency_ms,
            api_key_id=api_key_id,
            error=error,
        )
        
        # Update model last used timestamp
        try:
            model = await MLModel.find_one({"model_id": model_id})
            if model:
                model.last_used_at = datetime.utcnow()
                await model.save()
        except Exception as e:
            logger.error(f"Failed to update model last_used_at: {e}")
        
        return prediction_id
    
    @staticmethod
    async def _window(model_id: str, hours: int) -> list[dict[str, Any]]:
        """Return all logged events for a model within the last ``hours``."""
        recent = await prediction_log.get_recent_predictions(model_id, limit=10000)
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [p for p in recent if p["timestamp"] > cutoff]

    @staticmethod
    async def get_model_metrics(
        model_id: str,
        hours: int = 24
    ) -> dict[str, Any]:
        """Get model performance metrics for the last N hours.

        ``total_predictions`` counts successful predictions; ``error_rate`` is
        errors / total requests (issue #85 — errors are now logged from the
        production serving path). Latency percentiles are over successful requests.
        """
        empty = {
            "total_predictions": 0,
            "error_count": 0,
            "avg_latency_ms": 0,
            "latency_percentiles": {"p50": 0, "p90": 0, "p95": 0, "p99": 0},
            "predictions_per_hour": 0,
            "avg_confidence": 0,
            "error_rate": 0,
            "time_window_hours": hours,
        }

        filtered = await PredictionMonitoringService._window(model_id, hours)
        if not filtered:
            return empty

        successes = [p for p in filtered if not p.get("error")]
        error_count = len(filtered) - len(successes)
        total_requests = len(filtered)
        error_rate = error_count / total_requests if total_requests else 0

        if not successes:
            return {**empty, "error_count": error_count, "error_rate": round(error_rate, 4)}

        latencies = [p["latency_ms"] for p in successes]
        avg_latency = float(np.mean(latencies))
        p50, p90, p95, p99 = (
            float(v) for v in np.percentile(latencies, [50, 90, 95, 99])
        )

        time_span_hours = (
            datetime.utcnow() - successes[0]["timestamp"]
        ).total_seconds() / 3600
        predictions_per_hour = len(successes) / max(time_span_hours, 1)

        confidences = [p["probability"] for p in successes if p["probability"] is not None]
        avg_confidence = float(np.mean(confidences)) if confidences else 0

        return {
            "total_predictions": len(successes),
            "error_count": error_count,
            "avg_latency_ms": round(avg_latency, 2),
            "latency_percentiles": {
                "p50": round(p50, 2),
                "p90": round(p90, 2),
                "p95": round(p95, 2),
                "p99": round(p99, 2),
            },
            "predictions_per_hour": round(predictions_per_hour, 2),
            "avg_confidence": round(avg_confidence, 4),
            "error_rate": round(error_rate, 4),
            "time_window_hours": hours,
        }

    @staticmethod
    async def get_usage_timeline(
        model_id: str,
        hours: int = 24,
        bucket_minutes: int | None = None,
    ) -> dict[str, Any]:
        """Bucketed request/error/latency counts over time, for charts.

        Empty buckets are included so the chart spans the whole window.
        """
        if bucket_minutes is None:
            # Sensible default granularity scaled to the window (~24-48 buckets).
            bucket_minutes = 15 if hours <= 6 else 60 if hours <= 48 else 360
        bucket_minutes = max(1, bucket_minutes)

        now = datetime.utcnow()
        window_start = now - timedelta(hours=hours)
        bucket = timedelta(minutes=bucket_minutes)
        n_buckets = max(1, int((hours * 60) // bucket_minutes) + 1)

        # Pre-seed empty buckets keyed by bucket index.
        buckets: list[dict[str, Any]] = []
        for i in range(n_buckets):
            start = window_start + bucket * i
            buckets.append({
                "timestamp": start.isoformat(),
                "requests": 0,
                "errors": 0,
                "_latencies": [],
            })

        for p in await PredictionMonitoringService._window(model_id, hours):
            idx = int((p["timestamp"] - window_start).total_seconds() // (bucket_minutes * 60))
            if idx < 0 or idx >= n_buckets:
                continue
            b = buckets[idx]
            b["requests"] += 1
            if p.get("error"):
                b["errors"] += 1
            else:
                b["_latencies"].append(p["latency_ms"])

        for b in buckets:
            lats = b.pop("_latencies")
            b["avg_latency_ms"] = round(float(np.mean(lats)), 2) if lats else 0

        return {
            "bucket_minutes": bucket_minutes,
            "time_window_hours": hours,
            "buckets": buckets,
        }

    @staticmethod
    async def get_health(model_id: str, hours: int = 24) -> dict[str, Any]:
        """Deployment health status + threshold-based error-rate/latency alerts."""
        filtered = await PredictionMonitoringService._window(model_id, hours)
        metrics = await PredictionMonitoringService.get_model_metrics(model_id, hours)

        last_request_at = (
            max(p["timestamp"] for p in filtered).isoformat() if filtered else None
        )

        error_rate = metrics["error_rate"]
        avg_latency = metrics["avg_latency_ms"]

        alerts: list[dict[str, str]] = []
        if error_rate >= UNHEALTHY_ERROR_RATE:
            alerts.append({
                "level": "critical",
                "type": "error_rate",
                "message": f"Error rate {error_rate:.1%} exceeds {UNHEALTHY_ERROR_RATE:.0%}",
            })
        elif error_rate >= DEGRADED_ERROR_RATE:
            alerts.append({
                "level": "warning",
                "type": "error_rate",
                "message": f"Error rate {error_rate:.1%} exceeds {DEGRADED_ERROR_RATE:.0%}",
            })

        if avg_latency >= UNHEALTHY_LATENCY_MS:
            alerts.append({
                "level": "critical",
                "type": "latency",
                "message": f"Avg latency {avg_latency:.0f}ms exceeds {UNHEALTHY_LATENCY_MS:.0f}ms",
            })
        elif avg_latency >= DEGRADED_LATENCY_MS:
            alerts.append({
                "level": "warning",
                "type": "latency",
                "message": f"Avg latency {avg_latency:.0f}ms exceeds {DEGRADED_LATENCY_MS:.0f}ms",
            })

        if not filtered:
            status = "unknown"
        elif any(a["level"] == "critical" for a in alerts):
            status = "unhealthy"
        elif alerts:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "error_rate": error_rate,
            "avg_latency_ms": avg_latency,
            "requests": len(filtered),
            "last_request_at": last_request_at,
            "alerts": alerts,
            "time_window_hours": hours,
        }
    
    @staticmethod
    async def get_prediction_distribution(
        model_id: str,
        hours: int = 24
    ) -> dict[str, Any]:
        """Get distribution of predictions"""
        recent_preds = await prediction_log.get_recent_predictions(model_id, limit=10000)
        
        if not recent_preds:
            return {"distribution": {}, "total": 0, "unique_values": 0}

        # Filter by time window
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        filtered_preds = [
            p for p in recent_preds
            if p["timestamp"] > cutoff_time
        ]

        # Count predictions by value (skip failed-request markers)
        distribution: defaultdict[str, int] = defaultdict(int)
        for pred in filtered_preds:
            if pred.get("error"):
                continue
            pred_value = str(pred["prediction"])
            distribution[pred_value] += 1

        return {
            "distribution": dict(distribution),
            "total": sum(distribution.values()),
            "unique_values": len(distribution)
        }
    
    @staticmethod
    async def detect_drift(
        model_id: str,
        feature_stats: dict[str, dict[str, float]]
    ) -> dict[str, Any]:
        """Detect data drift by comparing current feature stats with training stats"""
        # This is a simplified version - production would use statistical tests
        model = await MLModel.find_one({"model_id": model_id})
        if not model:
            return {"drift_detected": False, "message": "Model not found"}
        
        # In production, we'd compare with stored training statistics
        # For now, return a placeholder
        return {
            "drift_detected": False,
            "drift_score": 0.0,
            "features_with_drift": [],
            "recommendation": "No significant drift detected"
        }
    
    @staticmethod
    async def get_usage_by_api_key(
        model_id: str,
        hours: int = 24
    ) -> dict[str, int]:
        """Get prediction usage grouped by API key"""
        recent_preds = await prediction_log.get_recent_predictions(model_id, limit=10000)
        
        if not recent_preds:
            return {}
        
        # Filter by time window
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        filtered_preds = [
            p for p in recent_preds 
            if p["timestamp"] > cutoff_time
        ]
        
        # Count by API key
        usage: defaultdict[str, int] = defaultdict(int)
        for pred in filtered_preds:
            api_key = pred.get("api_key_id", "unknown")
            usage[api_key] += 1
        
        return dict(usage)