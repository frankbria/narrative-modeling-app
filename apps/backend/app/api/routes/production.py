"""
Production model serving API routes
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import hashlib
import redis
from beanie import PydanticObjectId

from app.models.api_key import APIKey
from app.models.ml_model import MLModel
from app.models.user_data import UserData
from app.services.model_storage import ModelStorageService
from app.api.deps import get_current_user_id
from app.config import settings
router = APIRouter(prefix="/production", tags=["production"])

# Initialize Redis for rate limiting
redis_client = None  # Redis is optional for development
try:
    if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
        redis_client = redis.from_url(settings.REDIS_URL)
except:
    pass


# Request/Response Models
class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., description="Friendly name for the API key")
    description: Optional[str] = Field(None, description="Description of key usage")
    model_ids: Optional[List[str]] = Field(None, description="Specific model IDs to allow")
    rate_limit: int = Field(default=1000, description="Requests per hour")
    expires_in_days: Optional[int] = Field(None, description="Days until expiration")


class APIKeyResponse(BaseModel):
    key_id: str
    api_key: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime]
    rate_limit: int
    model_ids: List[str]


class ProductionPredictRequest(BaseModel):
    data: List[Dict[str, Any]] = Field(..., description="Input data for prediction")
    include_metadata: bool = Field(default=False, description="Include model metadata")
    include_probabilities: bool = Field(default=True, description="Include probabilities for classification")


class ProductionPredictResponse(BaseModel):
    predictions: List[Any]
    probabilities: Optional[List[List[float]]] = None
    model_version: str
    prediction_id: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class APIKeyListResponse(BaseModel):
    key_id: str
    name: str
    description: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    total_requests: int
    rate_limit: int
    is_active: bool


# Helper functions
def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


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


async def check_rate_limit(api_key: APIKey, request: Request) -> None:
    """Check if the API key has exceeded its rate limit"""
    if not redis_client:
        return  # Skip rate limiting if Redis not configured
    
    # Create rate limit key
    rate_key = f"rate_limit:{api_key.key_id}:{datetime.utcnow().hour}"
    
    # Increment counter
    try:
        current_count = redis_client.incr(rate_key)
        
        # Set expiration on first request of the hour
        if current_count == 1:
            redis_client.expire(rate_key, 3600)  # 1 hour
        
        # Check limit
        if current_count > api_key.rate_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Limit: {api_key.rate_limit}/hour"
            )
    except redis.RedisError:
        # Don't block requests if Redis is down
        pass


# API Routes
@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user_id: str = Depends(get_current_user_id)
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
        expires_at=expires_at
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
        model_ids=api_key_doc.model_ids
    )


@router.get("/api-keys", response_model=List[APIKeyListResponse])
async def list_api_keys(
    current_user_id: str = Depends(get_current_user_id)
):
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
            is_active=key.is_active
        )
        for key in api_keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Revoke an API key"""
    api_key = await APIKey.find_one({
        "key_id": key_id,
        "user_id": current_user_id
    })
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.is_active = False
    await api_key.save()
    
    return {"message": "API key revoked successfully"}


@router.post("/v1/models/{model_id}/predict", response_model=ProductionPredictResponse)
async def production_predict(
    model_id: str,
    request: ProductionPredictRequest,
    req: Request,
    api_key: APIKey = Depends(verify_api_key)
):
    """Make predictions using a deployed model (Production API)"""
    
    # Check rate limit
    await check_rate_limit(api_key, req)
    
    # Verify model access
    if not api_key.has_model_access(model_id):
        raise HTTPException(status_code=403, detail="API key does not have access to this model")
    
    # Get the model
    model = await MLModel.find_one({
        "model_id": model_id,
        "user_id": api_key.user_id,
        "is_active": True
    })
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found or inactive")
    
    # Load the model
    storage_service = ModelStorageService()
    
    try:
        model_artifacts = await storage_service.load_model(model.model_path)
        trained_model = model_artifacts["model"]
        feature_engineer = model_artifacts.get("feature_engineer")
        
        # Transform input data if feature engineer exists
        import pandas as pd
        df = pd.DataFrame(request.data)
        
        if feature_engineer:
            X_transformed = feature_engineer.transform(df)
        else:
            X_transformed = df[model.feature_names]
        
        # Make predictions
        predictions = trained_model.predict(X_transformed)
        
        # Get probabilities for classification
        probabilities = None
        if request.include_probabilities and model.problem_type.endswith("classification"):
            if hasattr(trained_model, "predict_proba"):
                probabilities = trained_model.predict_proba(X_transformed).tolist()
        
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
                "training_date": model.created_at.isoformat()
            }
        
        # Log prediction (async, don't wait)
        # In production, this would go to a logging service
        
        return ProductionPredictResponse(
            predictions=predictions.tolist(),
            probabilities=probabilities,
            model_version=model.version,
            prediction_id=prediction_id,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/v1/models/{model_id}/info")
async def get_model_info(
    model_id: str,
    api_key: APIKey = Depends(verify_api_key)
):
    """Get information about a deployed model"""
    
    # Verify model access
    if not api_key.has_model_access(model_id):
        raise HTTPException(status_code=403, detail="API key does not have access to this model")
    
    # Get the model
    model = await MLModel.find_one({
        "model_id": model_id,
        "user_id": api_key.user_id,
        "is_active": True
    })
    
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
        "performance": {
            "cv_score": model.cv_score,
            "test_score": model.test_score
        }
    }