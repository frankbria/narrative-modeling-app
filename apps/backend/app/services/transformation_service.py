"""
Transformation service for TransformationConfig operations.

This service handles transformation configuration operations using the new
TransformationConfig model, delegating actual transformation execution to
the existing TransformationEngine.
"""

from typing import List, Optional, Dict, Any
from app.models.transformation import (
    TransformationConfig,
    TransformationStep,
    TransformationPreview,
    TransformationValidation
)
from app.services.transformation_service.transformation_engine import (
    TransformationEngine,
    TransformationType
)


class TransformationService:
    """Service for transformation operations using TransformationConfig."""

    def __init__(self):
        """Initialize service with transformation engine."""
        self.engine = TransformationEngine()

    async def create_transformation_config(
        self,
        user_id: str,
        dataset_id: str,
        config_id: str,
        transformation_steps: Optional[List[TransformationStep]] = None,
        current_file_path: Optional[str] = None,
        **kwargs
    ) -> TransformationConfig:
        """
        Create transformation configuration.

        Args:
            user_id: User who owns the configuration
            dataset_id: Dataset this configuration applies to
            config_id: Unique configuration identifier
            transformation_steps: List of transformation steps (optional)
            current_file_path: Current file path after transformations
            **kwargs: Additional fields

        Returns:
            Created TransformationConfig instance
        """
        config = TransformationConfig(
            user_id=user_id,
            dataset_id=dataset_id,
            config_id=config_id,
            transformation_steps=transformation_steps or [],
            current_file_path=current_file_path,
            **kwargs
        )
        await config.save()
        return config

    async def get_transformation_config(
        self,
        config_id: str
    ) -> Optional[TransformationConfig]:
        """
        Retrieve transformation configuration by config ID.

        Args:
            config_id: Configuration identifier

        Returns:
            TransformationConfig instance or None if not found
        """
        return await TransformationConfig.find_one(
            TransformationConfig.config_id == config_id
        )

    async def list_transformation_configs(
        self,
        dataset_id: str
    ) -> List[TransformationConfig]:
        """
        List all transformation configurations for a dataset.

        Args:
            dataset_id: Dataset identifier

        Returns:
            List of TransformationConfig instances
        """
        return await TransformationConfig.find(
            TransformationConfig.dataset_id == dataset_id
        ).to_list()

    async def add_transformation_step(
        self,
        config_id: str,
        transformation_type: str,
        column: Optional[str] = None,
        columns: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[TransformationConfig]:
        """
        Add a transformation step to configuration.

        Args:
            config_id: Configuration identifier
            transformation_type: Type of transformation
            column: Single column to transform (optional)
            columns: Multiple columns to transform (optional)
            parameters: Transformation parameters (optional)

        Returns:
            Updated TransformationConfig or None if not found
        """
        config = await self.get_transformation_config(config_id)
        if not config:
            return None

        # Add step using model method
        config.add_transformation_step(
            transformation_type=transformation_type,
            column=column,
            columns=columns,
            parameters=parameters
        )

        await config.save()
        return config

    async def validate_transformation_config(
        self,
        config_id: str
    ) -> Optional[TransformationValidation]:
        """
        Validate all transformation steps in configuration.

        Args:
            config_id: Configuration identifier

        Returns:
            TransformationValidation result or None if config not found
        """
        config = await self.get_transformation_config(config_id)
        if not config:
            return None

        # Validate using model method
        validation_result = config.validate_transformations()

        await config.save()
        return validation_result

    async def mark_transformations_applied(
        self,
        config_id: str,
        file_path: str
    ) -> Optional[TransformationConfig]:
        """
        Mark transformations as applied.

        Args:
            config_id: Configuration identifier
            file_path: Path to transformed file

        Returns:
            Updated TransformationConfig or None if not found
        """
        config = await self.get_transformation_config(config_id)
        if not config:
            return None

        config.mark_applied(file_path)
        await config.save()
        return config

    async def clear_transformations(
        self,
        config_id: str
    ) -> Optional[TransformationConfig]:
        """
        Clear all transformation steps from configuration.

        Args:
            config_id: Configuration identifier

        Returns:
            Updated TransformationConfig or None if not found
        """
        config = await self.get_transformation_config(config_id)
        if not config:
            return None

        config.clear_transformations()
        await config.save()
        return config

    async def delete_transformation_config(
        self,
        config_id: str
    ) -> bool:
        """
        Delete transformation configuration.

        Args:
            config_id: Configuration identifier

        Returns:
            True if deleted, False if not found
        """
        config = await self.get_transformation_config(config_id)
        if not config:
            return False

        await config.delete()
        return True

    async def get_applied_configs(
        self,
        dataset_id: str
    ) -> List[TransformationConfig]:
        """
        Get all applied transformation configurations for a dataset.

        Args:
            dataset_id: Dataset identifier

        Returns:
            List of applied TransformationConfig instances
        """
        return await TransformationConfig.find(
            TransformationConfig.dataset_id == dataset_id,
            TransformationConfig.is_applied == True
        ).to_list()
