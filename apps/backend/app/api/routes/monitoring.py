"""
Model monitoring and analytics API routes
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.ml_model import MLModel
from app.models.api_key import APIKey
from app.auth.nextauth_auth import get_current_user_id
from app.services.prediction_monitoring import PredictionMonitoringService
from beanie import PydanticObjectId


router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# Response Models
class ModelMetricsResponse(BaseModel):
    model_id: str
    model_name: str
    total_predictions: int
    avg_latency_ms: float
    predictions_per_hour: float
    avg_confidence: float
    error_rate: float
    time_window_hours: int
    last_prediction_at: Optional[datetime]


class PredictionDistributionResponse(BaseModel):
    model_id: str
    distribution: Dict[str, int]
    total: int
    unique_values: int
    most_common: Optional[str]
    least_common: Optional[str]


class DriftDetectionResponse(BaseModel):
    model_id: str
    drift_detected: bool
    drift_score: float
    features_with_drift: List[str]
    recommendation: str
    checked_at: datetime


class UsageStatsResponse(BaseModel):
    total_models: int
    active_models: int
    total_predictions_24h: int
    total_api_keys: int
    active_api_keys: int
    models: List[Dict[str, Any]]


class APIKeyUsageResponse(BaseModel):
    api_key_id: str
    name: str
    total_requests: int
    requests_last_24h: int
    rate_limit: int
    usage_percentage: float
    models_accessed: List[str]


# API Routes
@router.get("/models/{model_id}/metrics", response_model=ModelMetricsResponse)
async def get_model_metrics(
    model_id: str,
    hours: int = Query(default=24, ge=1, le=168, description="Time window in hours"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get performance metrics for a specific model"""
    
    # Verify model ownership
    model = await MLModel.find_one({
        "model_id": model_id,
        "user_id": current_user_id
    })
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get metrics from monitoring service
    metrics = await PredictionMonitoringService.get_model_metrics(model_id, hours)
    
    return ModelMetricsResponse(
        model_id=model_id,
        model_name=model.name,
        **metrics,
        last_prediction_at=model.last_used_at
    )


@router.get("/models/{model_id}/distribution", response_model=PredictionDistributionResponse)
async def get_prediction_distribution(
    model_id: str,
    hours: int = Query(default=24, ge=1, le=168, description="Time window in hours"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get distribution of predictions for a model"""
    
    # Verify model ownership
    model = await MLModel.find_one({
        "model_id": model_id,
        "user_id": current_user_id
    })
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get distribution
    dist_data = await PredictionMonitoringService.get_prediction_distribution(model_id, hours)
    
    # Find most and least common
    most_common = None
    least_common = None
    if dist_data["distribution"]:
        sorted_dist = sorted(dist_data["distribution"].items(), key=lambda x: x[1], reverse=True)
        most_common = sorted_dist[0][0]
        least_common = sorted_dist[-1][0]
    
    return PredictionDistributionResponse(
        model_id=model_id,
        **dist_data,
        most_common=most_common,
        least_common=least_common
    )


@router.get("/models/{model_id}/drift", response_model=DriftDetectionResponse)
async def check_drift(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Check for data drift in model inputs"""
    
    # Verify model ownership
    model = await MLModel.find_one({
        "model_id": model_id,
        "user_id": current_user_id
    })
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check drift (simplified version)
    drift_result = await PredictionMonitoringService.detect_drift(model_id, {})
    
    return DriftDetectionResponse(
        model_id=model_id,
        **drift_result,
        checked_at=datetime.utcnow()
    )


@router.get("/overview", response_model=UsageStatsResponse)
async def get_usage_overview(
    current_user_id: str = Depends(get_current_user_id)
):
    """Get overall usage statistics for all models"""
    
    # Get all user's models
    models = await MLModel.find({"user_id": current_user_id}).to_list()
    
    total_models = len(models)
    active_models = sum(1 for m in models if m.is_active)
    
    # Get API keys
    api_keys = await APIKey.find({"user_id": current_user_id}).to_list()
    total_api_keys = len(api_keys)
    active_api_keys = sum(1 for k in api_keys if k.is_active)
    
    # Get predictions for each model
    total_predictions_24h = 0
    model_summaries = []
    
    for model in models:
        metrics = await PredictionMonitoringService.get_model_metrics(model.model_id, 24)
        total_predictions_24h += metrics["total_predictions"]
        
        model_summaries.append({
            "model_id": model.model_id,
            "name": model.name,
            "is_active": model.is_active,
            "predictions_24h": metrics["total_predictions"],
            "avg_latency_ms": metrics["avg_latency_ms"],
            "last_used_at": model.last_used_at
        })
    
    # Sort by predictions
    model_summaries.sort(key=lambda x: x["predictions_24h"], reverse=True)
    
    return UsageStatsResponse(
        total_models=total_models,
        active_models=active_models,
        total_predictions_24h=total_predictions_24h,
        total_api_keys=total_api_keys,
        active_api_keys=active_api_keys,
        models=model_summaries
    )


@router.get("/api-keys/usage", response_model=List[APIKeyUsageResponse])
async def get_api_key_usage(
    current_user_id: str = Depends(get_current_user_id)
):
    """Get usage statistics for all API keys"""
    
    # Get all user's API keys
    api_keys = await APIKey.find({"user_id": current_user_id}).to_list()
    
    usage_stats = []
    
    for key in api_keys:
        # Get models this key has accessed
        models_accessed = set()
        requests_24h = 0
        
        # Get all models
        if not key.model_ids:  # Access to all models
            models = await MLModel.find({"user_id": current_user_id}).to_list()
            model_ids = [m.model_id for m in models]
        else:
            model_ids = key.model_ids
        
        # Count requests in last 24h for each model
        for model_id in model_ids:
            usage_by_key = await PredictionMonitoringService.get_usage_by_api_key(model_id, 24)
            if key.key_id in usage_by_key:
                requests_24h += usage_by_key[key.key_id]
                models_accessed.add(model_id)
        
        usage_percentage = (requests_24h / key.rate_limit * 100) if key.rate_limit > 0 else 0
        
        usage_stats.append(APIKeyUsageResponse(
            api_key_id=key.key_id,
            name=key.name,
            total_requests=key.total_requests,
            requests_last_24h=requests_24h,
            rate_limit=key.rate_limit,
            usage_percentage=round(usage_percentage, 2),
            models_accessed=list(models_accessed)
        ))
    
    # Sort by usage
    usage_stats.sort(key=lambda x: x.requests_last_24h, reverse=True)
    
    return usage_stats


@router.get("/models/{model_id}/logs")
async def get_prediction_logs(
    model_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get recent prediction logs for a model"""
    
    # Verify model ownership
    model = await MLModel.find_one({
        "model_id": model_id,
        "user_id": current_user_id
    })
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Get recent predictions
    from app.services.prediction_monitoring import prediction_log
    recent_preds = await prediction_log.get_recent_predictions(model_id, limit)
    
    # Format for response
    logs = []
    for pred in recent_preds:
        logs.append({
            "prediction_id": pred["prediction_id"],
            "timestamp": pred["timestamp"],
            "prediction": pred["prediction"],
            "probability": pred.get("probability"),
            "latency_ms": pred.get("latency_ms", 0),
            "api_key_id": pred.get("api_key_id")
        })
    
    return {
        "model_id": model_id,
        "logs": logs,
        "count": len(logs),
        "limit": limit
    }