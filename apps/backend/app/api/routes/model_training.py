"""
API routes for model training and management
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import logging

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.models.ml_model import MLModel
from app.services.s3_service import get_file_from_s3
from app.services.model_storage import ModelStorageService
from app.services.model_training import (
    AutoMLEngine,
    FeatureEngineeringConfig,
    ProblemType
)

logger = logging.getLogger(__name__)
router = APIRouter()


class TrainModelRequest(BaseModel):
    """Request for training a model"""
    dataset_id: str
    target_column: str
    name: Optional[str] = None
    description: Optional[str] = None
    feature_config: Optional[Dict[str, Any]] = None
    training_config: Optional[Dict[str, Any]] = None


class TrainModelResponse(BaseModel):
    """Response after initiating model training"""
    model_id: str
    status: str = "training"
    message: str


class ModelInfo(BaseModel):
    """Model information response"""
    model_id: str
    name: str
    description: Optional[str]
    problem_type: str
    algorithm: str
    target_column: str
    cv_score: float
    test_score: float
    created_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool


class PredictRequest(BaseModel):
    """Request for making predictions"""
    data: List[Dict[str, Any]]
    include_probabilities: bool = False


class PredictResponse(BaseModel):
    """Response with predictions"""
    predictions: List[Any]
    probabilities: Optional[List[List[float]]] = None
    feature_names: List[str]
    model_info: Dict[str, Any]


@router.post("/train", response_model=TrainModelResponse)
async def train_model(
    request: TrainModelRequest,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Train a new ML model on the specified dataset
    """
    # Verify dataset access
    user_data = await UserData.find_one(
        UserData.id == request.dataset_id,
        UserData.user_id == current_user_id
    )
    
    if not user_data:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Create a temporary model entry
    model_id = f"model_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    # Start training in background
    background_tasks.add_task(
        train_model_task,
        user_data,
        request,
        current_user_id,
        model_id
    )
    
    return TrainModelResponse(
        model_id=model_id,
        status="training",
        message="Model training started. Check status endpoint for progress."
    )


async def train_model_task(
    user_data: UserData,
    request: TrainModelRequest,
    user_id: str,
    model_id: str
):
    """Background task for model training"""
    try:
        logger.info(f"Starting model training for dataset {request.dataset_id}")
        
        # Load data from S3
        file_data = await get_file_from_s3(user_data.file_key)
        
        # Convert to dataframe based on file type
        if user_data.file_type == "csv":
            df = pd.read_csv(file_data)
        elif user_data.file_type in ["xls", "xlsx"]:
            df = pd.read_excel(file_data)
        elif user_data.file_type == "parquet":
            df = pd.read_parquet(file_data)
        else:
            raise ValueError(f"Unsupported file type: {user_data.file_type}")
        
        # Create feature engineering config
        feature_config = None
        if request.feature_config:
            feature_config = FeatureEngineeringConfig(**request.feature_config)
        
        # Create AutoML engine
        training_config = request.training_config or {}
        engine = AutoMLEngine(
            max_models=training_config.get("max_models", 5),
            cv_folds=training_config.get("cv_folds", 5),
            test_size=training_config.get("test_size", 0.2),
            random_state=42
        )
        
        # Run AutoML
        result = await engine.run(df, request.target_column, feature_config)
        
        # Prepare metadata
        model_metadata = {
            "name": request.name or f"{result.best_model.name} on {user_data.filename}",
            "description": request.description,
            "problem_type": result.problem_type.value,
            "target_column": request.target_column,
            "feature_names": result.feature_names,
            "n_samples_train": len(df),
            "feature_importance": result.feature_importance,
            "metrics": {
                "cv_score": result.best_model.cv_score,
                "test_score": result.best_model.test_score,
                "training_time": result.training_time
            },
            "training_config": training_config
        }
        
        # Save model
        storage_service = ModelStorageService()
        ml_model = await storage_service.save_model(
            result.best_model,
            engine.feature_engineer,
            user_id,
            request.dataset_id,
            model_metadata
        )
        
        logger.info(f"Model training completed: {ml_model.model_id}")
        
    except Exception as e:
        logger.error(f"Error training model: {str(e)}")
        # In production, you'd want to update a status in the database
        raise


@router.get("/", response_model=List[ModelInfo])
async def list_models(
    dataset_id: Optional[str] = Query(None),
    is_active: bool = Query(True),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    List all models for the current user
    """
    storage_service = ModelStorageService()
    models = await storage_service.list_models(
        current_user_id,
        dataset_id=dataset_id,
        is_active=is_active
    )
    
    return [
        ModelInfo(
            model_id=model.model_id,
            name=model.name,
            description=model.description,
            problem_type=model.problem_type,
            algorithm=model.algorithm,
            target_column=model.target_column,
            cv_score=model.cv_score,
            test_score=model.test_score,
            created_at=model.created_at,
            last_used_at=model.last_used_at,
            is_active=model.is_active
        )
        for model in models
    ]


@router.get("/{model_id}", response_model=MLModel)
async def get_model(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get detailed information about a specific model
    """
    model = await MLModel.find_one(
        MLModel.model_id == model_id,
        MLModel.user_id == current_user_id
    )
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return model


@router.post("/{model_id}/predict", response_model=PredictResponse)
async def predict(
    model_id: str,
    request: PredictRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Make predictions using a trained model
    """
    # Load model
    storage_service = ModelStorageService()
    try:
        model, feature_engineer = await storage_service.load_model(model_id, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # Get model metadata
    ml_model = await MLModel.find_one(
        MLModel.model_id == model_id,
        MLModel.user_id == current_user_id
    )
    
    # Convert input data to DataFrame
    input_df = pd.DataFrame(request.data)
    
    # Apply feature engineering if available
    if feature_engineer:
        input_df = await feature_engineer.transform(input_df)
    
    # Make predictions
    predictions = model.predict(input_df)
    
    # Get probabilities if requested and available
    probabilities = None
    if request.include_probabilities and hasattr(model, 'predict_proba'):
        prob_array = model.predict_proba(input_df)
        probabilities = prob_array.tolist()
    
    # Convert predictions to list
    if isinstance(predictions, np.ndarray):
        predictions = predictions.tolist()
    
    return PredictResponse(
        predictions=predictions,
        probabilities=probabilities,
        feature_names=ml_model.feature_names,
        model_info={
            "model_id": model_id,
            "algorithm": ml_model.algorithm,
            "problem_type": ml_model.problem_type,
            "target_column": ml_model.target_column
        }
    )


@router.delete("/{model_id}")
async def delete_model(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Delete a model
    """
    storage_service = ModelStorageService()
    deleted = await storage_service.delete_model(model_id, current_user_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return {"message": f"Model {model_id} deleted successfully"}


@router.put("/{model_id}/deactivate")
async def deactivate_model(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Deactivate a model (soft delete)
    """
    model = await MLModel.find_one(
        MLModel.model_id == model_id,
        MLModel.user_id == current_user_id
    )
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model.is_active = False
    model.updated_at = datetime.now(timezone.utc)
    await model.save()
    
    return {"message": f"Model {model_id} deactivated"}