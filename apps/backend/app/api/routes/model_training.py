"""
API routes for model training and management
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
import pandas as pd
import numpy as np
import io
import uuid
from datetime import datetime, timezone
import logging

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.models.ml_model import MLModel
from app.models.batch_job import JobStatus
from app.models.training_job import TrainingJob, ModelComparisonEntry
from app.services.s3_service import get_file_from_s3
from app.utils.s3 import parse_s3_url
from app.services.model_storage import ModelStorageService
from app.services.model_training import (
    AutoMLEngine,
    FeatureEngineeringConfig,
    TrainingCancelledError,
    TrainingEvent,
)
from app.services.model_training.algorithm_selector import AlgorithmSelector
from app.services.model_training.comparison import (
    build_best_model_explanation,
    build_data_profile,
)
from dataclasses import asdict

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


class TrainingStatusResponse(BaseModel):
    """Status and results of an async training job"""
    model_id: str
    status: str  # pending | running | completed | failed
    progress: float  # 0.0 - 1.0
    current_algorithm: Optional[str] = None
    completed_algorithms: int = 0
    total_algorithms: int = 0
    metrics: Dict[str, Any] = {}
    model_comparison: List[Dict[str, Any]] = []
    algorithm_recommendations: List[Dict[str, Any]] = []
    best_model_id: Optional[str] = None
    best_algorithm: Optional[str] = None
    explanation: Optional[str] = None
    error: Optional[str] = None


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

    # Create a unique model id. A short uuid suffix avoids collisions between
    # requests made within the same second (the id is the lookup key for the
    # TrainingJob status endpoint, so it must be unique).
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    model_id = f"model_{timestamp}_{uuid.uuid4().hex[:8]}"

    # Persist a pending TrainingJob synchronously so the status endpoint can be
    # polled immediately (before the background task has had a chance to run).
    training_job = TrainingJob(
        model_id=model_id,
        user_id=current_user_id,
        dataset_id=request.dataset_id,
        target_column=request.target_column,
        status=JobStatus.PENDING,
    )
    await training_job.insert()

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
        message=f"Model training started. Poll GET /api/v1/ml/{model_id}/status for progress."
    )


async def train_model_task(
    user_data: UserData,
    request: TrainModelRequest,
    user_id: str,
    model_id: str
):
    """Background task for model training.

    Tracks lifecycle on the ``TrainingJob`` document (created by ``train_model``)
    so that ``GET /ml/{model_id}/status`` reflects real progress, the model
    comparison, the algorithm recommendations, and any failure.
    """
    # Best-effort lookup of the tracking job; training proceeds even if it is
    # missing or the lookup fails (e.g. DB unavailable).
    try:
        training_job = await TrainingJob.find_one(
            TrainingJob.model_id == model_id,
            TrainingJob.user_id == user_id,
        )
    except Exception as exc:
        logger.warning(f"Could not load TrainingJob {model_id}: {exc}")
        training_job = None

    try:
        logger.info(f"Starting model training for dataset {request.dataset_id}")

        # Mark RUNNING at task entry so the status reflects real activity during
        # the (potentially slow) S3 download and dataset parse, not just model fit.
        if training_job:
            training_job.mark_started()
            training_job.add_log(
                "info", f"Training task started for dataset {request.dataset_id}"
            )
            await training_job.save()

        # Extract S3 file key (parse_s3_url handles all persisted URL shapes)
        _, file_key = parse_s3_url(user_data.s3_url)

        # Load data from S3
        file_bytes = await get_file_from_s3(file_key)

        if training_job:
            training_job.add_log(
                "info", f"Dataset downloaded ({len(file_bytes)} bytes)"
            )
            await training_job.save()

        # Convert to dataframe based on file type, wrapping bytes in proper file-like objects
        if user_data.file_type == "csv":
            # For CSV, decode bytes to text and use StringIO
            file_str = file_bytes.decode("utf-8")
            df = pd.read_csv(io.StringIO(file_str))
        elif user_data.file_type in ["xls", "xlsx"]:
            # For Excel, use BytesIO
            file_io = io.BytesIO(file_bytes)
            file_io.seek(0)
            df = pd.read_excel(file_io)
        elif user_data.file_type == "parquet":
            # For Parquet, use BytesIO
            file_io = io.BytesIO(file_bytes)
            file_io.seek(0)
            df = pd.read_parquet(file_io)
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

        # Progress callback persists per-algorithm progress to the TrainingJob.
        # Partial ($set) updates are used here and in on_event so a concurrent
        # cancellation flag written by POST /{model_id}/cancel is never clobbered
        # by saving this (stale) in-memory document wholesale.
        async def on_progress(completed: int, total: int, current: Optional[str]):
            if not training_job:
                return
            training_job.update_progress(
                completed_algorithms=completed,
                total_algorithms=total,
                current_algorithm=current,
            )
            await training_job.set(
                {
                    TrainingJob.progress: training_job.progress,
                    TrainingJob.updated_at: training_job.updated_at,
                }
            )

        # Event callback persists engine logs, the pipeline stage, and
        # incremental model-comparison rows as candidates finish training.
        async def on_event(event: TrainingEvent):
            if not training_job:
                return
            training_job.add_log(event.level, event.message, stage=event.stage)
            if event.stage:
                training_job.progress.current_stage = event.stage
            if event.candidate:
                training_job.model_comparison.append(
                    ModelComparisonEntry(**event.candidate)
                )
            await training_job.set(
                {
                    TrainingJob.logs: training_job.logs,
                    TrainingJob.progress: training_job.progress,
                    TrainingJob.model_comparison: training_job.model_comparison,
                    TrainingJob.updated_at: training_job.updated_at,
                }
            )

        # Cancellation check re-reads the job from MongoDB so a flag set by
        # POST /{model_id}/cancel after this task loaded its copy is seen.
        async def is_cancellation_requested() -> bool:
            fresh = await TrainingJob.find_one(
                TrainingJob.model_id == model_id,
                TrainingJob.user_id == user_id,
            )
            return bool(fresh and fresh.cancellation_requested)

        # Run AutoML
        result = await engine.run(
            df,
            request.target_column,
            feature_config,
            progress_callback=on_progress,
            event_callback=on_event,
            cancel_check=is_cancellation_requested,
        )

        # Prepare metadata
        model_metadata: Dict[str, Any] = {
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

        # Save model with the pre-generated model_id
        storage_service = ModelStorageService()
        ml_model = await storage_service.save_model(
            result.best_model,
            engine.feature_engineer,
            user_id,
            request.dataset_id,
            model_metadata,
            model_id=model_id
        )

        # Persist comparison + recommendations + best-model explanation on the job.
        if training_job:
            comparison = [
                ModelComparisonEntry(**row)
                for row in result.metadata.get("model_comparison", [])
            ]
            recommendations = await _build_algorithm_recommendations(
                df, request.target_column, result.problem_type
            )
            explanation = build_best_model_explanation(
                result.best_model, result.all_models, result.problem_type
            )
            training_job.mark_completed(
                best_model_id=ml_model.model_id,
                best_algorithm=result.best_model.name,
                best_model_explanation=explanation,
                model_comparison=comparison,
                algorithm_recommendations=recommendations,
                metrics=model_metadata["metrics"],
            )
            training_job.add_log(
                "info",
                (
                    f"Training completed: best algorithm {result.best_model.name} "
                    f"(cv_score={result.best_model.cv_score:.4f})"
                ),
            )
            await training_job.save()

        logger.info(f"Model training completed: {ml_model.model_id}")

    except TrainingCancelledError:
        logger.info(f"Model training cancelled by user: {model_id}")
        if training_job:
            # Guarded like the failure path: persisting the cancellation must
            # never raise out of the background task.
            try:
                training_job.mark_cancelled()
                training_job.add_log("info", "Training cancelled by user")
                await training_job.save()
            except Exception as save_exc:
                logger.error(
                    f"Failed to persist CANCELLED status for {model_id}: {save_exc}"
                )

    except Exception as e:
        logger.error(f"Error training model: {str(e)}")
        if training_job:
            # Guard the failure-recording itself: a secondary error here (e.g. a
            # transient DB outage during save) must not escape the background task.
            try:
                training_job.mark_failed(str(e))
                training_job.add_log("error", f"Training failed: {e}")
                await training_job.save()
            except Exception as save_exc:
                logger.error(
                    f"Failed to persist FAILED status for {model_id}: {save_exc}"
                )
        # Swallow here: this runs as a fire-and-forget BackgroundTask, so the
        # failure is recorded on the TrainingJob (above) rather than re-raised
        # into a context where nothing can handle it.


async def _build_algorithm_recommendations(
    df: pd.DataFrame, target_column: str, problem_type
) -> List[Dict[str, Any]]:
    """Build plain-language algorithm recommendations for a dataset.

    Uses the rule-based ``AlgorithmSelector`` (no LLM/API call). Returns an empty
    list and logs on any failure so recommendations never break training.
    """
    try:
        profile = build_data_profile(df, target_column, problem_type)
        selector = AlgorithmSelector()
        recommendations = await selector.select_algorithms(problem_type, profile, {})
        return [asdict(rec) for rec in recommendations]
    except Exception as exc:
        logger.warning(f"Failed to build algorithm recommendations: {exc}")
        return []


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


@router.get("/{model_id}/status", response_model=TrainingStatusResponse)
async def get_training_status(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get the status, progress, and results of an async training job.

    The frontend polls this endpoint after starting training. While training is
    in progress it returns live per-algorithm progress; on completion it returns
    the model comparison, algorithm recommendations, and the best-model
    explanation; on failure it returns the error message.
    """
    job = await TrainingJob.find_one(
        TrainingJob.model_id == model_id,
        TrainingJob.user_id == current_user_id,
    )

    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")

    return TrainingStatusResponse(
        model_id=job.model_id,
        status=job.status.value,
        progress=job.progress.fraction,
        current_algorithm=job.progress.current_algorithm,
        completed_algorithms=job.progress.completed_algorithms,
        total_algorithms=job.progress.total_algorithms,
        metrics=job.metrics,
        model_comparison=[entry.model_dump() for entry in job.model_comparison],
        algorithm_recommendations=job.algorithm_recommendations,
        best_model_id=job.best_model_id,
        best_algorithm=job.best_algorithm,
        explanation=job.best_model_explanation,
        error=job.error,
    )


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