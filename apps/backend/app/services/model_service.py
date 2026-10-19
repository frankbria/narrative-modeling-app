"""
Model service for ModelConfig operations.

This service handles ML model configuration operations using the new ModelConfig model.
Inherits from BaseService for standardized CRUD patterns and error handling.

Security:
- All retrieval methods enforce ownership checks by default when user_id is provided
- Ownership checks can be bypassed for internal operations by omitting user_id parameter
- All bypassed operations are logged for security auditing via BaseService._check_ownership()
"""

from app.models.model import ModelConfig, ModelStatus
from app.services.base_service import BaseService


class ModelService(BaseService[ModelConfig]):
    """Service for model operations using ModelConfig."""

    model_class = ModelConfig
    resource_name = "Model"

    def _get_id_field(self) -> str:
        """Return the unique identifier field name."""
        return "model_id"

    async def get_model_config(
        self,
        model_id: str,
        user_id: str | None = None
    ) -> ModelConfig | None:
        """
        Retrieve model configuration by model ID.

        Args:
            model_id: Model identifier
            user_id: Optional user ID for ownership checking

        Returns:
            ModelConfig instance or None if not found
        """
        return await self.get_by_id(
            resource_id=model_id,
            user_id=user_id,
            check_ownership=bool(user_id)
        )

    async def list_model_configs(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 1000
    ) -> list[ModelConfig]:
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
    ) -> list[ModelConfig]:
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
        ).sort("-created_at").to_list()

    async def get_deployed_models(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 1000
    ) -> list[ModelConfig]:
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
            NotFoundError: If model not found or not the caller's (#985)
            OperationError: If update fails
        """
        # BaseService.update() now raises NotFoundError directly, no need to check for None
        return await self.update(
            resource_id=model_id,
            user_id=user_id,
            update_data=update_fields
        )