"""
API routes for model training and management
"""

import io
import logging
import math
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from beanie import PydanticObjectId
from beanie.odm.operators.update.array import Push
from beanie.odm.operators.update.general import Set
from bson.errors import InvalidId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.nextauth_auth import get_current_user_id
from app.models.batch_job import JobStatus
from app.models.ml_model import MLModel
from app.models.training_job import (
    LogLevel,
    ModelComparisonEntry,
    TrainingJob,
    TrainingLogEntry,
)
from app.models.user_data import UserData
from app.schemas.error_analysis import ErrorAnalysisResponse
from app.schemas.evaluation import (
    ClassificationMetrics,
    FeatureImportanceResponse,
    ModelComparisonRequest,
    ModelComparisonResponse,
    ModelEvaluationResponse,
    ModelEvaluationSummary,
    ModelVersionEntry,
    ModelVersionListResponse,
    PromoteVersionResponse,
    RankedFeature,
    RegressionMetrics,
    ShapSummaryResponse,
)
from app.schemas.model import PredictionExplanation
from app.services.confidence_service import DEFAULT_LOW_CONFIDENCE_THRESHOLD
from app.services.error_analysis_service import error_analysis_service
from app.services.evaluation_explanation_service import evaluation_explanation_service
from app.services.exceptions import NotFoundError
from app.services.interpretability_service import InterpretabilityService
from app.services.metrics_service import MetricsService
from app.services.model_storage import (
    ModelStorageService,
    build_evaluation_payload,
    build_shap_payload,
)
from app.services.model_training import (
    AutoMLEngine,
    FeatureEngineeringConfig,
    TrainingCancelledError,
    TrainingEvent,
    TuningConfig,
)
from app.services.model_training.algorithm_selector import AlgorithmSelector
from app.services.model_training.comparison import (
    build_best_model_explanation,
    build_data_profile,
)
from app.services.model_versioning_service import model_versioning_service
from app.services.prediction_enrichment import PredictionEnricher
from app.services.s3_service import get_file_from_s3
from app.utils.s3 import parse_s3_url

logger = logging.getLogger(__name__)
router = APIRouter()

# Upper bound on records accepted by the synchronous single-prediction endpoint;
# larger workloads must go through the async batch path (issue #82 hardening).
MAX_PREDICT_RECORDS = 1000

# Stateless — reuse one instance instead of constructing it per request (#83).
_prediction_enricher = PredictionEnricher()
# Stateless SHAP interpretability helper (issue #80).
_interpretability_service = InterpretabilityService()


def _rank_importance(importance: dict[str, float] | None) -> list[RankedFeature]:
    """Convert an importance dict into a list ranked by descending importance.

    Tolerates a non-dict (e.g. corrupted S3 payload) by returning an empty list,
    preserving the endpoints' never-500 contract.
    """
    if not isinstance(importance, dict) or not importance:
        return []
    return [
        RankedFeature(feature_name=name, importance=float(value))
        for name, value in sorted(
            importance.items(), key=lambda kv: kv[1], reverse=True
        )
    ]


class TrainModelRequest(BaseModel):
    """Request for training a model"""

    dataset_id: str
    target_column: str
    name: str | None = None
    description: str | None = None
    feature_config: dict[str, Any] | None = None
    training_config: dict[str, Any] | None = None


class TrainModelResponse(BaseModel):
    """Response after initiating model training"""

    model_id: str
    status: str = "training"
    message: str


class ModelInfo(BaseModel):
    """Model information response"""

    model_id: str
    name: str
    description: str | None
    problem_type: str
    algorithm: str
    target_column: str
    cv_score: float
    test_score: float
    created_at: datetime
    last_used_at: datetime | None
    is_active: bool


class PredictRequest(BaseModel):
    """Request for making predictions"""

    data: list[dict[str, Any]] = Field(..., max_length=MAX_PREDICT_RECORDS)
    include_probabilities: bool = False
    # Per-prediction feature-contribution breakdowns are off by default to keep
    # responses light; opt in for explainability (issue #83).
    include_explanations: bool = False


