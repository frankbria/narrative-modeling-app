"""
Model API routes.

Provides endpoints for managing ML model configurations using ModelService.
Implements Story 12.1: API Integration for New Models (Model portion).

Endpoints:
- POST /models/train - Create and initiate model training
- GET /models/{model_id} - Retrieve specific model configuration
- GET /models - List models with filtering (user_id, dataset_id, status)
- PUT /models/{model_id} - Update model configuration
- GET /models/{model_id}/performance - Retrieve performance metrics
- PUT /models/{model_id}/deploy - Deploy model to endpoint
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.nextauth_auth import get_current_user_id
from app.models.model import ModelStatus
from app.schemas.model import (
    ModelConfigResponse,
    ModelDeployRequest,
    ModelDeployResponse,
    ModelListItem,
    ModelListResponse,
    ModelTrainRequest,
    ModelTrainResponse,
    ModelUpdateRequest,
    PerformanceMetricsResponse,
)
from app.services.exceptions import NotFoundError, PermissionDeniedError
from app.services.model_service import ModelService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/train", response_model=ModelTrainResponse, status_code=status.HTTP_201_CREATED)
async def train_model(
    request: ModelTrainRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Create model configuration and initiate training.

    This endpoint creates a ModelConfig with TRAINING status initially,
    then triggers background training process that updates status to
    TRAINED/FAILED.

    Args:
        request: Model training configuration
        current_user_id: Authenticated user ID

    Returns:
        ModelTrainResponse with model_id and initial status

    Raises:
        HTTPException: 400 for invalid configuration, 404 if dataset not found
    """
    try:
        # Verify dataset exists
        import time
        import uuid

        from app.models.model import (
            FeatureConfig,
            HyperparameterConfig,
            PerformanceMetrics,
            TrainingConfig,
        )
        from app.services.dataset_service import DatasetService

        dataset_service = DatasetService()
        dataset = await dataset_service.get_dataset(request.dataset_id)

        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {request.dataset_id} not found"
            )

        # Create model configuration
        model_service = ModelService()
        model_id = f"model_{uuid.uuid4().hex}"

        start_time = time.time()

        # Build configurations from request
        feature_config = FeatureConfig(
            feature_names=request.feature_columns,
            target_column=request.target_column,
            numeric_features=request.feature_columns  # Simplified for now
        )

        training_config = TrainingConfig(
            train_test_split=request.train_test_split,
            cv_folds=request.cv_folds,
            validation_strategy=request.validation_strategy,
            training_time=0.0,  # Will be updated during actual training
            n_samples_train=int(dataset.num_rows * request.train_test_split),
            n_samples_test=int(dataset.num_rows * (1 - request.train_test_split)),
            early_stopping=request.early_stopping,
            optimization_metric=request.optimization_metric
        )

        # Initialize with placeholder metrics (will be updated during training)
        performance_metrics = PerformanceMetrics(
            cv_score=0.0,
            test_score=0.0
        )

        hyperparameters = HyperparameterConfig(
            **request.hyperparameters if request.hyperparameters else {}
        )

        # Create model config with TRAINING status
        _ = await model_service.create_model_config(
            user_id=current_user_id,
            dataset_id=request.dataset_id,
            model_id=model_id,
            name=request.name,
            description=request.description,
            problem_type=request.problem_type,  # Already validated as ProblemType by Pydantic
            algorithm=request.algorithm,
            feature_config=feature_config,
            training_config=training_config,
            performance_metrics=performance_metrics,
            model_path=f"models/{model_id}.pkl",
            model_size=0,  # Will be updated after training
            hyperparameters=hyperparameters
        )

        training_time = time.time() - start_time

        # Return training response
        return ModelTrainResponse(
            model_id=model_id,
            status="training",
            message="Model training initiated successfully",
            training_time=training_time,
            performance_metrics=PerformanceMetricsResponse(
                cv_score=0.0,
                test_score=0.0
            )
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 404 for dataset not found)
        raise
    except ValueError as e:
        logger.error(f"Model training failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Model training failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate model training: {str(e)}"
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

        # Convert to response schema
        from app.schemas.model import (
            DeploymentConfigResponse,
            FeatureConfigResponse,
            PerformanceMetricsResponse,
            TrainingConfigResponse,
        )

        return ModelConfigResponse(
            model_id=model.model_id,
            user_id=model.user_id,
            dataset_id=model.dataset_id,
            name=model.name,
            description=model.description,
            problem_type=model.problem_type.value,
            algorithm=model.algorithm,
            hyperparameters=model.hyperparameters.model_dump(),
            feature_config=FeatureConfigResponse(
                feature_names=model.feature_config.feature_names,
                target_column=model.feature_config.target_column,
                engineered_features=model.feature_config.engineered_features,
                dropped_features=model.feature_config.dropped_features,
                feature_importance=model.feature_config.feature_importance,
                numeric_features=model.feature_config.numeric_features,
                categorical_features=model.feature_config.categorical_features,
                datetime_features=model.feature_config.datetime_features
            ),
            training_config=TrainingConfigResponse(
                train_test_split=model.training_config.train_test_split,
                cv_folds=model.training_config.cv_folds,
                validation_strategy=model.training_config.validation_strategy,
                training_time=model.training_config.training_time,
                n_samples_train=model.training_config.n_samples_train,
                n_samples_test=model.training_config.n_samples_test,
                early_stopping=model.training_config.early_stopping,
                optimization_metric=model.training_config.optimization_metric
            ),
            performance_metrics=PerformanceMetricsResponse(
                cv_score=model.performance_metrics.cv_score,
                test_score=model.performance_metrics.test_score,
                accuracy=model.performance_metrics.accuracy,
                precision=model.performance_metrics.precision,
                recall=model.performance_metrics.recall,
                f1_score=model.performance_metrics.f1_score,
                roc_auc=model.performance_metrics.roc_auc,
                rmse=model.performance_metrics.rmse,
                mae=model.performance_metrics.mae,
                r2_score=model.performance_metrics.r2_score,
                additional_metrics=model.performance_metrics.additional_metrics,
                confusion_matrix=model.performance_metrics.confusion_matrix
            ),
            model_path=model.model_path,
            model_file_url=str(model.model_file_url) if model.model_file_url else None,
            feature_transformer_path=model.feature_transformer_path,
            model_size=model.model_size,
            status=model.status.value,
            deployment_config=DeploymentConfigResponse(
                is_deployed=model.deployment_config.is_deployed if model.deployment_config else False,
                deployed_at=model.deployment_config.deployed_at if model.deployment_config else None,
                deployment_endpoint=model.deployment_config.deployment_endpoint if model.deployment_config else None,
                prediction_count=model.deployment_config.prediction_count if model.deployment_config else 0,
                last_prediction_at=model.deployment_config.last_prediction_at if model.deployment_config else None,
                average_prediction_time=model.deployment_config.average_prediction_time if model.deployment_config else None,
                error_rate=model.deployment_config.error_rate if model.deployment_config else None
            ),
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve model: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model: {str(e)}"
        )


@router.get("", response_model=ModelListResponse)
async def list_models(
    current_user_id: str = Depends(get_current_user_id),
    dataset_id: str | None = Query(None, description="Filter by dataset ID"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status (TRAINING, TRAINED, DEPLOYED, ARCHIVED, FAILED)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    List models with optional filtering and pagination.

    Filters:
    - dataset_id: Show only models trained on specific dataset
    - status: Show only models with specific status

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

        # Calculate skip for database-level pagination
        skip = (page - 1) * limit

        # Get models with database-level pagination where possible
        if dataset_id:
            # For dataset filter, we still need to fetch and filter in-memory
            # TODO: Add list_models_by_dataset_and_user() method for better performance
            models = await model_service.list_models_by_dataset(dataset_id)
            # Filter by user
            models = [m for m in models if m.user_id == current_user_id]

            # Apply status filter if provided
            if status_filter:
                models = [m for m in models if m.status.value == status_filter]

            # Apply pagination in-memory (already filtered)
            total = len(models)
            paginated_models = models[skip:skip + limit]
        else:
            # Use database-level pagination for better performance
            if status_filter:
                # Use filtered query with pagination
                status_enum = ModelStatus(status_filter)
                if status_enum == ModelStatus.DEPLOYED:
                    paginated_models = await model_service.get_deployed_models(
                        current_user_id, skip=skip, limit=limit
                    )
                    total = await model_service.count_for_user(
                        current_user_id, status=status_enum
                    )
                else:
                    # For other statuses, use list_for_user with status filter
                    paginated_models = await model_service.list_for_user(
                        current_user_id, skip=skip, limit=limit,
                        status=status_enum
                    )
                    total = await model_service.count_for_user(
                        current_user_id, status=status_enum
                    )
            else:
                # No filter - use database-level pagination
                paginated_models = await model_service.list_model_configs(
                    current_user_id, skip=skip, limit=limit
                )
                total = await model_service.count_for_user(current_user_id)

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
        HTTPException: 404 if model not found, 400 for invalid updates
    """
    try:
        model_service = ModelService()

        # Build update dict from request
        update_fields: dict[str, Any] = {}
        if request.name is not None:
            update_fields["name"] = request.name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.tags is not None:
            update_fields["tags"] = request.tags
        if request.notes is not None:
            update_fields["notes"] = request.notes

        # Update model with ownership check
        updated_model = await model_service.update_model_config(
            model_id=model_id,
            user_id=current_user_id,
            **update_fields
        )

        if not updated_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found"
            )

        # Convert to response (reuse get_model logic)
        from app.schemas.model import (
            DeploymentConfigResponse,
            FeatureConfigResponse,
            PerformanceMetricsResponse,
            TrainingConfigResponse,
        )

        return ModelConfigResponse(
            model_id=updated_model.model_id,
            user_id=updated_model.user_id,
            dataset_id=updated_model.dataset_id,
            name=updated_model.name,
            description=updated_model.description,
            problem_type=updated_model.problem_type.value,
            algorithm=updated_model.algorithm,
            hyperparameters=updated_model.hyperparameters.model_dump(),
            feature_config=FeatureConfigResponse(
                feature_names=updated_model.feature_config.feature_names,
                target_column=updated_model.feature_config.target_column,
                engineered_features=updated_model.feature_config.engineered_features,
                dropped_features=updated_model.feature_config.dropped_features,
                feature_importance=updated_model.feature_config.feature_importance,
                numeric_features=updated_model.feature_config.numeric_features,
                categorical_features=updated_model.feature_config.categorical_features,
                datetime_features=updated_model.feature_config.datetime_features
            ),
            training_config=TrainingConfigResponse(
                train_test_split=updated_model.training_config.train_test_split,
                cv_folds=updated_model.training_config.cv_folds,
                validation_strategy=updated_model.training_config.validation_strategy,
                training_time=updated_model.training_config.training_time,
                n_samples_train=updated_model.training_config.n_samples_train,
                n_samples_test=updated_model.training_config.n_samples_test,
                early_stopping=updated_model.training_config.early_stopping,
                optimization_metric=updated_model.training_config.optimization_metric
            ),
            performance_metrics=PerformanceMetricsResponse(
                cv_score=updated_model.performance_metrics.cv_score,
                test_score=updated_model.performance_metrics.test_score,
                accuracy=updated_model.performance_metrics.accuracy,
                precision=updated_model.performance_metrics.precision,
                recall=updated_model.performance_metrics.recall,
                f1_score=updated_model.performance_metrics.f1_score,
                roc_auc=updated_model.performance_metrics.roc_auc,
                rmse=updated_model.performance_metrics.rmse,
                mae=updated_model.performance_metrics.mae,
                r2_score=updated_model.performance_metrics.r2_score,
                additional_metrics=updated_model.performance_metrics.additional_metrics,
                confusion_matrix=updated_model.performance_metrics.confusion_matrix
            ),
            model_path=updated_model.model_path,
            model_file_url=str(updated_model.model_file_url) if updated_model.model_file_url else None,
            feature_transformer_path=updated_model.feature_transformer_path,
            model_size=updated_model.model_size,
            status=updated_model.status.value,
            deployment_config=DeploymentConfigResponse(
                is_deployed=updated_model.deployment_config.is_deployed if updated_model.deployment_config else False,
                deployed_at=updated_model.deployment_config.deployed_at if updated_model.deployment_config else None,
                deployment_endpoint=updated_model.deployment_config.deployment_endpoint if updated_model.deployment_config else None,
                prediction_count=updated_model.deployment_config.prediction_count if updated_model.deployment_config else 0,
                last_prediction_at=updated_model.deployment_config.last_prediction_at if updated_model.deployment_config else None,
                average_prediction_time=updated_model.deployment_config.average_prediction_time if updated_model.deployment_config else None,
                error_rate=updated_model.deployment_config.error_rate if updated_model.deployment_config else None
            ),
            version=updated_model.version,
            is_active=updated_model.is_active,
            parent_model_id=updated_model.parent_model_id,
            created_at=updated_model.created_at,
            updated_at=updated_model.updated_at,
            trained_at=updated_model.trained_at,
            last_used_at=updated_model.last_used_at,
            tags=updated_model.tags,
            notes=updated_model.notes
        )

    except HTTPException:
        raise
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update model: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update model: {str(e)}"
        )


@router.get("/{model_id}/performance", response_model=PerformanceMetricsResponse)
async def get_model_performance(
    model_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Retrieve model performance metrics.

    Returns comprehensive performance metrics including:
    - Cross-validation score
    - Test set score
    - Classification metrics (accuracy, precision, recall, f1, roc_auc)
    - Regression metrics (rmse, mae, r2_score)
    - Confusion matrix (for classification)

    Args:
        model_id: Model identifier
        current_user_id: Authenticated user ID

    Returns:
        PerformanceMetricsResponse with all available metrics

    Raises:
        HTTPException: 404 if model not found or metrics not available
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

        # Return performance metrics
        return PerformanceMetricsResponse(
            cv_score=model.performance_metrics.cv_score,
            test_score=model.performance_metrics.test_score,
            accuracy=model.performance_metrics.accuracy,
            precision=model.performance_metrics.precision,
            recall=model.performance_metrics.recall,
            f1_score=model.performance_metrics.f1_score,
            roc_auc=model.performance_metrics.roc_auc,
            rmse=model.performance_metrics.rmse,
            mae=model.performance_metrics.mae,
            r2_score=model.performance_metrics.r2_score,
            additional_metrics=model.performance_metrics.additional_metrics,
            confusion_matrix=model.performance_metrics.confusion_matrix
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve performance metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve performance metrics: {str(e)}"
        )


@router.put("/{model_id}/deploy", response_model=ModelDeployResponse)
async def deploy_model(
    model_id: str,
    request: ModelDeployRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Deploy model to production endpoint.

    State machine transitions:
    - TRAINED → DEPLOYED: Success
    - PENDING/TRAINING → DEPLOYED: 400 Bad Request (must be trained first)
    - DEPLOYED → DEPLOYED: 409 Conflict (already deployed)

    Updates:
    - status: DEPLOYED
    - deployment_config.is_deployed: True
    - deployment_config.deployed_at: Current timestamp
    - deployment_config.deployment_endpoint: Provided endpoint URL

    Args:
        model_id: Model identifier
        request: Deployment configuration (optional endpoint)
        current_user_id: Authenticated user ID

    Returns:
        Deployment confirmation with endpoint details

    Raises:
        HTTPException:
            - 404 if model not found
            - 400 if model not trained yet
            - 409 if already deployed
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

        # Validate state machine: must be TRAINED to deploy
        if model.status != ModelStatus.TRAINED:
            if model.status == ModelStatus.DEPLOYED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Model {model_id} is already deployed"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Model must be trained before deployment. Current status: {model.status.value}"
                )

        # Deploy model with ownership check
        deployed_model = await model_service.mark_model_deployed(
            model_id=model_id,
            endpoint=request.endpoint,
            user_id=current_user_id
        )

        if not deployed_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found"
            )

        if deployed_model.deployment_config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found"
            )

        return ModelDeployResponse(
            model_id=model_id,
            status=deployed_model.status.value,
            deployed_at=deployed_model.deployment_config.deployed_at,
            deployment_endpoint=deployed_model.deployment_config.deployment_endpoint,
            message=f"Model {model_id} deployed successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deploy model: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy model: {str(e)}"
        )
