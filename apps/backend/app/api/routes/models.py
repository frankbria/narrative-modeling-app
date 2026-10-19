"""
Model API routes.

Provides CRUD endpoints for legacy ModelConfig documents using ModelService.

The train / deploy / performance endpoints on this surface never did real
work (the legacy train reported status="training" but never trained), so they
return 410 Gone (#274). Real training/serving lives on /api/v1/ml/.

Endpoints:
- POST /models/train - **410 Gone** → use POST /api/v1/ml/train
- GET /models/{model_id} - Retrieve specific ModelConfig
- GET /models - List models with filtering (dataset_id, status)
- PUT /models/{model_id} - Update ModelConfig
- GET /models/{model_id}/performance - **410 Gone** → use GET /api/v1/ml/{id}/evaluation
- PUT /models/{model_id}/deploy - **410 Gone** → use PUT /api/v1/ml/{id}/deploy
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.nextauth_auth import get_current_user_id
from app.models.model import DeploymentConfig, ModelConfig, ModelStatus
from app.schemas.model import (
    DeploymentConfigResponse,
    FeatureConfigResponse,
    ModelConfigResponse,
    ModelListItem,
    ModelListResponse,
    ModelUpdateRequest,
    PerformanceMetricsResponse,
    TrainingConfigResponse,
)
from app.services.exceptions import NotFoundError
from app.services.model_service import ModelService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/train", status_code=status.HTTP_410_GONE)
async def train_model():
    """Removed (#274). The legacy ModelConfig train endpoint reported
    ``status="training"`` but never actually trained a model.

    Real AutoML training lives at ``POST /api/v1/ml/train``.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="POST /api/v1/models/train is no longer available. "
               "Use POST /api/v1/ml/train for real model training.",
    )


def _deployment_response(config: DeploymentConfig | None) -> DeploymentConfigResponse:
    """A model with no deployment config reads as one with the defaults (not deployed, no predictions)."""
    return DeploymentConfigResponse(**(config or DeploymentConfig()).model_dump())


def _model_response(model: ModelConfig) -> ModelConfigResponse:
    """The API view of a ModelConfig, shared by GET and PUT /models/{model_id}."""
    return ModelConfigResponse(
        model_id=model.model_id,
        user_id=model.user_id,
        dataset_id=model.dataset_id,
        name=model.name,
        description=model.description,
        problem_type=model.problem_type.value,
        algorithm=model.algorithm,
        hyperparameters=model.hyperparameters.model_dump(),
        feature_config=FeatureConfigResponse(**model.feature_config.model_dump()),
        training_config=TrainingConfigResponse(**model.training_config.model_dump()),
        performance_metrics=PerformanceMetricsResponse(**model.performance_metrics.model_dump()),
        model_path=model.model_path,
        model_file_url=str(model.model_file_url) if model.model_file_url else None,
        feature_transformer_path=model.feature_transformer_path,
        model_size=model.model_size,
        status=model.status.value,
        deployment_config=_deployment_response(model.deployment_config),
        version=model.version,
        is_active=model.is_active,
        parent_model_id=model.parent_model_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        trained_at=model.trained_at,
        last_used_at=model.last_used_at,
        tags=model.tags,
        notes=model.notes
    )


