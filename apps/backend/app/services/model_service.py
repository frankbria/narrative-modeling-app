"""
Model service for ModelConfig operations.

This service handles ML model configuration operations using the new ModelConfig model.

Security:
- All retrieval methods enforce ownership checks by default when user_id is provided
- Ownership checks can be bypassed for internal operations by omitting user_id parameter
- All bypassed operations are logged for security auditing
"""

from typing import List, Optional, Dict, Any
import logging

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

logger = logging.getLogger(__name__)


class ModelService:
    """Service for model operations using ModelConfig."""

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
        """
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

    async def get_model_config(
        self,
        model_id: str,
        user_id: Optional[str] = None
    ) -> Optional[ModelConfig]:
        """
        Retrieve model configuration by model ID.

        Security: Enforces ownership check when user_id is provided.
        For internal operations that require bypassing ownership checks,
        omit the user_id parameter. All bypassed operations are logged.

        Args:
            model_id: Model identifier
            user_id: Optional user ID for ownership verification.
                    If provided, only returns model if owned by this user.
                    If None, bypasses ownership check (logged for audit).

        Returns:
            ModelConfig instance or None if not found or ownership check fails
        """
        model = await ModelConfig.find_one(ModelConfig.model_id == model_id)

        if model is None:
            return None

        # Enforce ownership check if user_id is provided
        if user_id is not None:
            if model.user_id != user_id:
                logger.warning(
                    f"Ownership check failed: User {user_id} attempted to access "
                    f"model {model_id} owned by {model.user_id}"
                )
                return None
        else:
            # Log bypassed ownership check for security audit
            logger.info(
                f"Ownership check bypassed for model {model_id} "
                f"(owned by {model.user_id}). This is expected for internal operations."
            )

        return model

    async def list_model_configs(
        self,
        user_id: str
    ) -> List[ModelConfig]:
        """
        List all model configurations for a user, sorted chronologically.

        Optimization: Uses compound index (user_id, created_at).

        Args:
            user_id: User identifier

        Returns:
            List of ModelConfig instances sorted by created_at descending
        """
        return await ModelConfig.find(
            ModelConfig.user_id == user_id
        ).sort(-ModelConfig.created_at).to_list()

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
        metrics: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Optional[ModelConfig]:
        """
        Update model training status and optionally update metrics.

        Security: Enforces ownership check when user_id is provided.

        Args:
            model_id: Model identifier
            status: New model status
            metrics: Additional metrics to update (optional)
            user_id: Optional user ID for ownership verification

        Returns:
            Updated ModelConfig or None if not found or ownership check fails
        """
        config = await self.get_model_config(model_id, user_id=user_id)
        if not config:
            return None

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

    async def mark_model_trained(
        self,
        model_id: str,
        user_id: Optional[str] = None
    ) -> Optional[ModelConfig]:
        """
        Mark model as trained.

        Security: Enforces ownership check when user_id is provided.

        Args:
            model_id: Model identifier
            user_id: Optional user ID for ownership verification

        Returns:
            Updated ModelConfig or None if not found or ownership check fails
        """
        config = await self.get_model_config(model_id, user_id=user_id)
        if not config:
            return None

        config.mark_trained()
        await config.save()
        return config

    async def mark_model_deployed(
        self,
        model_id: str,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Optional[ModelConfig]:
        """
        Mark model as deployed.

        Security: Enforces ownership check when user_id is provided.

        Args:
            model_id: Model identifier
            endpoint: API endpoint for deployed model (optional)
            user_id: Optional user ID for ownership verification

        Returns:
            Updated ModelConfig or None if not found or ownership check fails
        """
        config = await self.get_model_config(model_id, user_id=user_id)
        if not config:
            return None

        config.mark_deployed(endpoint)
        await config.save()
        return config

    async def mark_model_archived(
        self,
        model_id: str,
        user_id: Optional[str] = None
    ) -> Optional[ModelConfig]:
        """
        Mark model as archived.

        Security: Enforces ownership check when user_id is provided.

        Args:
            model_id: Model identifier
            user_id: Optional user ID for ownership verification

        Returns:
            Updated ModelConfig or None if not found or ownership check fails
        """
        config = await self.get_model_config(model_id, user_id=user_id)
        if not config:
            return None

        config.mark_archived()
        await config.save()
        return config

    async def mark_model_failed(
        self,
        model_id: str,
        user_id: Optional[str] = None
    ) -> Optional[ModelConfig]:
        """
        Mark model training as failed.

        Security: Enforces ownership check when user_id is provided.

        Args:
            model_id: Model identifier
            user_id: Optional user ID for ownership verification

        Returns:
            Updated ModelConfig or None if not found or ownership check fails
        """
        config = await self.get_model_config(model_id, user_id=user_id)
        if not config:
            return None

        config.mark_failed()
        await config.save()
        return config

    async def record_prediction(
        self,
        model_id: str,
        prediction_time_ms: Optional[float] = None,
        user_id: Optional[str] = None
    ) -> Optional[ModelConfig]:
        """
        Record a prediction event.

        Security: Enforces ownership check when user_id is provided.

        Args:
            model_id: Model identifier
            prediction_time_ms: Prediction time in milliseconds (optional)
            user_id: Optional user ID for ownership verification

        Returns:
            Updated ModelConfig or None if not found or ownership check fails
        """
        config = await self.get_model_config(model_id, user_id=user_id)
        if not config:
            return None

        config.record_prediction(prediction_time_ms)
        await config.save()
        return config

    async def get_active_models(
        self,
        user_id: str
    ) -> List[ModelConfig]:
        """
        Get all active model configurations for a user, sorted chronologically.

        Optimization: Uses compound index (user_id, is_active, created_at).

        Args:
            user_id: User identifier

        Returns:
            List of active ModelConfig instances sorted by created_at descending
        """
        return await ModelConfig.find(
            ModelConfig.user_id == user_id,
            ModelConfig.is_active == True
        ).sort(-ModelConfig.created_at).to_list()

    async def get_deployed_models(
        self,
        user_id: str
    ) -> List[ModelConfig]:
        """
        Get all deployed model configurations for a user, sorted chronologically.

        Optimization: Uses compound index (user_id, status, created_at).

        Args:
            user_id: User identifier

        Returns:
            List of deployed ModelConfig instances sorted by created_at descending
        """
        return await ModelConfig.find(
            ModelConfig.user_id == user_id,
            ModelConfig.status == ModelStatus.DEPLOYED
        ).sort(-ModelConfig.created_at).to_list()

    async def delete_model_config(
        self,
        model_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Delete model configuration.

        Security: Enforces ownership check when user_id is provided.

        Args:
            model_id: Model identifier
            user_id: Optional user ID for ownership verification

        Returns:
            True if deleted, False if not found or ownership check fails
        """
        config = await self.get_model_config(model_id, user_id=user_id)
        if not config:
            return False

        await config.delete()
        return True

    async def update_model_config(
        self,
        model_id: str,
        user_id: Optional[str] = None,
        **update_fields
    ) -> Optional[ModelConfig]:
        """
        Update model configuration fields.

        Security: Enforces ownership check when user_id is provided.

        Args:
            model_id: Model identifier
            user_id: Optional user ID for ownership verification
            **update_fields: Fields to update

        Returns:
            Updated ModelConfig or None if not found or ownership check fails
        """
        config = await self.get_model_config(model_id, user_id=user_id)
        if not config:
            return None

        # Update fields
        for field, value in update_fields.items():
            if hasattr(config, field):
                setattr(config, field, value)

        config.update_timestamp()
        await config.save()
        return config
