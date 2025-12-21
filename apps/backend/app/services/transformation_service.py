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
from app.services.transformation_engine.transformation_engine import (
    TransformationEngine,
    TransformationType
)
from app.services.base_service import BaseService
from app.services.exceptions import (
    NotFoundError,
    ValidationError,
    OperationError
)


class TransformationService(BaseService[TransformationConfig]):
    """Service for transformation operations using TransformationConfig."""

    model_class = TransformationConfig
    resource_name = "TransformationConfig"

    def __init__(self):
        """Initialize service with transformation engine."""
        self.engine = TransformationEngine()

    def _get_id_field(self) -> str:
        """
        Return the name of the unique identifier field.

        Returns:
            Field name string for TransformationConfig
        """
        return "config_id"

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
        return await self.get_by_id(config_id, check_ownership=False)

    async def list_transformation_configs(
        self,
        dataset_id: str
    ) -> List[TransformationConfig]:
        """
        List all transformation configurations for a dataset, sorted chronologically.

        Optimization: Uses compound index (dataset_id, created_at).

        Args:
            dataset_id: Dataset identifier

        Returns:
            List of TransformationConfig instances sorted by created_at descending
        """
        return await TransformationConfig.find(
            TransformationConfig.dataset_id == dataset_id
        ).sort(-TransformationConfig.created_at).to_list()

    async def add_transformation_step(
        self,
        config_id: str,
        transformation_type: str,
        column: Optional[str] = None,
        columns: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> TransformationConfig:
        """
        Add a transformation step to configuration.

        Args:
            config_id: Configuration identifier
            transformation_type: Type of transformation
            column: Single column to transform (optional)
            columns: Multiple columns to transform (optional)
            parameters: Transformation parameters (optional)

        Returns:
            Updated TransformationConfig

        Raises:
            NotFoundError: If config not found
        """
        config = await self.get_by_id_or_raise(config_id, check_ownership=False)

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
    ) -> TransformationValidation:
        """
        Validate all transformation steps in configuration.

        Args:
            config_id: Configuration identifier

        Returns:
            TransformationValidation result

        Raises:
            NotFoundError: If config not found
        """
        config = await self.get_by_id_or_raise(config_id, check_ownership=False)

        # Validate using model method
        validation_result = config.validate_transformations()

        await config.save()
        return validation_result

    async def mark_transformations_applied(
        self,
        config_id: str,
        file_path: str
    ) -> TransformationConfig:
        """
        Mark transformations as applied.

        Args:
            config_id: Configuration identifier
            file_path: Path to transformed file

        Returns:
            Updated TransformationConfig

        Raises:
            NotFoundError: If config not found
        """
        config = await self.get_by_id_or_raise(config_id, check_ownership=False)

        config.mark_applied(file_path)
        await config.save()
        return config

    async def clear_transformations(
        self,
        config_id: str
    ) -> TransformationConfig:
        """
        Clear all transformation steps from configuration.

        Args:
            config_id: Configuration identifier

        Returns:
            Updated TransformationConfig

        Raises:
            NotFoundError: If config not found
        """
        config = await self.get_by_id_or_raise(config_id, check_ownership=False)

        config.clear_transformations()
        await config.save()
        return config

    async def delete_transformation_config(
        self,
        config_id: str,
        user_id: str
    ) -> bool:
        """
        Delete transformation configuration.

        Args:
            config_id: Configuration identifier
            user_id: User identifier for ownership check

        Returns:
            True if deleted, False if not found

        Raises:
            PermissionDeniedError: If user doesn't own the resource
        """
        return await self.delete(config_id, user_id, soft_delete=False)

    async def get_applied_configs(
        self,
        dataset_id: str
    ) -> List[TransformationConfig]:
        """
        Get all applied transformation configurations for a dataset, sorted chronologically.

        Optimization: Uses compound index (dataset_id, is_applied, created_at).

        Args:
            dataset_id: Dataset identifier

        Returns:
            List of applied TransformationConfig instances sorted by created_at descending
        """
        return await TransformationConfig.find(
            TransformationConfig.dataset_id == dataset_id,
            TransformationConfig.is_applied == True
        ).sort(-TransformationConfig.created_at).to_list()

    async def preview_transformation(
        self,
        user_id: str,
        dataset_id: str,
        transformation_type: str,
        parameters: Dict[str, Any],
        preview_rows: int = 10
    ) -> Dict[str, Any]:
        """
        Preview transformation without applying it.

        Args:
            user_id: User identifier (for ownership verification)
            dataset_id: Dataset identifier
            transformation_type: Type of transformation
            parameters: Transformation parameters
            preview_rows: Number of rows to preview

        Returns:
            Preview result with before/after samples

        Raises:
            NotFoundError: If dataset not found or user doesn't own it
            OperationError: If transformation preview fails
        """
        from app.models.dataset import DatasetMetadata
        from app.services.transformation_engine.data_utils import get_dataframe_from_s3
        from app.services.transformation_engine.transformation_engine import TransformationType

        # Get dataset with ownership verification
        dataset = await DatasetMetadata.find_one({
            "dataset_id": dataset_id,
            "user_id": user_id
        })

        if not dataset:
            raise NotFoundError(
                resource_type="Dataset",
                resource_id=dataset_id,
                message=f"Dataset {dataset_id} not found or not owned by user"
            )

        try:
            # Load data from S3
            file_path = dataset.file_path or dataset.s3_url
            df = await get_dataframe_from_s3(file_path)

            # Preview transformation using engine
            result = self.engine.preview_transformation(
                df=df,
                transformation_type=TransformationType(transformation_type),
                parameters=parameters,
                n_rows=preview_rows
            )

            return {
                "success": result.success,
                "preview_data": result.preview_data,
                "affected_rows": result.affected_rows,
                "affected_columns": result.affected_columns,
                "stats_before": result.stats_before,
                "stats_after": result.stats_after,
                "error": result.error,
                "warnings": result.warnings
            }
        except ValueError as e:
            raise OperationError(
                message="Failed to preview transformation",
                operation="preview_transformation",
                original_error=e,
                details={"dataset_id": dataset_id, "transformation_type": transformation_type}
            )

    async def apply_transformation(
        self,
        user_id: str,
        dataset_id: str,
        transformation_type: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply transformation and persist results.

        Args:
            user_id: User identifier
            dataset_id: Dataset identifier
            transformation_type: Type of transformation
            parameters: Transformation parameters

        Returns:
            Apply result with transformation_id and affected rows/columns

        Raises:
            NotFoundError: If dataset not found or user doesn't own it
            OperationError: If transformation application fails
        """
        import time
        from datetime import datetime, timezone
        from app.models.dataset import DatasetMetadata
        from app.services.transformation_engine.data_utils import (
            get_dataframe_from_s3,
            upload_dataframe_to_s3
        )
        from app.services.transformation_engine.transformation_engine import TransformationType
        from app.services.redis_cache import cache_service
        import pandas as pd

        start_time = time.time()

        # Get dataset with ownership verification
        dataset = await DatasetMetadata.find_one({
            "dataset_id": dataset_id,
            "user_id": user_id
        })

        if not dataset:
            raise NotFoundError(
                resource_type="Dataset",
                resource_id=dataset_id,
                message=f"Dataset {dataset_id} not found or not owned by user {user_id}"
            )

        try:
            # Load data from S3
            file_path = dataset.file_path or dataset.s3_url
            df = await get_dataframe_from_s3(file_path)

            # Apply transformation using engine
            result = self.engine.apply_transformation(
                df=df,
                transformation_type=TransformationType(transformation_type),
                parameters=parameters
            )

            if not result.success:
                return {
                    "success": False,
                    "dataset_id": dataset_id,
                    "transformation_id": "",
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "error": result.error
                }

            # Save transformed data to S3
            transformed_df = pd.DataFrame(result.transformed_data)
            timestamp = datetime.now(timezone.utc).timestamp()
            new_file_path = await upload_dataframe_to_s3(
                transformed_df,
                f"transformed/{user_id}/{dataset_id}_{timestamp}.parquet"
            )

            # Create transformation config
            config_id = f"config_{dataset_id}_{int(timestamp)}"
            await self.create_transformation_config(
                user_id=user_id,
                dataset_id=dataset_id,
                config_id=config_id,
                current_file_path=new_file_path
            )

            # Add transformation step
            await self.add_transformation_step(
                config_id=config_id,
                transformation_type=transformation_type,
                column=parameters.get("column"),
                columns=parameters.get("columns"),
                parameters=parameters
            )

            # Mark as applied
            config = await self.mark_transformations_applied(
                config_id=config_id,
                file_path=new_file_path
            )

            # Calculate execution time early for versioning
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Create dataset version for transformation
            from app.services.versioning_service import versioning_service

            # Get parent version (most recent version for this dataset)
            from app.models.version import DatasetVersion
            parent_version = await DatasetVersion.find(
                {"dataset_id": dataset_id}
            ).sort([("version_number", -1)]).first_or_none()

            if parent_version:
                # Get file content for versioning
                import io
                buffer = io.BytesIO()
                transformed_df.to_parquet(buffer, index=False)
                transformed_content = buffer.getvalue()

                # Update dataset metadata for version creation
                dataset.num_rows = len(transformed_df)
                dataset.num_columns = len(transformed_df.columns)
                dataset.columns = transformed_df.columns.tolist()

                # Build transformation steps for lineage
                transformation_steps = [
                    {
                        "transformation_type": transformation_type,
                        "column": parameters.get("column"),
                        "columns": parameters.get("columns"),
                        "parameters": parameters,
                        "execution_time": execution_time_ms
                    }
                ]

                # Create version with lineage
                version, lineage = await versioning_service.create_transformation_version(
                    parent_version_id=parent_version.version_id,
                    transformed_content=transformed_content,
                    transformation_steps=transformation_steps,
                    dataset_metadata=dataset,
                    user_id=user_id,
                    description=f"Applied {transformation_type} transformation",
                    transformation_config_id=config_id
                )

            # Update dataset file path
            dataset.file_path = new_file_path
            dataset.update_timestamp()
            await dataset.save()

            # Clear cached data
            await cache_service.delete_pattern(f"stats_{dataset_id}_*")

            return {
                "success": True,
                "dataset_id": dataset_id,
                "transformation_id": config_id,
                "affected_rows": result.affected_rows,
                "affected_columns": result.affected_columns,
                "execution_time_ms": execution_time_ms,
                "warnings": result.warnings
            }
        except ValueError as e:
            raise OperationError(
                message="Failed to apply transformation",
                operation="apply_transformation",
                original_error=e,
                details={
                    "dataset_id": dataset_id,
                    "transformation_type": transformation_type,
                    "user_id": user_id
                }
            )

    async def get_transformation_history(
        self,
        config_id: str
    ) -> Dict[str, Any]:
        """
        Get transformation history with lineage.

        Args:
            config_id: Configuration identifier

        Returns:
            Transformation history with steps, timestamps, and lineage

        Raises:
            NotFoundError: If config not found
        """
        config = await self.get_by_id_or_raise(config_id, check_ownership=False)

        # Build transformation steps response
        steps = [
            {
                "transformation_type": step.transformation_type,
                "column": step.column,
                "columns": step.columns,
                "parameters": step.parameters,
                "applied_at": step.applied_at.isoformat(),
                "rows_affected": step.rows_affected,
                "data_loss_percentage": step.data_loss_percentage,
                "is_valid": step.is_valid,
                "validation_errors": step.validation_errors
            }
            for step in config.transformation_steps
        ]

        return {
            "config_id": config.config_id,
            "dataset_id": config.dataset_id,
            "user_id": config.user_id,
            "transformation_steps": steps,
            "is_applied": config.is_applied,
            "applied_at": config.applied_at.isoformat() if config.applied_at else None,
            "current_file_path": config.current_file_path,
            "total_transformations": config.total_transformations,
            "total_data_loss": config.total_data_loss,
            "parent_config_id": config.parent_config_id,
            "version": config.version,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat()
        }