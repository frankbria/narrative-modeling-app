"""
Production model serving API routes
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.auth.nextauth_auth import get_current_user_id
from app.models.api_key import APIKey
from app.models.ml_model import MLModel
from app.schemas.model import PredictionExplanation
from app.services.confidence_service import DEFAULT_LOW_CONFIDENCE_THRESHOLD
from app.services.model_storage import ModelStorageService
from app.services.prediction_enrichment import PredictionEnricher
from app.services.prediction_monitoring import prediction_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/production", tags=["production"])

# Stateless — reuse one instance instead of constructing it per request (#83).
_prediction_enricher = PredictionEnricher()


async def _record_serving_metrics(
    model_id: str,
    request_data: list[dict[str, Any]],
    predictions: list[Any],
    confidence: list[float] | None,
    latency_ms: float,
    api_key_id: str | None,
    error: str | None = None,
) -> None:
    """Best-effort per-request monitoring logging (issue #85).

    Logged to the in-memory prediction log only — never touches the DB on the hot
    path and never raises, so monitoring can't break or slow real predictions.
    """
    try:
        if error is not None:
            # Log one error entry per input record so error rate stays per-record
            # consistent with successes — otherwise a failed N-record batch would
            # under-report error rate vs an N-record success (codex review).
            n = len(request_data) or 1
            for i in range(n):
                await prediction_log.log_prediction(
                    model_id=model_id,
                    prediction_id=f"pred_{PydanticObjectId()}",
                    input_data=request_data[i] if i < len(request_data) else {},
                    prediction=None,
                    latency_ms=latency_ms / n,
                    api_key_id=api_key_id,
                    error=error,
                )
            return

        per_record_latency = latency_ms / (len(predictions) or 1)
        for i, pred in enumerate(predictions):
            await prediction_log.log_prediction(
                model_id=model_id,
                prediction_id=f"pred_{PydanticObjectId()}",
                input_data=request_data[i] if i < len(request_data) else {},
                prediction=pred,
                probability=(
                    confidence[i] if confidence and i < len(confidence) else None
                ),
                latency_ms=per_record_latency,
                api_key_id=api_key_id,
            )
    except Exception:  # noqa: BLE001 - monitoring must never break serving
        logger.exception("Failed to record serving metrics for model %s", model_id)

# Rate limiting is enforced globally by RateLimitMiddleware over every /api/v1 route
# (issue #151), including this endpoint, using the per-key APIKey.rate_limit budget.
# The previous in-route sync-Redis check was removed as redundant.


# Request/Response Models
class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., description="Friendly name for the API key")
    description: str | None = Field(None, description="Description of key usage")
    model_ids: list[str] | None = Field(
        None, description="Specific model IDs to allow"
    )
    rate_limit: int = Field(default=1000, description="Requests per hour")
    expires_in_days: int | None = Field(None, description="Days until expiration")


class APIKeyResponse(BaseModel):
    key_id: str
    api_key: str
    name: str
    created_at: datetime
    expires_at: datetime | None
    rate_limit: int
    model_ids: list[str]


class ProductionPredictRequest(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="Input data for prediction")
    include_metadata: bool = Field(default=False, description="Include model metadata")
    include_probabilities: bool = Field(
        default=True, description="Include probabilities for classification"
    )
    include_explanations: bool = Field(
        default=False,
        description="Include per-prediction feature contributions (issue #83)",
    )


class ProductionPredictResponse(BaseModel):
    predictions: list[Any]
    probabilities: list[list[float]] | None = None
    model_version: str
    prediction_id: str
    timestamp: datetime
    metadata: dict[str, Any] | None = None
    # Confidence & explainability enrichment (issue #83), all optional.
    confidence: list[float] | None = None
    low_confidence: list[bool] | None = None
    is_calibrated: bool = False
    calibration_method: str | None = None
    confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD
    prediction_intervals: list[list[float] | None] | None = None
    explanations: list[PredictionExplanation | None] | None = None


class APIKeyListResponse(BaseModel):
    key_id: str
    name: str
    description: str | None
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    total_requests: int
    rate_limit: int
    is_active: bool


# Helper functions
def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage (delegates to the model's shared scheme)."""
    return APIKey.hash_key(api_key)


async def verify_api_key(api_key: str = Header(..., alias="X-API-Key")) -> APIKey:
    """Verify and return the API key document"""
    if not api_key or not api_key.startswith("sk_live_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    # Hash the key and look it up
    key_hash = hash_api_key(api_key)
    api_key_doc = await APIKey.find_one({"key_hash": key_hash})

    if not api_key_doc:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not api_key_doc.is_valid():
        raise HTTPException(status_code=401, detail="API key expired or inactive")

    # Update last used timestamp
    api_key_doc.last_used_at = datetime.utcnow()
    api_key_doc.total_requests += 1
    await api_key_doc.save()

    return api_key_doc


# API Routes
@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest, current_user_id: str = Depends(get_current_user_id)
):
    """Create a new API key for production model serving"""

    # Generate the key
    api_key_plain = APIKey.generate_key()
    key_hash = hash_api_key(api_key_plain)

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    # Create the document
    api_key_doc = APIKey(
        key_id=f"key_{PydanticObjectId()}",
        key_hash=key_hash,
        name=request.name,
        description=request.description,
        user_id=current_user_id,
        model_ids=request.model_ids or [],
        rate_limit=request.rate_limit,
        expires_at=expires_at,
    )

    await api_key_doc.create()

    # Return the key only once
    return APIKeyResponse(
        key_id=api_key_doc.key_id,
        api_key=api_key_plain,  # Only returned on creation
        name=api_key_doc.name,
        created_at=api_key_doc.created_at,
        expires_at=api_key_doc.expires_at,
        rate_limit=api_key_doc.rate_limit,
        model_ids=api_key_doc.model_ids,
    )


@router.get("/api-keys", response_model=list[APIKeyListResponse])
async def list_api_keys(current_user_id: str = Depends(get_current_user_id)):
    """List all API keys for the current user"""
    api_keys = await APIKey.find({"user_id": current_user_id}).to_list()

    return [
        APIKeyListResponse(
            key_id=key.key_id,
            name=key.name,
            description=key.description,
            created_at=key.created_at,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            total_requests=key.total_requests,
            rate_limit=key.rate_limit,
            is_active=key.is_active,
        )
        for key in api_keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """Revoke an API key"""
    api_key = await APIKey.find_one({"key_id": key_id, "user_id": current_user_id})

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    await api_key.save()

    return {"message": "API key revoked successfully"}


@router.post("/v1/models/{model_id}/predict", response_model=ProductionPredictResponse)
async def production_predict(
    model_id: str,
    request: ProductionPredictRequest,
    api_key: APIKey = Depends(verify_api_key),
):
    """Make predictions using a deployed model (Production API)

    Rate limiting is enforced globally by RateLimitMiddleware (#151).
    """

    # Verify model access
    if not api_key.has_model_access(model_id):
        raise HTTPException(
            status_code=403, detail="API key does not have access to this model"
        )

    # Get the model
    model = await MLModel.find_one(
        {"model_id": model_id, "user_id": api_key.user_id, "is_active": True}
    )

    if not model:
        raise HTTPException(status_code=404, detail="Model not found or inactive")

    # Load the model
    storage_service = ModelStorageService()

    request_start = datetime.utcnow()
    try:
        # load_model returns a (model, feature_engineer) tuple keyed by
        # (model_id, user_id) — not a dict keyed by S3 path (issue #82 bugfix).
        trained_model, feature_engineer = await storage_service.load_model(
            model_id, api_key.user_id
        )

        # Transform input data if feature engineer exists
        import pandas as pd

        df = pd.DataFrame(request.data)

        if feature_engineer:
            X_transformed = await feature_engineer.transform(df)
        else:
            X_transformed = df[model.feature_names]

        # Make predictions
        predictions = trained_model.predict(X_transformed)

        # Compute probabilities whenever the (calibrated) classifier supports
        # them; they drive confidence + low-confidence flags regardless of
        # whether the caller asked to see the full vectors (issue #83).
        proba_list = None
        if model.problem_type.endswith("classification") and hasattr(
            trained_model, "predict_proba"
        ):
            try:
                proba_list = trained_model.predict_proba(X_transformed).tolist()
            except Exception:  # noqa: BLE001 - probabilities are optional
                proba_list = None

        predictions_list = predictions.tolist()

        # Confidence / uncertainty / explanation enrichment (issue #83).
        enricher = _prediction_enricher
        confidence, low_confidence = enricher.per_record_confidence(proba_list)
        prediction_intervals = enricher.prediction_intervals(
            predictions_list, getattr(model, "residual_std", None)
        )
        explanations = None
        if request.include_explanations:
            explanations = enricher.explanations(
                trained_model,
                X_transformed,
                model.feature_names,
                predictions_list,
                model.problem_type,
                feature_importance=model.feature_importance,
            )

        # Create prediction ID for tracking
        prediction_id = f"pred_{PydanticObjectId()}"

        # Prepare metadata if requested
        metadata = None
        if request.include_metadata:
            metadata = {
                "model_name": model.name,
                "algorithm": model.algorithm,
                "problem_type": model.problem_type,
                "feature_count": model.n_features,
                "training_date": model.created_at.isoformat(),
            }

        # Record per-request monitoring metrics (issue #85) — best-effort.
        latency_ms = (datetime.utcnow() - request_start).total_seconds() * 1000
        await _record_serving_metrics(
            model_id=model_id,
            request_data=request.data,
            predictions=predictions_list,
            confidence=confidence,
            latency_ms=latency_ms,
            api_key_id=api_key.key_id,
        )

        return ProductionPredictResponse(
            predictions=predictions_list,
            probabilities=proba_list if request.include_probabilities else None,
            model_version=model.version,
            prediction_id=prediction_id,
            timestamp=datetime.utcnow(),
            metadata=metadata,
            confidence=confidence,
            low_confidence=low_confidence,
            is_calibrated=bool(getattr(model, "is_calibrated", False)),
            calibration_method=getattr(model, "calibration_method", None),
            confidence_threshold=enricher.threshold,
            prediction_intervals=prediction_intervals,
            explanations=explanations,
        )

    except Exception as e:
        # Record the failure so the dashboard's error rate / alerts reflect it.
        latency_ms = (datetime.utcnow() - request_start).total_seconds() * 1000
        await _record_serving_metrics(
            model_id=model_id,
            request_data=request.data,
            predictions=[],
            confidence=None,
            latency_ms=latency_ms,
            api_key_id=api_key.key_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/v1/models/{model_id}/info")
async def get_model_info(model_id: str, api_key: APIKey = Depends(verify_api_key)):
    """Get information about a deployed model"""

    # Verify model access
    if not api_key.has_model_access(model_id):
        raise HTTPException(
            status_code=403, detail="API key does not have access to this model"
        )

    # Get the model
    model = await MLModel.find_one(
        {"model_id": model_id, "user_id": api_key.user_id, "is_active": True}
    )

    if not model:
        raise HTTPException(status_code=404, detail="Model not found or inactive")

    return {
        "model_id": model.model_id,
        "name": model.name,
        "description": model.description,
        "problem_type": model.problem_type,
        "algorithm": model.algorithm,
        "feature_names": model.feature_names,
        "version": model.version,
        "created_at": model.created_at,
        "performance": {"cv_score": model.cv_score, "test_score": model.test_score},
    }
