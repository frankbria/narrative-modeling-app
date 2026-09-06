"""
A/B Testing API routes
"""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.nextauth_auth import get_current_user_id
from app.models.ab_test import ABTest, ExperimentStatus
from app.services.ab_testing import ABTestingService

router = APIRouter(prefix="/ab-testing", tags=["ab-testing"])


# Request/Response Models
class CreateExperimentRequest(BaseModel):
    name: str = Field(..., description="Experiment name")
    description: str | None = Field(None, description="Experiment description")
    model_ids: list[str] = Field(..., description="List of model IDs to test")
    primary_metric: str = Field(default="accuracy", description="Primary metric to optimize")
    secondary_metrics: list[str] = Field(default_factory=list)
    traffic_split: list[float] | None = Field(None, description="Traffic percentage for each variant")
    min_sample_size: int = Field(default=1000, description="Minimum samples per variant")
    confidence_level: float = Field(default=0.95, description="Statistical confidence level")
    test_duration_hours: int | None = Field(None, description="Maximum test duration")


class ExperimentResponse(BaseModel):
    experiment_id: str
    name: str
    description: str | None
    status: ExperimentStatus
    variants: list[dict[str, Any]]
    primary_metric: str
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    winner_variant_id: str | None
    statistical_significance: float | None
    lift_percentage: float | None


class VariantAssignmentResponse(BaseModel):
    experiment_id: str
    variant_id: str
    variant_name: str
    model_id: str


class ExperimentMetricsResponse(BaseModel):
    experiment_id: str
    name: str
    status: str
    duration: float | None
    total_predictions: int
    variants: list[dict[str, Any]]
    comparison: dict[str, Any] | None


