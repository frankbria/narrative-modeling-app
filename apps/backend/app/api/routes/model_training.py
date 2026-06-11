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

from beanie import PydanticObjectId
from beanie.odm.operators.update.array import Push
from beanie.odm.operators.update.general import Set
from bson.errors import InvalidId

from app.auth.nextauth_auth import get_current_user_id
from app.models.user_data import UserData
from app.models.ml_model import MLModel
from app.models.batch_job import JobStatus
from app.models.training_job import (
    TrainingJob,
    TrainingLogEntry,
    ModelComparisonEntry,
)
from app.services.s3_service import get_file_from_s3
from app.utils.s3 import parse_s3_url
from app.services.model_storage import ModelStorageService, build_evaluation_payload
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
    status: str  # pending | running | completed | failed | cancelled
    progress: float  # 0.0 - 1.0
    current_algorithm: Optional[str] = None
    current_stage: Optional[str] = None  # preprocessing | training | finalizing
    completed_algorithms: int = 0
    total_algorithms: int = 0
    elapsed_seconds: Optional[float] = None
    estimated_remaining_seconds: Optional[float] = None
    cancellation_requested: bool = False
    metrics: Dict[str, Any] = {}
    model_comparison: List[Dict[str, Any]] = []
    algorithm_recommendations: List[Dict[str, Any]] = []
    best_model_id: Optional[str] = None
    best_algorithm: Optional[str] = None
    explanation: Optional[str] = None
    error: Optional[str] = None


class TrainingJobSummary(BaseModel):
    """Condensed view of one training job for the jobs list"""

    model_id: str
    dataset_id: str
    target_column: str
    status: str
    progress_percentage: float
    current_stage: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    best_algorithm: Optional[str] = None
    best_score: Optional[float] = None
    elapsed_seconds: Optional[float] = None


class TrainingJobListResponse(BaseModel):
    """Paginated list of the current user's training jobs"""

    jobs: List[TrainingJobSummary]
    total_count: int
    limit: int
    skip: int


class TrainingLogsResponse(BaseModel):
    """Paginated log entries for one training job"""

    model_id: str
    logs: List[TrainingLogEntry]
    total_count: int
    has_more: bool


class CancelTrainingResponse(BaseModel):
    """Acknowledgement that cancellation of a training job was requested"""

    model_id: str
    status: str
    cancellation_requested: bool
    message: str