class PredictResponse(BaseModel):
    """Response with predictions"""

    predictions: list[Any]
    probabilities: list[list[float]] | None = None
    # Per-record confidence (max class probability) for classification; None
    # for regression or when probabilities are unavailable (issue #82).
    confidence: list[float] | None = None
    # Ordered class labels matching each probability vector, so the UI can map
    # probabilities to human-readable classes (issue #82).
    class_labels: list[str] | None = None
    feature_names: list[str]
    model_info: dict[str, Any]
    # Confidence & explainability enrichment (issue #83). All optional:
    # pre-#83 models report is_calibrated=False and omit intervals/explanations.
    low_confidence: list[bool] | None = None  # per-record warning flags
    is_calibrated: bool = False
    calibration_method: str | None = None
    confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD
    prediction_intervals: list[list[float] | None] | None = None  # regression
    explanations: list[PredictionExplanation | None] | None = None


class FeatureDescriptor(BaseModel):
    """One raw input feature the prediction form must collect (issue #82)."""

    name: str
    # "number" for numeric inputs, "categorical" for a constrained choice.
    type: str
    # Allowed values for categorical features (from the fitted encoder), when
    # recoverable; None otherwise.
    options: list[str] | None = None


class ModelFeaturesResponse(BaseModel):
    """The input schema needed to auto-generate a prediction form (issue #82)."""

    features: list[FeatureDescriptor]
    class_labels: list[str] | None = None
    problem_type: str
    target_column: str


class TrainingStatusResponse(BaseModel):
    """Status and results of an async training job"""

    model_id: str
    status: str  # pending | running | completed | failed | cancelled
    progress: float  # 0.0 - 1.0
    current_algorithm: str | None = None
    current_stage: str | None = None  # preprocessing | training | finalizing
    completed_algorithms: int = 0
    total_algorithms: int = 0
    elapsed_seconds: float | None = None
    estimated_remaining_seconds: float | None = None
    cancellation_requested: bool = False
    metrics: dict[str, Any] = {}
    model_comparison: list[dict[str, Any]] = []
    algorithm_recommendations: list[dict[str, Any]] = []
    best_model_id: str | None = None
    best_algorithm: str | None = None
    explanation: str | None = None
    error: str | None = None


class TrainingJobSummary(BaseModel):
    """Condensed view of one training job for the jobs list"""

    model_id: str
    dataset_id: str
    target_column: str
    status: str
    progress_percentage: float
    current_stage: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    best_algorithm: str | None = None
    best_score: float | None = None
    elapsed_seconds: float | None = None


class TrainingJobListResponse(BaseModel):
    """Paginated list of the current user's training jobs"""

    jobs: list[TrainingJobSummary]
    total_count: int
    limit: int
    skip: int


class TrainingLogsResponse(BaseModel):
    """Paginated log entries for one training job"""

    model_id: str
    logs: list[TrainingLogEntry]
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
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
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

        # Create AutoML engine. Hyperparameter tuning (issue #77) is opt-in via
        # the existing training_config dict — no request-schema change. When
        # enable_tuning is set, the nested tuning_config keys feed TuningConfig
        # (an unknown strategy raises in __post_init__, surfaced as a failed job).
        training_config = request.training_config or {}
        tuning_engine_config = None
        if training_config.get("enable_tuning"):
            raw_tuning = dict(training_config.get("tuning_config") or {})
            if training_config.get("tuning_strategy"):
                raw_tuning.setdefault("strategy", training_config["tuning_strategy"])
            tuning_engine_config = TuningConfig(**raw_tuning)
        engine = AutoMLEngine(
            max_models=training_config.get("max_models", 5),
            cv_folds=training_config.get("cv_folds", 5),
            test_size=training_config.get("test_size", 0.2),
            random_state=42,
            enable_tuning=bool(training_config.get("enable_tuning")),
            tuning_config=tuning_engine_config,
        )

        # Progress callback persists per-algorithm progress to the TrainingJob.
        # Partial updates are used here and in on_event so concurrent writes by
        # POST /{model_id}/cancel (the cancellation flag and its log entry) are
        # never clobbered by saving this (stale) in-memory document wholesale:
        # scalars/embedded docs go through $set, log appends through $push.
        async def on_progress(completed: int, total: int, current: str | None):
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
            level: LogLevel
            if event.level == "warning":
                level = "warning"
            elif event.level == "error":
                level = "error"
            else:
                level = "info"
            entry = training_job.add_log(level, event.message, stage=event.stage)
            fields_to_set: dict[Any, Any] = {
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
        model_metadata: dict[str, Any] = {
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
            # Confidence/uncertainty metadata (issue #83).
            "is_calibrated": result.is_calibrated,
            "calibration_method": result.calibration_method,
            "calibration_score": result.calibration_score,
            "residual_std": result.residual_std,
            # SHAP interpretability (issue #80).
            "shap_explainer_type": result.shap_explainer_type,
            # Hyperparameter tuning (issue #77). None when tuning was off.
            # tuning_time is the sum of the per-algorithm search durations, NOT
            # the full AutoML wall time (result.training_time).
            "tuning_strategy": result.tuning_strategy,
            "tuning_time": (
                sum(r.get("total_time", 0.0) for r in result.tuning_results.values())
                if result.tuning_results
                else None
            ),
            "improvement_from_tuning": result.improvement_from_tuning,
            "tuning_results": result.tuning_results,
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
                    x_test=result.x_test,
                    feature_names=result.feature_names,
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to build evaluation payload for {model_id}: {exc}"
                )

        # Global SHAP summary for the interpretability dashboard (issue #80).
        # Built best-effort; ``None`` for unsupported model types.
        shap_data = None
        try:
            shap_data = build_shap_payload(result.shap_global)
        except Exception as exc:
            logger.warning(f"Failed to build SHAP payload for {model_id}: {exc}")

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
            shap_data=shap_data,
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
) -> list[dict[str, Any]]:
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