# API Routes
@router.post("/experiments", response_model=ExperimentResponse)
async def create_experiment(
    request: CreateExperimentRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a new A/B test experiment"""
    
    try:
        experiment = await ABTestingService.create_experiment(
            name=request.name,
            model_ids=request.model_ids,
            user_id=current_user_id,
            primary_metric=request.primary_metric,
            traffic_split=request.traffic_split,
            description=request.description
        )
        
        # Update additional settings
        experiment.secondary_metrics = request.secondary_metrics
        experiment.min_sample_size = request.min_sample_size
        experiment.confidence_level = request.confidence_level
        experiment.test_duration_hours = request.test_duration_hours
        await experiment.save()
        
        return ExperimentResponse(
            experiment_id=experiment.experiment_id,
            name=experiment.name,
            description=experiment.description,
            status=experiment.status,
            variants=[v.dict() for v in experiment.variants],
            primary_metric=experiment.primary_metric,
            created_at=experiment.created_at,
            started_at=experiment.started_at,
            ended_at=experiment.ended_at,
            winner_variant_id=experiment.winner_variant_id,
            statistical_significance=experiment.statistical_significance,
            lift_percentage=experiment.lift_percentage
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/experiments", response_model=list[ExperimentResponse])
async def list_experiments(
    status: ExperimentStatus | None = Query(None, description="Filter by status"),
    current_user_id: str = Depends(get_current_user_id)
):
    """List all experiments for the current user"""
    
    query = {"user_id": current_user_id}
    if status:
        query["status"] = status
    
    experiments = await ABTest.find(query).sort("-created_at").to_list()
    
    return [
        ExperimentResponse(
            experiment_id=exp.experiment_id,
            name=exp.name,
            description=exp.description,
            status=exp.status,
            variants=[v.dict() for v in exp.variants],
            primary_metric=exp.primary_metric,
            created_at=exp.created_at,
            started_at=exp.started_at,
            ended_at=exp.ended_at,
            winner_variant_id=exp.winner_variant_id,
            statistical_significance=exp.statistical_significance,
            lift_percentage=exp.lift_percentage
        )
        for exp in experiments
    ]


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get details of a specific experiment"""
    
    experiment = await ABTest.find_one({
        "experiment_id": experiment_id,
        "user_id": current_user_id
    })
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    return ExperimentResponse(
        experiment_id=experiment.experiment_id,
        name=experiment.name,
        description=experiment.description,
        status=experiment.status,
        variants=[v.dict() for v in experiment.variants],
        primary_metric=experiment.primary_metric,
        created_at=experiment.created_at,
        started_at=experiment.started_at,
        ended_at=experiment.ended_at,
        winner_variant_id=experiment.winner_variant_id,
        statistical_significance=experiment.statistical_significance,
        lift_percentage=experiment.lift_percentage
    )


@router.post("/experiments/{experiment_id}/start")
async def start_experiment(
    experiment_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Start an experiment"""
    
    experiment = await ABTest.find_one({
        "experiment_id": experiment_id,
        "user_id": current_user_id
    })
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if experiment.status != ExperimentStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Experiment must be in draft status to start")
    
    if not experiment.is_valid_configuration():
        raise HTTPException(status_code=400, detail="Invalid experiment configuration")
    
    experiment.status = ExperimentStatus.RUNNING
    experiment.started_at = datetime.now(UTC)
    await experiment.save()
    
    return {"message": "Experiment started successfully"}


@router.post("/experiments/{experiment_id}/pause")
async def pause_experiment(
    experiment_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Pause a running experiment"""
    
    experiment = await ABTest.find_one({
        "experiment_id": experiment_id,
        "user_id": current_user_id
    })
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if experiment.status != ExperimentStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Only running experiments can be paused")
    
    experiment.status = ExperimentStatus.PAUSED
    await experiment.save()
    
    return {"message": "Experiment paused successfully"}


@router.post("/experiments/{experiment_id}/complete")
async def complete_experiment(
    experiment_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Manually complete an experiment"""
    
    experiment = await ABTest.find_one({
        "experiment_id": experiment_id,
        "user_id": current_user_id
    })
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if experiment.status not in [ExperimentStatus.RUNNING, ExperimentStatus.PAUSED]:
        raise HTTPException(status_code=400, detail="Experiment must be running or paused to complete")
    
    experiment = await ABTestingService.complete_experiment(experiment)
    
    return {
        "message": "Experiment completed successfully",
        "winner_variant_id": experiment.winner_variant_id,
        "statistical_significance": experiment.statistical_significance,
        "lift_percentage": experiment.lift_percentage
    }


@router.get("/experiments/{experiment_id}/assign-variant", response_model=VariantAssignmentResponse)
async def assign_variant(
    experiment_id: str,
    user_identifier: str = Query(..., description="User identifier for consistent assignment"),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get variant assignment for a user, within the caller's own experiment."""

    experiment = await ABTest.find_one({
        "experiment_id": experiment_id,
        "user_id": current_user_id,
        "status": ExperimentStatus.RUNNING
    })
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Active experiment not found")
    
    variant = ABTestingService.assign_variant(experiment, user_identifier)
    
    return VariantAssignmentResponse(
        experiment_id=experiment.experiment_id,
        variant_id=variant.variant_id,
        variant_name=variant.name,
        model_id=variant.model_id
    )


@router.get("/experiments/{experiment_id}/metrics", response_model=ExperimentMetricsResponse)
async def get_experiment_metrics(
    experiment_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """Get detailed metrics for an experiment"""
    
    experiment = await ABTest.find_one({
        "experiment_id": experiment_id,
        "user_id": current_user_id
    })
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    metrics = await ABTestingService.get_experiment_metrics(experiment)
    
    return ExperimentMetricsResponse(**metrics)


@router.post("/track-prediction")
async def track_prediction(
    experiment_id: str,
    variant_id: str,
    latency_ms: float,
    success: bool = True,
    custom_metrics: dict[str, float] | None = None,
    current_user_id: str = Depends(get_current_user_id)
):
    """Track a prediction for a variant of the caller's own experiment.

    Ownership is established here rather than in the service:
    `ABTestingService.track_prediction` looks the experiment up by id alone and
    returns silently on a miss, which is deliberate for non-blocking tracking
    but cannot double as an authorization boundary.
    """

    experiment = await ABTest.find_one({
        "experiment_id": experiment_id,
        "user_id": current_user_id
    })
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    await ABTestingService.track_prediction(
        experiment_id=experiment_id,
        variant_id=variant_id,
        latency_ms=latency_ms,
        success=success,
        custom_metrics=custom_metrics
    )
    
    return {"message": "Prediction tracked successfully"}