@router.get("/{model_id}", response_model=ModelConfigResponse)
async def get_model(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Retrieve specific model configuration by ID.

    Args:
        model_id: Unique model identifier
        current_user_id: Authenticated user ID

    Returns:
        Complete ModelConfig details

    Raises:
        HTTPException: 404 if model not found or user doesn't own model
    """
    try:
        model_service = ModelService()
        # Ownership check is now enforced in the service layer
        model = await model_service.get_model_config(model_id, user_id=current_user_id)

        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found"
            )

        return _model_response(model)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve model: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model: {str(e)}"
        )


async def _page_for_dataset(
    model_service: ModelService,
    user_id: str,
    dataset_id: str,
    status_filter: ModelStatus | None,
    skip: int,
    limit: int,
) -> tuple[list[ModelConfig], int]:
    """One page of the caller's models for a dataset. The service has no
    dataset-and-user query, so this fetches the dataset's models and filters in memory."""
    models = [
        m for m in await model_service.list_models_by_dataset(dataset_id)
        if m.user_id == user_id and status_filter in (None, m.status)
    ]
    return models[skip:skip + limit], len(models)


async def _page_for_user(
    model_service: ModelService,
    user_id: str,
    status_filter: ModelStatus | None,
    skip: int,
    limit: int,
) -> tuple[list[ModelConfig], int]:
    """One page of the caller's models, paginated in the database."""
    if status_filter == ModelStatus.DEPLOYED:
        page = await model_service.get_deployed_models(user_id, skip=skip, limit=limit)
    elif status_filter:
        page = await model_service.list_for_user(user_id, skip=skip, limit=limit, status=status_filter)
    else:
        page = await model_service.list_model_configs(user_id, skip=skip, limit=limit)
    count_filters = {"status": status_filter} if status_filter else {}
    return page, await model_service.count_for_user(user_id, **count_filters)


@router.get("", response_model=ModelListResponse)
async def list_models(
    current_user_id: str = Depends(get_current_user_id),
    dataset_id: str | None = Query(None, description="Filter by dataset ID"),
    status_filter: ModelStatus | None = Query(
        None, alias="status", description="Filter by status (training, trained, deployed, archived, failed)"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    List models with optional filtering and pagination.

    Filters:
    - dataset_id: Show only models trained on specific dataset
    - status: Show only models with specific status; any other value is a 422

    Results are sorted by created_at (newest first).

    Args:
        current_user_id: Authenticated user ID
        dataset_id: Optional dataset filter
        status_filter: Optional status filter
        page: Page number (1-indexed)
        limit: Items per page (max 100)

    Returns:
        List of models with pagination metadata
    """
    try:
        model_service = ModelService()
        skip = (page - 1) * limit
        if dataset_id:
            paginated_models, total = await _page_for_dataset(
                model_service, current_user_id, dataset_id, status_filter, skip, limit
            )
        else:
            paginated_models, total = await _page_for_user(
                model_service, current_user_id, status_filter, skip, limit
            )

        # Convert to list items
        model_items = [
            ModelListItem(
                model_id=model.model_id,
                name=model.name,
                description=model.description,
                problem_type=model.problem_type.value,
                algorithm=model.algorithm,
                status=model.status.value,
                test_score=model.performance_metrics.test_score,
                is_active=model.is_active,
                is_deployed=model.deployment_config.is_deployed if model.deployment_config else False,
                created_at=model.created_at,
                trained_at=model.trained_at
            )
            for model in paginated_models
        ]

        return ModelListResponse(
            models=model_items,
            total=total
        )

    except Exception as e:
        logger.error(f"Failed to list models: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}"
        )


async def _updated_model_response(
    model_id: str, user_id: str, request: ModelUpdateRequest
) -> ModelConfigResponse:
    """Apply the fields the request sets and return the model.

    The service checks ownership and raises NotFoundError for a model that is missing or not the caller's.
    """
    updated_model = await ModelService().update_model_config(
        model_id=model_id, user_id=user_id, **request.model_dump(exclude_none=True)
    )
    return _model_response(updated_model)


@router.put("/{model_id}", response_model=ModelConfigResponse)
async def update_model(
    model_id: str,
    request: ModelUpdateRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Update model configuration metadata.

    Allows updating:
    - name: Human-readable model name
    - description: Model description
    - tags: Organization tags
    - notes: Additional notes

    Does NOT allow updating training configuration or hyperparameters
    after training is complete.

    Args:
        model_id: Model identifier
        request: Fields to update
        current_user_id: Authenticated user ID

    Returns:
        Updated ModelConfig

    Raises:
        HTTPException: 404 if the model is not found or is not the caller's
    """
    try:
        return await _updated_model_response(model_id, current_user_id, request)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update model: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update model: {str(e)}"
        )


@router.get("/{model_id}/performance", status_code=status.HTTP_410_GONE)
async def get_model_performance(model_id: str):
    """Removed (#274). Legacy ModelConfig performance metrics were only ever
    zero-valued placeholders because the legacy train endpoint never trained.

    Real model metrics live at ``GET /api/v1/ml/{model_id}/evaluation``.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="GET /api/v1/models/{model_id}/performance is no longer available. "
               "Use GET /api/v1/ml/{model_id}/evaluation for real metrics.",
    )


@router.put("/{model_id}/deploy", status_code=status.HTTP_410_GONE)
async def deploy_model(model_id: str):
    """Removed (#274). This deployed a legacy ModelConfig that the real
    training flow never creates, so it 404'd for every real model.

    Real deployment lives at ``PUT /api/v1/ml/{model_id}/deploy`` (#84).
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="PUT /api/v1/models/{model_id}/deploy is no longer available. "
               "Use PUT /api/v1/ml/{model_id}/deploy to deploy a trained model.",
    )
