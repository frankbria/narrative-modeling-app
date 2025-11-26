"""
Model service for ModelConfig operations.

This service handles ML model configuration operations using the new ModelConfig model.
Inherits from BaseService for standardized CRUD patterns and error handling.
"""

from typing import List, Optional, Dict, Any
from app.models.model import (
    ModelConfig,
    ProblemType,
    ModelStatus,
    HyperparameterConfig,
    FeatureConfig,
    PerformanceMetrics,
    TrainingConfig,
    DeploymentConfig
)
from app.services.base_service import BaseService
from app.services.exceptions import NotFoundError, OperationError


class ModelService(BaseService[ModelConfig]):
    """Service for model operations using ModelConfig."""

    model_class = ModelConfig
    resource_name = "Model"

    def _get_id_field(self) -> str:
        """Return the unique identifier field name."""
        return "model_id"

    async def create_model_config(
        self,
        user_id: str,
        dataset_id: str,
        model_id: str,
        name: str,
        problem_type: ProblemType,
        algorithm: str,
        feature_config: FeatureConfig,
        training_config: TrainingConfig,
        performance_metrics: PerformanceMetrics,
        model_path: str,
        model_size: int,
        hyperparameters: Optional[HyperparameterConfig] = None,
        description: Optional[str] = None,
        model_file_url: Optional[str] = None,
        feature_transformer_path: Optional[str] = None,
        deployment_config: Optional[DeploymentConfig] = None,
        **kwargs
    ) -> ModelConfig:
        """
        Create model configuration.

        Args:
            user_id: User who owns the model
            dataset_id: Dataset used for training
            model_id: Unique model identifier
            name: Human-readable model name
            problem_type: Type of ML problem
            algorithm: Algorithm name
            feature_config: Feature configuration
            training_config: Training configuration
            performance_metrics: Performance metrics
            model_path: Storage path for serialized model
            model_size: Model file size in bytes
            hyperparameters: Hyperparameter configuration (optional)
            description: Model description (optional)
            model_file_url: HTTP URL for model file access (optional)
            feature_transformer_path: Storage path for feature transformer (optional)
            deployment_config: Deployment configuration (optional)
            **kwargs: Additional fields

        Returns:
            Created ModelConfig instance

        Raises:
            OperationError: If model creation fails
        """
        try:
            config = ModelConfig(
                user_id=user_id,
                dataset_id=dataset_id,
                model_id=model_id,
                name=name,
                description=description,
                problem_type=problem_type,
                algorithm=algorithm,
                hyperparameters=hyperparameters or HyperparameterConfig(),
                feature_config=feature_config,
                training_config=training_config,
                performance_metrics=performance_metrics,
                model_path=model_path,
                model_file_url=model_file_url,
                feature_transformer_path=feature_transformer_path,
                model_size=model_size,
                status=ModelStatus.TRAINING,
                deployment_config=deployment_config or DeploymentConfig(),
                **kwargs
            )
            await config.save()
            return config
        except Exception as e:
            raise OperationError(
                message="Failed to create model configuration",
                operation="create_model_config",
                original_error=e
            )

    async def get_model_config(
        self,
        model_id: str
    ) -> Optional[ModelConfig]:
        """
        Retrieve model configuration by model ID.

        Args:
            model_id: Model identifier

        Returns:
            ModelConfig instance or None if not found
        """
        return await self.get_by_id(model_id, check_ownership=False)

    async def list_model_configs(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 1000
    ) -> List[ModelConfig]:
        """
        List all model configurations for a user, sorted chronologically.

        PERFORMANCE WARNING: Default limit=1000 is high and may cause performance
        issues with large datasets. Consider using pagination with smaller limits
        (e.g., 20-100) or use list_for_user() directly with explicit pagination.

        Optimization: Uses compound index (user_id, created_at).

        Args:
            user_id: User identifier
            skip: Number of records to skip (for pagination)
            limit: Maximum records to return (default: 1000 for backward compatibility)

        Returns:
            List of ModelConfig instances sorted by created_at descending
        """
        return await self.list_for_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            sort_field="created_at",
            sort_ascending=False
        )

    async def list_models_by_dataset(
        self,
        dataset_id: str
    ) -> List[ModelConfig]:
        """
        List all model configurations for a dataset, sorted chronologically.

        Optimization: Uses compound index (dataset_id, created_at).

        Args:
            dataset_id: Dataset identifier

        Returns:
            List of ModelConfig instances sorted by created_at descending
        """
        return await ModelConfig.find(
            ModelConfig.dataset_id == dataset_id
        ).sort(-ModelConfig.created_at).to_list()

    async def update_training_status(
        self,
        model_id: str,
        status: ModelStatus,
        metrics: Optional[Dict[str, Any]] = None
    ) -> ModelConfig:
        """
        Update model training status and optionally update metrics.

        Args:
            model_id: Model identifier
            status: New model status
            metrics: Additional metrics to update (optional)

        Returns:
            Updated ModelConfig

        Raises:
            NotFoundError: If model not found
            OperationError: If update fails
        """
        config = await self.get_by_id_or_raise(model_id, check_ownership=False)

        try:
            config.status = status

            if metrics:
                # Update performance metrics with new values
                for key, value in metrics.items():
                    if hasattr(config.performance_metrics, key):
                        setattr(config.performance_metrics, key, value)
                    else:
                        # Add to additional_metrics if not a standard field
                        config.performance_metrics.additional_metrics[key] = value

            config.update_timestamp()
            await config.save()
            return config
        except Exception as e:
            raise OperationError(
                message="Failed to update training status",
                operation="update_training_status",
                original_error=e
            )

    async def mark_model_trained(
        self,
        model_id: str
    ) -> ModelConfig:
        """
        Mark model as trained.

        Args:
            model_id: Model identifier

        Returns:
            Updated ModelConfig

        Raises:
            NotFoundError: If model not found
            OperationError: If update fails
        """
        config = await self.get_by_id_or_raise(model_id, check_ownership=False)

        try:
            config.mark_trained()
            await config.save()
            return config
        except Exception as e:
            raise OperationError(
                message="Failed to mark model as trained",
                operation="mark_model_trained",
                original_error=e
            )

    async def mark_model_deployed(
        self,
        model_id: str,
        endpoint: Optional[str] = None
    ) -> ModelConfig:
        """
        Mark model as deployed.

        Args:
            model_id: Model identifier
            endpoint: API endpoint for deployed model (optional)

        Returns:
            Updated ModelConfig

        Raises:
            NotFoundError: If model not found
            OperationError: If update fails
        """
        config = await self.get_by_id_or_raise(model_id, check_ownership=False)

        try:
            config.mark_deployed(endpoint)
            await config.save()
            return config
        except Exception as e:
            raise OperationError(
                message="Failed to mark model as deployed",
                operation="mark_model_deployed",
                original_error=e
            )

    async def mark_model_archived(
        self,
        model_id: str
    ) -> ModelConfig:
        """
        Mark model as archived.

        Args:
            model_id: Model identifier

        Returns:
            Updated ModelConfig

        Raises:
            NotFoundError: If model not found
            OperationError: If update fails
        """
        config = await self.get_by_id_or_raise(model_id, check_ownership=False)

        try:
            config.mark_archived()
            await config.save()
            return config
        except Exception as e:
            raise OperationError(
                message="Failed to mark model as archived",
                operation="mark_model_archived",
                original_error=e
            )

    async def mark_model_failed(
        self,
        model_id: str
    ) -> ModelConfig:
        """
        Mark model training as failed.

        Args:
            model_id: Model identifier

        Returns:
            Updated ModelConfig

        Raises:
            NotFoundError: If model not found
            OperationError: If update fails
        """
        config = await self.get_by_id_or_raise(model_id, check_ownership=False)

        try:
            config.mark_failed()
            await config.save()
            return config
        except Exception as e:
            raise OperationError(
                message="Failed to mark model as failed",
                operation="mark_model_failed",
                original_error=e
            )

    async def record_prediction(
        self,
        model_id: str,
        prediction_time_ms: Optional[float] = None
    ) -> ModelConfig:
        """
        Record a prediction event.

        Args:
            model_id: Model identifier
            prediction_time_ms: Prediction time in milliseconds (optional)

        Returns:
            Updated ModelConfig

        Raises:
            NotFoundError: If model not found
            OperationError: If update fails
        """
        config = await self.get_by_id_or_raise(model_id, check_ownership=False)

        try:
            config.record_prediction(prediction_time_ms)
            await config.save()
            return config
        except Exception as e:
            raise OperationError(
                message="Failed to record prediction",
                operation="record_prediction",
                original_error=e
            )

    async def get_active_models(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 1000
    ) -> List[ModelConfig]:
        """
        Get all active model configurations for a user, sorted chronologically.

        PERFORMANCE WARNING: Default limit=1000 is high and may cause performance
        issues with large datasets. Consider using pagination with smaller limits.

        Optimization: Uses compound index (user_id, is_active, created_at).

        Args:
            user_id: User identifier
            skip: Number of records to skip (for pagination)
            limit: Maximum records to return (default: 1000 for backward compatibility)

        Returns:
            List of active ModelConfig instances sorted by created_at descending
        """
        return await self.list_for_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            sort_field="created_at",
            sort_ascending=False,
            is_active=True
        )

    async def get_deployed_models(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 1000
    ) -> List[ModelConfig]:
        """
        Get all deployed model configurations for a user, sorted chronologically.

        PERFORMANCE WARNING: Default limit=1000 is high and may cause performance
        issues with large datasets. Consider using pagination with smaller limits.

        Optimization: Uses compound index (user_id, status, created_at).

        Args:
            user_id: User identifier
            skip: Number of records to skip (for pagination)
            limit: Maximum records to return (default: 1000 for backward compatibility)

        Returns:
            List of deployed ModelConfig instances sorted by created_at descending
        """
        return await self.list_for_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            sort_field="created_at",
            sort_ascending=False,
            status=ModelStatus.DEPLOYED
        )

    async def delete_model_config(
        self,
        model_id: str,
        user_id: str
    ) -> bool:
        """
        Delete model configuration.

        Args:
            model_id: Model identifier
            user_id: User ID for ownership check

        Returns:
            True if deleted, False if not found

        Raises:
            PermissionDeniedError: If user doesn't own the model
        """
        return await self.delete(
            resource_id=model_id,
            user_id=user_id,
            soft_delete=False
        )

    async def update_model_config(
        self,
        model_id: str,
        user_id: str,
        **update_fields
    ) -> ModelConfig:
        """
        Update model configuration fields.

        Args:
            model_id: Model identifier
            user_id: User ID for ownership check
            **update_fields: Fields to update

        Returns:
            Updated ModelConfig

        Raises:
            NotFoundError: If model not found
            PermissionDeniedError: If user doesn't own the model
            OperationError: If update fails
        """
        # BaseService.update() now raises NotFoundError directly, no need to check for None
        return await self.update(
            resource_id=model_id,
            user_id=user_id,
            update_data=update_fields
        )