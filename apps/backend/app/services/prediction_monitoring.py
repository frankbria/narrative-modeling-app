"""
Prediction monitoring and analytics service
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from beanie import PydanticObjectId
from app.models.ml_model import MLModel
import asyncio
import logging

logger = logging.getLogger(__name__)


class PredictionLog:
    """In-memory prediction log (would be in a time-series DB in production)"""
    def __init__(self):
        self.logs = defaultdict(list)
        self.lock = asyncio.Lock()
    
    async def log_prediction(
        self,
        model_id: str,
        prediction_id: str,
        input_data: Dict[str, Any],
        prediction: Any,
        probability: Optional[float] = None,
        latency_ms: float = 0,
        api_key_id: Optional[str] = None
    ):
        """Log a prediction event"""
        async with self.lock:
            self.logs[model_id].append({
                "prediction_id": prediction_id,
                "timestamp": datetime.utcnow(),
                "input_data": input_data,
                "prediction": prediction,
                "probability": probability,
                "latency_ms": latency_ms,
                "api_key_id": api_key_id
            })
            
            # Keep only last 10000 predictions per model
            if len(self.logs[model_id]) > 10000:
                self.logs[model_id] = self.logs[model_id][-10000:]
    
    async def get_recent_predictions(
        self,
        model_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
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
        input_data: Dict[str, Any],
        prediction: Any,
        probability: Optional[float] = None,
        latency_ms: float = 0,
        api_key_id: Optional[str] = None
    ) -> str:
        """Log a prediction for monitoring"""
        prediction_id = f"pred_{PydanticObjectId()}"
        
        # Log to in-memory store
        await prediction_log.log_prediction(
            model_id=model_id,
            prediction_id=prediction_id,
            input_data=input_data,
            prediction=prediction,
            probability=probability,
            latency_ms=latency_ms,
            api_key_id=api_key_id
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
    async def get_model_metrics(
        model_id: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get model performance metrics for the last N hours"""
        recent_preds = await prediction_log.get_recent_predictions(model_id, limit=10000)
        
        if not recent_preds:
            return {
                "total_predictions": 0,
                "avg_latency_ms": 0,
                "predictions_per_hour": 0,
                "avg_confidence": 0,
                "error_rate": 0
            }
        
        # Filter by time window
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        filtered_preds = [
            p for p in recent_preds 
            if p["timestamp"] > cutoff_time
        ]
        
        if not filtered_preds:
            return {
                "total_predictions": 0,
                "avg_latency_ms": 0,
                "predictions_per_hour": 0,
                "avg_confidence": 0,
                "error_rate": 0
            }
        
        # Calculate metrics
        total_predictions = len(filtered_preds)
        avg_latency = np.mean([p["latency_ms"] for p in filtered_preds])
        
        # Predictions per hour
        time_span_hours = (datetime.utcnow() - filtered_preds[0]["timestamp"]).total_seconds() / 3600
        predictions_per_hour = total_predictions / max(time_span_hours, 1)
        
        # Average confidence (for classification models)
        confidences = [p["probability"] for p in filtered_preds if p["probability"] is not None]
        avg_confidence = np.mean(confidences) if confidences else 0
        
        # Error rate (would need ground truth in production)
        error_rate = 0  # Placeholder
        
        return {
            "total_predictions": total_predictions,
            "avg_latency_ms": round(avg_latency, 2),
            "predictions_per_hour": round(predictions_per_hour, 2),
            "avg_confidence": round(avg_confidence, 4),
            "error_rate": error_rate,
            "time_window_hours": hours
        }
    
    @staticmethod
    async def get_prediction_distribution(
        model_id: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get distribution of predictions"""
        recent_preds = await prediction_log.get_recent_predictions(model_id, limit=10000)
        
        if not recent_preds:
            return {"distribution": {}, "total": 0}
        
        # Filter by time window
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        filtered_preds = [
            p for p in recent_preds 
            if p["timestamp"] > cutoff_time
        ]
        
        # Count predictions by value
        distribution = defaultdict(int)
        for pred in filtered_preds:
            pred_value = str(pred["prediction"])
            distribution[pred_value] += 1
        
        return {
            "distribution": dict(distribution),
            "total": len(filtered_preds),
            "unique_values": len(distribution)
        }
    
    @staticmethod
    async def detect_drift(
        model_id: str,
        feature_stats: Dict[str, Dict[str, float]]
    ) -> Dict[str, Any]:
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
    ) -> Dict[str, int]:
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
        usage = defaultdict(int)
        for pred in filtered_preds:
            api_key = pred.get("api_key_id", "unknown")
            usage[api_key] += 1
        
        return dict(usage)