@router.post("/train", response_model=TrainModelResponse)
async def train_model(
    request: TrainModelRequest,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Train a new ML model on the specified dataset
    """
    # Verify dataset access. UserData.id is an ObjectId, so the raw string
    # from the request must be coerced or the comparison never matches; a
    # non-ObjectId string is passed through and simply matches nothing.
    dataset_id: Any = request.dataset_id
    try:
        dataset_id = PydanticObjectId(request.dataset_id)
    except (InvalidId, ValueError, TypeError):
        pass
    user_data = await UserData.find_one(
        UserData.id == dataset_id, UserData.user_id == current_user_id
    )

    if not user_data:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Create a unique model id. A short uuid suffix avoids collisions between
    # requests made within the same second (the id is the lookup key for the
    # TrainingJob status endpoint, so it must be unique).
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
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
        train_model_task, user_data, request, current_user_id, model_id
    )

    return TrainModelResponse(
        model_id=model_id,
        status="training",
        message=f"Model training started. Poll GET /api/v1/ml/{model_id}/status for progress.",
    )


async def train_model_task(
    user_data: UserData, request: TrainModelRequest, user_id: str, model_id: str
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
            random_state=42,
        )

        # Progress callback persists per-algorithm progress to the TrainingJob.
        # Partial updates are used here and in on_event so concurrent writes by
        # POST /{model_id}/cancel (the cancellation flag and its log entry) are
        # never clobbered by saving this (stale) in-memory document wholesale:
        # scalars/embedded docs go through $set, log appends through $push.
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
            entry = training_job.add_log(event.level, event.message, stage=event.stage)
            fields_to_set: Dict[Any, Any] = {
                TrainingJob.progress: training_job.progress,
                TrainingJob.updated_at: training_job.updated_at,
            }
            if event.stage:
                training_job.progress.current_stage = event.stage
            if event.candidate:
                training_job.model_comparison.append(
                    ModelComparisonEntry(**event.candidate)
                )
                # Only candidate events change the comparison; rewriting the
                # array on every stage/log event is wasted write volume.
                fields_to_set[TrainingJob.model_comparison] = (
                    training_job.model_comparison
                )
            await training_job.update(
                Push({TrainingJob.logs: entry}),
                Set(fields_to_set),
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
                "training_time": result.training_time,
            },
            "training_config": training_config,
        }

        # Held-out evaluation artifacts for the dashboard (issue #79).
        # Built best-effort: a payload problem must never fail training.
        evaluation_data = None
        if result.y_test is not None and result.y_pred is not None:
            try:
                evaluation_data = build_evaluation_payload(
                    problem_type=result.problem_type.value,
                    y_test=result.y_test,
                    y_pred=result.y_pred,
                    y_proba=result.y_proba,
                    class_labels=result.class_labels,
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to build evaluation payload for {model_id}: {exc}"
                )

        # Save model with the pre-generated model_id
        storage_service = ModelStorageService()
        ml_model = await storage_service.save_model(
            result.best_model,
            engine.feature_engineer,
            user_id,
            request.dataset_id,
            model_metadata,
            model_id=model_id,
            evaluation_data=evaluation_data,
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
            training_job = await _refreshed_job(training_job)
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
                training_job = await _refreshed_job(training_job)
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
                training_job = await _refreshed_job(training_job)
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


async def _refreshed_job(job: TrainingJob) -> TrainingJob:
    """Re-read a training job before a terminal full-document save.

    The cancel endpoint may have appended a log entry (and set the
    cancellation flag) after the background task loaded its copy; saving the
    stale in-memory document wholesale would silently drop those writes.
    Falls back to the in-memory copy if the re-read fails.
    """
    try:
        fresh = await TrainingJob.find_one(
            TrainingJob.model_id == job.model_id,
            TrainingJob.user_id == job.user_id,
        )
        return fresh or job
    except Exception as exc:
        logger.warning(f"Could not refresh TrainingJob {job.model_id}: {exc}")
        return job


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
    current_user_id: str = Depends(get_current_user_id),
):
    """
    List all models for the current user
    """
    storage_service = ModelStorageService()
    models = await storage_service.list_models(
        current_user_id, dataset_id=dataset_id, is_active=is_active
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
            is_active=model.is_active,
        )
        for model in models
    ]


def _best_comparison_score(job: TrainingJob) -> Optional[float]:
    """Best score across the comparison rows (test_score, else cv_score)."""
    scores = [
        row.test_score if row.test_score is not None else row.cv_score
        for row in job.model_comparison
    ]
    scores = [score for score in scores if score is not None]
    return max(scores) if scores else None


# NOTE: registered before the dynamic GET /{model_id} route so "jobs" is never
# captured as a model id.
@router.get("/jobs", response_model=TrainingJobListResponse)
async def list_training_jobs(
    status: Optional[str] = Query(
        None,
        description=(
            "Lifecycle status filter; accepts a single status or a "
            "comma-separated list (e.g. 'completed,failed,cancelled')"
        ),
    ),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    List the current user's training jobs, newest first.

    Supports filtering by one or more lifecycle statuses (comma-separated, so
    the history view can paginate over exactly the terminal statuses) and
    skip/limit pagination; ``total_count`` is the size of the filtered result
    set.
    """
    query: Dict[str, Any] = {"user_id": current_user_id}
    if status is not None:
        try:
            statuses = [JobStatus(s.strip()) for s in status.split(",") if s.strip()]
        except ValueError:
            raise HTTPException(
                status_code=422, detail=f"Invalid status filter: {status}"
            )
        if not statuses:
            raise HTTPException(
                status_code=422, detail="Status filter must not be empty"
            )
        query["status"] = statuses[0] if len(statuses) == 1 else {"$in": statuses}

    total_count = await TrainingJob.find(query).count()
    jobs = (
        await TrainingJob.find(query)
        .sort("-created_at")
        .skip(skip)
        .limit(limit)
        .to_list()
    )

    return TrainingJobListResponse(
        jobs=[
            TrainingJobSummary(
                model_id=job.model_id,
                dataset_id=job.dataset_id,
                target_column=job.target_column,
                status=job.status.value,
                progress_percentage=job.progress.percentage,
                current_stage=job.progress.current_stage,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                best_algorithm=job.best_algorithm,
                best_score=_best_comparison_score(job),
                elapsed_seconds=job.elapsed_seconds,
            )
            for job in jobs
        ],
        total_count=total_count,
        limit=limit,
        skip=skip,
    )


@router.get("/{model_id}/logs", response_model=TrainingLogsResponse)
async def get_training_logs(
    model_id: str,
    level: Optional[str] = Query(None, pattern="^(info|warning|error)$"),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Get the log entries recorded for a training job, oldest first.

    Supports filtering by level and skip/limit pagination; ``has_more`` flags
    whether further pages exist beyond the returned window.
    """
    job = await TrainingJob.find_one(
        TrainingJob.model_id == model_id,
        TrainingJob.user_id == current_user_id,
    )

    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")

    entries = job.logs
    if level is not None:
        entries = [entry for entry in entries if entry.level == level]
    total_count = len(entries)

    return TrainingLogsResponse(
        model_id=job.model_id,
        logs=entries[skip : skip + limit],
        total_count=total_count,
        has_more=skip + limit < total_count,
    )


@router.post("/{model_id}/cancel", response_model=CancelTrainingResponse)
async def cancel_training(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Request cancellation of a running (or pending) training job.

    Cancellation is cooperative: the flag is checked by the training task
    between candidate models, so the job transitions to ``cancelled`` shortly
    after, not instantly. Returns 409 if the job is already terminal.
    """
    job = await TrainingJob.find_one(
        TrainingJob.model_id == model_id,
        TrainingJob.user_id == current_user_id,
    )

    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")

    terminal_statuses = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
    if job.status in terminal_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Training job is already {job.status.value} and cannot be cancelled",
        )

    job.cancellation_requested = True
    job.add_log("info", "Cancellation requested")
    await job.save()

    return CancelTrainingResponse(
        model_id=job.model_id,
        status=job.status.value,
        cancellation_requested=True,
        message=(
            "Cancellation requested. The job will stop before training the "
            "next candidate model."
        ),
    )


@router.get("/{model_id}/status", response_model=TrainingStatusResponse)
async def get_training_status(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
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
        current_stage=job.progress.current_stage,
        completed_algorithms=job.progress.completed_algorithms,
        total_algorithms=job.progress.total_algorithms,
        elapsed_seconds=job.elapsed_seconds,
        estimated_remaining_seconds=job.estimated_remaining_seconds,
        cancellation_requested=job.cancellation_requested,
        metrics=job.metrics,
        model_comparison=[entry.model_dump() for entry in job.model_comparison],
        algorithm_recommendations=job.algorithm_recommendations,
        best_model_id=job.best_model_id,
        best_algorithm=job.best_algorithm,
        explanation=job.best_model_explanation,
        error=job.error,
    )


@router.get("/{model_id}", response_model=MLModel)
async def get_model(model_id: str, current_user_id: str = Depends(get_current_user_id)):
    """
    Get detailed information about a specific model
    """
    model = await MLModel.find_one(
        MLModel.model_id == model_id, MLModel.user_id == current_user_id
    )

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    return model


@router.post("/{model_id}/predict", response_model=PredictResponse)
async def predict(
    model_id: str,
    request: PredictRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Make predictions using a trained model
    """
    # Load model
    storage_service = ModelStorageService()
    try:
        model, feature_engineer = await storage_service.load_model(
            model_id, current_user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Get model metadata
    ml_model = await MLModel.find_one(
        MLModel.model_id == model_id, MLModel.user_id == current_user_id
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
    if request.include_probabilities and hasattr(model, "predict_proba"):
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
            "target_column": ml_model.target_column,
        },
    )


@router.delete("/{model_id}")
async def delete_model(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
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
    model_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """
    Deactivate a model (soft delete)
    """
    model = await MLModel.find_one(
        MLModel.model_id == model_id, MLModel.user_id == current_user_id
    )

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    model.is_active = False
    model.updated_at = datetime.now(timezone.utc)
    await model.save()

    return {"message": f"Model {model_id} deactivated"}