@router.get("/", response_model=list[ModelInfo])
async def list_models(
    dataset_id: str | None = Query(None),
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


def _best_comparison_score(job: TrainingJob) -> float | None:
    """Best score across the comparison rows (test_score, else cv_score)."""
    scores = [
        row.test_score if row.test_score is not None else row.cv_score
        for row in job.model_comparison
    ]
    valid_scores: list[float] = [score for score in scores if score is not None]
    return max(valid_scores) if valid_scores else None


# NOTE: registered before the dynamic GET /{model_id} route so "jobs" is never
# captured as a model id.
@router.get("/jobs", response_model=TrainingJobListResponse)
async def list_training_jobs(
    status: str | None = Query(
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
    query: dict[str, Any] = {"user_id": current_user_id}
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


# NOTE: registered before the dynamic /{model_id} routes so "compare" is never
# captured as a model id (same precedent as GET /jobs above).
@router.post("/compare", response_model=ModelComparisonResponse)
async def compare_models(
    request: ModelComparisonRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Compare 2-5 of the current user's models side by side (issue #79).

    All models must belong to the same dataset and share a problem type so
    their scores are actually comparable. Returns 404 when any id is unknown
    (or owned by another user) and 400 on mixed datasets/problem types.
    """
    models: list[MLModel] = []
    missing: list[str] = []
    for model_id in request.model_ids:
        model = await MLModel.find_one(
            MLModel.model_id == model_id, MLModel.user_id == current_user_id
        )
        if model is None:
            missing.append(model_id)
        else:
            models.append(model)

    if missing:
        raise HTTPException(
            status_code=404, detail=f"Models not found: {', '.join(missing)}"
        )

    problem_types = {model.problem_type for model in models}
    if len(problem_types) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Models must share the same problem type to be compared "
                f"(got: {', '.join(sorted(problem_types))})"
            ),
        )
    dataset_ids = {model.dataset_id for model in models}
    if len(dataset_ids) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Models must be trained on the same dataset to be compared "
                f"(got: {', '.join(sorted(dataset_ids))})"
            ),
        )

    return ModelComparisonResponse(
        problem_type=models[0].problem_type,
        dataset_id=models[0].dataset_id,
        models=[
            ModelEvaluationSummary(
                model_id=model.model_id,
                name=model.name,
                algorithm=model.algorithm,
                problem_type=model.problem_type,
                cv_score=model.cv_score,
                test_score=model.test_score,
                metrics=_stored_scalar_metrics(model),
                created_at=model.created_at,
            )
            for model in models
        ],
    )


@router.get("/{model_id}/logs", response_model=TrainingLogsResponse)
async def get_training_logs(
    model_id: str,
    level: str | None = Query(None, pattern="^(info|warning|error)$"),
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


def _stored_scalar_metrics(model: MLModel) -> dict[str, float]:
    """Scalar metrics persisted at training time, as a plain float dict.

    Non-finite values are dropped: NaN/inf would serialize as invalid JSON
    (the artifact path is NaN-safe via _to_json_safe; keep this path symmetric).
    """
    stored: dict[str, float] = {}
    for key, value in (model.metrics or {}).items():
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        ):
            stored[key] = float(value)
    if model.cv_score is not None and math.isfinite(float(model.cv_score)):
        stored.setdefault("cv_score", float(model.cv_score))
    if model.test_score is not None and math.isfinite(float(model.test_score)):
        stored.setdefault("test_score", float(model.test_score))
    return stored


def _partial_evaluation_response(model: MLModel) -> ModelEvaluationResponse:
    """Stored-scalars-only payload for models without evaluation artifacts."""
    return ModelEvaluationResponse(
        model_id=model.model_id,
        model_name=model.name,
        algorithm=model.algorithm,
        problem_type=model.problem_type,
        partial=True,
        metrics=None,
        stored_metrics=_stored_scalar_metrics(model),
        confusion_matrix=None,
        roc_curve=None,
        pr_curve=None,
        feature_importance=model.feature_importance,
        ai_explanation=None,
        evaluated_at=datetime.now(UTC),
    )


async def _full_evaluation_response(
    model: MLModel, artifacts: dict[str, Any]
) -> ModelEvaluationResponse:
    """Compute the full evaluation payload from persisted held-out arrays."""
    problem_type = artifacts.get("problem_type") or model.problem_type
    y_test = artifacts["y_test"]
    y_pred = artifacts["y_pred"]
    y_proba = artifacts.get("y_proba")
    class_labels = artifacts.get("class_labels")
    is_classification = "classification" in str(problem_type).lower()

    metrics: ClassificationMetrics | RegressionMetrics
    if is_classification:
        metrics = MetricsService.compute_classification_metrics(
            y_test, y_pred, y_proba, class_labels
        )
        confusion = MetricsService.compute_confusion_matrix(
            y_test, y_pred, class_labels
        )
        labels = class_labels or confusion.labels
        roc = MetricsService.compute_roc_curves(y_test, y_proba, labels)
        pr = MetricsService.compute_pr_curves(y_test, y_proba, labels)
    else:
        metrics = MetricsService.compute_regression_metrics(y_test, y_pred)
        confusion = None
        roc = None
        pr = None

    # The explanation must never break the evaluation: the service already
    # degrades to its rule-based fallback internally, and this guard covers
    # anything unexpected beyond that.
    ai_explanation = None
    try:
        ai_explanation = await evaluation_explanation_service.generate_report_card(
            problem_type=str(problem_type),
            metrics=metrics,
            confusion_matrix=confusion,
            feature_importance=model.feature_importance,
            n_test_samples=len(y_test),
            model_name=model.name,
            algorithm=model.algorithm,
        )
    except Exception as exc:
        logger.warning(f"Report-card generation failed for {model.model_id}: {exc}")

    return ModelEvaluationResponse(
        model_id=model.model_id,
        model_name=model.name,
        algorithm=model.algorithm,
        problem_type=model.problem_type,
        partial=False,
        metrics=metrics,
        stored_metrics=_stored_scalar_metrics(model),
        confusion_matrix=confusion,
        roc_curve=roc,
        pr_curve=pr,
        feature_importance=model.feature_importance,
        ai_explanation=ai_explanation,
        evaluated_at=datetime.now(UTC),
    )


@router.get("/{model_id}/evaluation", response_model=ModelEvaluationResponse)
async def get_model_evaluation(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """
    Full evaluation payload for one model (issue #79).

    Computes detailed metrics, the confusion matrix, and ROC/PR curves from
    the held-out arrays persisted at training time, plus a plain-language AI
    report card (rule-based fallback when OpenAI is unavailable). For models
    without artifacts — trained before #79, or whose artifact load fails —
    returns ``partial=true`` with the stored scalar metrics; an owned,
    existing model never yields a 500.
    """
    model = await MLModel.find_one(
        MLModel.model_id == model_id, MLModel.user_id == current_user_id
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    artifacts = await MetricsService.load_evaluation_artifacts(model)
    if (
        not artifacts
        or artifacts.get("y_test") is None
        or artifacts.get("y_pred") is None
    ):
        return _partial_evaluation_response(model)

    try:
        return await _full_evaluation_response(model, artifacts)
    except Exception as exc:
        logger.error(
            f"Evaluation computation failed for {model_id}; "
            f"degrading to partial results: {exc}"
        )
        return _partial_evaluation_response(model)


# Interpretability endpoints (issue #80). These are two-segment paths, so the
# one-segment GET /{model_id} never captures them regardless of order; they are
# kept here next to the evaluation endpoint for readability.
@router.get(
    "/{model_id}/feature-importance", response_model=FeatureImportanceResponse
)
async def get_feature_importance(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """Global feature importance for a model (issue #80).

    Returns model-native importance (ranked) plus SHAP-based importance when
    the model type is SHAP-supported and a summary was computed at training
    time. ``partial=true`` only when neither is available (e.g. an unsupported
    model trained before any importance was captured). 404 for unknown/foreign
    models; never 500 for an owned model.
    """
    model = await MLModel.find_one(
        MLModel.model_id == model_id, MLModel.user_id == current_user_id
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    native = _rank_importance(model.feature_importance)

    shap_importance = None
    explainer_type = model.shap_explainer_type
    shap_artifacts = await MetricsService.load_shap_artifacts(model)
    if shap_artifacts:
        shap_importance = _rank_importance(shap_artifacts.get("shap_importance"))
        explainer_type = shap_artifacts.get("explainer_type", explainer_type)

    partial = not native and not shap_importance
    message = None
    if partial:
        message = (
            "No feature importance is available for this model. It may have been "
            "trained before interpretability was added, or its algorithm exposes "
            "no importance scores."
        )
    elif not shap_importance:
        message = (
            "SHAP-based importance is unavailable for this model; showing "
            "model-native feature importance."
        )

    return FeatureImportanceResponse(
        model_id=model_id,
        partial=partial,
        explainer_type=explainer_type,
        native_importance=native,
        shap_importance=shap_importance,
        message=message,
    )


@router.get("/{model_id}/shap", response_model=ShapSummaryResponse)
async def get_shap_summary(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """SHAP summary-plot data for a model (issue #80).

    Returns the mean |SHAP| per feature (ranked) plus a plain-language summary
    of the top drivers, computed at training time on the held-out set. For
    models trained before #80 or whose algorithm isn't SHAP-supported,
    ``partial=true`` with an explanatory message and empty importance — the
    endpoint never 500s for an owned model. 404 for unknown/foreign models.
    """
    model = await MLModel.find_one(
        MLModel.model_id == model_id, MLModel.user_id == current_user_id
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    shap_artifacts = await MetricsService.load_shap_artifacts(model)
    if not shap_artifacts or not shap_artifacts.get("shap_importance"):
        return ShapSummaryResponse(
            model_id=model_id,
            partial=True,
            explainer_type=model.shap_explainer_type,
            problem_type=model.problem_type,
            message=(
                "SHAP interpretability is unavailable for this model. Tree and "
                "linear models compute SHAP at training time; other algorithms "
                "(and models trained before this feature) fall back to "
                "model-native feature importance."
            ),
            evaluated_at=datetime.now(UTC),
        )

    importance: dict[str, float] = shap_artifacts["shap_importance"]
    return ShapSummaryResponse(
        model_id=model_id,
        partial=False,
        explainer_type=shap_artifacts.get("explainer_type"),
        problem_type=model.problem_type,
        feature_importance=_rank_importance(importance),
        base_value=shap_artifacts.get("base_value"),
        plain_language=_interpretability_service.top_drivers_text(importance),
        evaluated_at=datetime.now(UTC),
    )


@router.get("/{model_id}/tuning-results")
async def get_tuning_results(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    """Hyperparameter-tuning visualization data for a model (issue #77).

    Returns the per-algorithm tuning payload captured at training time — best
    params, parameter importance, optimization history, and improvement over the
    default hyperparameters. For models trained without tuning (the default, and
    every pre-#77 model), ``partial=true`` with an explanatory message and no
    results — the endpoint never 500s for an owned model. 404 for
    unknown/foreign models. Registered before ``/{model_id}`` so the literal
    path segment wins over the catch-all id route.
    """
    model = await MLModel.find_one(
        MLModel.model_id == model_id, MLModel.user_id == current_user_id
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if not model.tuning_results:
        return {
            "model_id": model_id,
            "partial": True,
            "tuning_strategy": None,
            "improvement_from_tuning": None,
            "results": {},
            "message": (
                "Hyperparameter tuning was not run for this model. Enable it via "
                "training_config.enable_tuning to optimize hyperparameters."
            ),
        }

    return {
        "model_id": model_id,
        "partial": False,
        "tuning_strategy": model.tuning_strategy,
        "improvement_from_tuning": model.improvement_from_tuning,
        "results": model.tuning_results,
        "message": None,
    }


@router.get("/{model_id}/errors", response_model=ErrorAnalysisResponse)
async def get_error_analysis(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """Error analysis for a model (issue #81).

    Surfaces error distribution, commonly-confused class pairs, high-error
    feature segments, error clusters, decision-tree error patterns, a browsable
    list of error cases, and AI improvement suggestions (rule-based fallback when
    OpenAI is unavailable). Computed on-demand from the held-out arrays + feature
    matrix persisted at training time. Models trained before #81 (no feature
    matrix) — or whose artifacts are missing — degrade to ``partial=true`` with
    distribution / confusion pairs / cases only; an owned model never 500s. 404
    for unknown/foreign models. Registered before ``/{model_id}`` so the literal
    path segment wins over the catch-all id route.
    """
    model = await MLModel.find_one(
        MLModel.model_id == model_id, MLModel.user_id == current_user_id
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    artifacts = await MetricsService.load_evaluation_artifacts(model)
    if (
        not artifacts
        or artifacts.get("y_test") is None
        or artifacts.get("y_pred") is None
    ):
        return ErrorAnalysisResponse(
            model_id=model_id,
            model_name=model.name,
            algorithm=model.algorithm,
            problem_type=model.problem_type,
            partial=True,
            message=(
                "Error analysis is unavailable for this model. It may have been "
                "trained before evaluation artifacts were captured."
            ),
            suggestions=[],
            evaluated_at=datetime.now(UTC),
        )

    has_matrix = bool(artifacts.get("X_test")) and bool(artifacts.get("feature_names"))
    data = error_analysis_service.analyze(
        problem_type=model.problem_type,
        y_test=artifacts["y_test"],
        y_pred=artifacts["y_pred"],
        y_proba=artifacts.get("y_proba"),
        class_labels=artifacts.get("class_labels"),
        x_test=artifacts.get("X_test"),
        feature_names=artifacts.get("feature_names"),
    )
    suggestions, generated_by = await error_analysis_service.generate_suggestions(
        data, problem_type=model.problem_type, algorithm=model.algorithm
    )

    message = None
    if not data.has_feature_matrix:
        message = (
            "This model has no stored feature matrix (trained before #81), so "
            "high-error segments, clusters, and patterns are unavailable. "
            "Distribution, confusion pairs, and error cases are still shown."
        )
    return ErrorAnalysisResponse(
        model_id=model_id,
        model_name=model.name,
        algorithm=model.algorithm,
        problem_type=model.problem_type,
        partial=not has_matrix,
        distribution=data.distribution,
        confusion_pairs=data.confusion_pairs,
        segments=data.segments,
        clusters=data.clusters,
        patterns=data.patterns,
        cases=data.cases,
        suggestions=suggestions,
        suggestions_generated_by=generated_by,
        message=message,
        evaluated_at=datetime.now(UTC),
    )


def _version_entry(model: MLModel, version_number: int) -> ModelVersionEntry:
    """Map an ``MLModel`` to a version-browser row (issue #78)."""
    return ModelVersionEntry(
        model_id=model.model_id,
        version_number=version_number,
        name=model.name,
        algorithm=model.algorithm,
        problem_type=model.problem_type,
        cv_score=model.cv_score,
        test_score=model.test_score,
        is_production=model.is_production,
        is_active=model.is_active,
        created_at=model.created_at,
        promoted_at=model.promoted_at,
        dataset_id=model.dataset_id,
        dataset_version_id=model.dataset_version_id,
        parent_model_id=model.parent_model_id,
        feature_names=model.feature_names,
        environment_metadata=model.environment_metadata,
        version_notes=model.version_notes,
    )


@router.get("/{model_id}/versions", response_model=ModelVersionListResponse)
async def list_model_versions(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """List a model's version history (issue #78).

    A version family is every model the user trained on the same dataset under
    the same name; versions are ordered oldest → newest with sequential version
    numbers, and each row carries its lineage (dataset version, features,
    environment). 404 for unknown/foreign models. Registered before the
    catch-all ``/{model_id}`` so the literal sub-path wins.
    """
    try:
        family = await model_versioning_service.list_family(model_id, current_user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc

    versions = [
        _version_entry(model, idx) for idx, model in enumerate(family, start=1)
    ]
    production_id = next(
        (m.model_id for m in family if m.is_production), None
    )
    anchor = next((m for m in family if m.model_id == model_id), None)
    if anchor is None:  # anchor deleted between the two reads in list_family
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelVersionListResponse(
        model_id=model_id,
        dataset_id=anchor.dataset_id,
        name=anchor.name,
        total=len(versions),
        production_model_id=production_id,
        versions=versions,
    )


@router.post("/{model_id}/promote", response_model=PromoteVersionResponse)
async def promote_model_version(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """Promote a version to production, demoting its siblings (issue #78).

    Rolling back is the same operation applied to an older version. 404 for
    unknown/foreign models.
    """
    try:
        promoted, demoted = await model_versioning_service.promote_to_production(
            model_id, current_user_id
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail="Model not found") from exc

    return PromoteVersionResponse(
        model_id=promoted.model_id,
        is_production=promoted.is_production,
        promoted_at=promoted.promoted_at,
        demoted_model_ids=demoted,
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


def _required_input_features(feature_engineer, ml_model) -> list[str]:
    """The raw input columns a record must supply.

    When a feature engineer was fitted at training time, the model consumes the
    *engineered* columns but callers supply the *raw* columns the engineer was
    fitted on (numeric + categorical). Without a feature engineer the model was
    trained directly on ``feature_names``.
    """
    if feature_engineer is not None:
        raw = list(getattr(feature_engineer, "numeric_features", []) or []) + list(
            getattr(feature_engineer, "categorical_features", []) or []
        )
        if raw:
            return raw
    return list(ml_model.feature_names)


def _categorical_options(feature_engineer, column: str) -> list[str] | None:
    """Recover the allowed values for a categorical column from the fitted
    encoder, so the form can render a dropdown. Returns None if unrecoverable."""
    try:
        transformers = getattr(feature_engineer, "transformers", {}) or {}
        if getattr(feature_engineer.config, "encoding_method", None) == "onehot":
            encoder = transformers.get("encoder")
            if encoder is not None:
                idx = feature_engineer.categorical_features.index(column)
                return [str(c) for c in encoder.categories_[idx]]
        label_encoders = transformers.get("label_encoders", {}) or {}
        encoder = label_encoders.get(column)
        if encoder is not None:
            return [str(c) for c in encoder.classes_]
    except Exception:
        return None
    return None


def _extract_class_labels(model, problem_type: str) -> list[str] | None:
    """Ordered class labels from the fitted estimator (classification only)."""
    try:
        if "classification" not in str(problem_type):
            return None
        raw = getattr(model, "classes_", None)
        if raw is None:
            return None
        return [str(c) for c in raw]
    except Exception:
        return None


@router.get("/{model_id}/features", response_model=ModelFeaturesResponse)
async def get_model_features(
    model_id: str, current_user_id: str = Depends(get_current_user_id)
):
    """
    Return the raw input feature schema for a model (issue #82).

    Drives the auto-generated single-prediction form: numeric fields, the
    categorical fields with their allowed values (when recoverable from the
    fitted encoder), plus class labels and problem type. Degrades to the stored
    ``feature_names`` when the model artifacts cannot be loaded.
    """
    ml_model = await MLModel.find_one(
        MLModel.model_id == model_id, MLModel.user_id == current_user_id
    )
    if not ml_model:
        raise HTTPException(status_code=404, detail="Model not found")

    feature_engineer = None
    class_labels: list[str] | None = None
    storage_service = ModelStorageService()
    try:
        model, feature_engineer = await storage_service.load_model(
            model_id, current_user_id
        )
        class_labels = _extract_class_labels(model, ml_model.problem_type)
    except Exception as exc:  # noqa: BLE001 - degrade, never 500 on the form
        logger.warning(
            "Could not load artifacts for %s features; "
            "falling back to stored feature_names: %s",
            model_id,
            exc,
        )

    features: list[FeatureDescriptor] = []
    if feature_engineer is not None and (
        getattr(feature_engineer, "numeric_features", None)
        or getattr(feature_engineer, "categorical_features", None)
    ):
        for name in feature_engineer.numeric_features or []:
            features.append(FeatureDescriptor(name=name, type="number"))
        for name in feature_engineer.categorical_features or []:
            features.append(
                FeatureDescriptor(
                    name=name,
                    type="categorical",
                    options=_categorical_options(feature_engineer, name),
                )
            )
    else:
        # No fitted engineer (or none persisted): the model was trained directly
        # on feature_names. Types are unknown, default to numeric inputs.
        features = [
            FeatureDescriptor(name=name, type="number")
            for name in ml_model.feature_names
        ]

    return ModelFeaturesResponse(
        features=features,
        class_labels=class_labels,
        problem_type=ml_model.problem_type,
        target_column=ml_model.target_column,
    )


@router.post("/{model_id}/predict", response_model=PredictResponse)
async def predict(
    model_id: str,
    request: PredictRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Make predictions using a trained model.

    Reuses the exact feature pipeline fitted at training time (issue #82) and
    rejects records missing required input features with a clear 422.
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
    if not ml_model:
        raise HTTPException(status_code=404, detail="Model not found")

    if not request.data:
        raise HTTPException(status_code=422, detail="No input records provided")

    # Validate that every record carries the required raw input features.
    required = _required_input_features(feature_engineer, ml_model)
    missing = sorted(
        {f for record in request.data for f in required if f not in record}
    )
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required feature(s): {', '.join(missing)}",
        )

    # Convert input data to DataFrame
    input_df = pd.DataFrame(request.data)

    # Apply the fitted pipeline and run inference. A bad feature value (e.g. an
    # unknown category the encoder was never fitted on) surfaces as a sklearn
    # ValueError — return it as a clear 422 rather than a 500 traceback leak.
    try:
        if feature_engineer:
            input_df = await feature_engineer.transform(input_df)

        # Make predictions
        predictions = model.predict(input_df)

        # Compute probabilities whenever the (now calibrated) classifier
        # supports them — they drive confidence + low-confidence flags even if
        # the caller didn't ask to see the full probability vectors (#83). The
        # `probabilities` field itself is only returned when requested (#82).
        proba_list = None
        if hasattr(model, "predict_proba"):
            try:
                proba_list = model.predict_proba(input_df).tolist()
            except Exception:  # noqa: BLE001 - probabilities are optional
                proba_list = None
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid feature value(s): {exc}")

    # Convert predictions to list
    if isinstance(predictions, np.ndarray):
        predictions = predictions.tolist()

    # Confidence / uncertainty / explanation enrichment (issue #83).
    enricher = _prediction_enricher
    confidence, low_confidence = enricher.per_record_confidence(proba_list)
    prediction_intervals = enricher.prediction_intervals(
        predictions, ml_model.residual_std
    )
    explanations = None
    if request.include_explanations:
        explanations = enricher.explanations(
            model,
            input_df,
            ml_model.feature_names,
            predictions,
            ml_model.problem_type,
            feature_importance=ml_model.feature_importance,
        )

    return PredictResponse(
        predictions=predictions,
        probabilities=proba_list if request.include_probabilities else None,
        confidence=confidence,
        class_labels=_extract_class_labels(model, ml_model.problem_type),
        feature_names=ml_model.feature_names,
        model_info={
            "model_id": model_id,
            "algorithm": ml_model.algorithm,
            "problem_type": ml_model.problem_type,
            "target_column": ml_model.target_column,
        },
        low_confidence=low_confidence,
        is_calibrated=bool(getattr(ml_model, "is_calibrated", False)),
        calibration_method=getattr(ml_model, "calibration_method", None),
        confidence_threshold=enricher.threshold,
        prediction_intervals=prediction_intervals,
        explanations=explanations,
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
    model.updated_at = datetime.now(UTC)
    await model.save()

    return {"message": f"Model {model_id} deactivated"}
