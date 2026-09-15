"""
History service for undo/redo transformation operations.

Handles navigation through transformation history, restoring previous dataset versions.
"""

import logging
from typing import TYPE_CHECKING, Any

from app.models.dataset import DatasetMetadata
from app.services.dataset_link import record_new_file
from app.services.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.services.versioning_service import VersioningService

if TYPE_CHECKING:
    from app.services.transformation_service import TransformationService

logger = logging.getLogger(__name__)


class HistoryService:
    """Service for managing transformation history and undo/redo operations."""

    def __init__(
        self,
        versioning_service: VersioningService,
        transformation_service: "TransformationService"
    ):
        """
        Initialize history service with dependencies.

        Args:
            versioning_service: Service for version management
            transformation_service: Service for transformation operations
        """
        self.versioning_service = versioning_service
        self.transformation_service = transformation_service

    async def undo(self, dataset_id: str, user_id: str) -> dict[str, Any]:
        """
        Move back one step in transformation history.

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier (for authorization)

        Returns:
            Dictionary with success, version_id, current_position, message

        Raises:
            NotFoundError: If transformation config not found
            PermissionDeniedError: If user doesn't own the dataset
            ValidationError: If cannot undo (at beginning of history)
        """
        # Get transformation config
        config = await self.transformation_service.get_transformation_config(dataset_id)
        if not config:
            raise NotFoundError(
                resource_type="Transformation config",
                resource_id=dataset_id,
                message=f"Transformation config not found for dataset {dataset_id}"
            )

        # Check ownership
        if config.user_id != user_id:
            raise PermissionDeniedError(
                message=f"User {user_id} does not own dataset {dataset_id}"
            )

        # Check if can undo
        if not config.can_undo():
            raise ValidationError(
                message="Cannot undo: already at the beginning of history",
                details={"current_position": config.current_position}
            )

        # Decrement position
        config.current_position -= 1

        # Get version at new position
        target_step = config.transformation_steps[config.current_position]
        version_id = target_step.version_id

        if version_id:
            # Update dataset file_path to point to this version
            dataset = await DatasetMetadata.find_one({
                "dataset_id": dataset_id,
                "user_id": user_id
            })

            if dataset:
                # Get version metadata to update file_path (no need to fetch content)
                version = await self.versioning_service.get_version(version_id, mark_accessed=False)
                if version:
                    # Bring the restored version's shape with the move so BOTH twins
                    # describe the restored file — record_new_file copies these onto the
                    # UserData twin, and a stale count silently mis-drives the training
                    # mode recommendation (model_training reads num_rows/num_columns off
                    # the twin). #629, same twin-drift class as #467/#524.
                    dataset.num_rows = version.num_rows
                    dataset.num_columns = version.num_columns
                    dataset.columns = version.columns
                    # Move file_path, s3_url AND the dual-written UserData twin
                    # together (#629) — setting file_path alone left the twin (which
                    # training reads by ObjectId) and s3_url at the pre-undo file, so
                    # training silently used the state the user just navigated away
                    # from, the same twin-drift #467 fixed for forward writers.
                    await record_new_file(dataset, version.s3_url)
                    logger.info(f"Moved dataset {dataset_id} to version url {version.s3_url}")

        # Save config
        await config.save()
        logger.info(f"Undone transformation for dataset {dataset_id}, position now {config.current_position}")

        return {
            "success": True,
            "version_id": version_id,
            "current_position": config.current_position,
            "message": f"Undone to position {config.current_position}"
        }

    async def redo(self, dataset_id: str, user_id: str) -> dict[str, Any]:
        """
        Move forward one step in transformation history.

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier (for authorization)

        Returns:
            Dictionary with success, version_id, current_position, message

        Raises:
            NotFoundError: If transformation config not found
            PermissionDeniedError: If user doesn't own the dataset
            ValidationError: If cannot redo (at end of history)
        """
        # Get transformation config
        config = await self.transformation_service.get_transformation_config(dataset_id)
        if not config:
            raise NotFoundError(
                resource_type="Transformation config",
                resource_id=dataset_id,
                message=f"Transformation config not found for dataset {dataset_id}"
            )

        # Check ownership
        if config.user_id != user_id:
            raise PermissionDeniedError(
                message=f"User {user_id} does not own dataset {dataset_id}"
            )

        # Check if can redo
        if not config.can_redo():
            raise ValidationError(
                message="Cannot redo: already at the end of history",
                details={"current_position": config.current_position}
            )

        # Increment position
        config.current_position += 1

        # Get version at new position
        target_step = config.transformation_steps[config.current_position]
        version_id = target_step.version_id

        if version_id:
            # Update dataset file_path to point to this version
            dataset = await DatasetMetadata.find_one({
                "dataset_id": dataset_id,
                "user_id": user_id
            })

            if dataset:
                # Get version metadata to update file_path (no need to fetch content)
                version = await self.versioning_service.get_version(version_id, mark_accessed=False)
                if version:
                    # Bring the restored version's shape with the move so BOTH twins
                    # describe the restored file — record_new_file copies these onto the
                    # UserData twin, and a stale count silently mis-drives the training
                    # mode recommendation (model_training reads num_rows/num_columns off
                    # the twin). #629, same twin-drift class as #467/#524.
                    dataset.num_rows = version.num_rows
                    dataset.num_columns = version.num_columns
                    dataset.columns = version.columns
                    # Move file_path, s3_url AND the dual-written UserData twin
                    # together (#629) — setting file_path alone left the twin (which
                    # training reads by ObjectId) and s3_url at the pre-undo file, so
                    # training silently used the state the user just navigated away
                    # from, the same twin-drift #467 fixed for forward writers.
                    await record_new_file(dataset, version.s3_url)
                    logger.info(f"Moved dataset {dataset_id} to version url {version.s3_url}")

        # Save config
        await config.save()
        logger.info(f"Redone transformation for dataset {dataset_id}, position now {config.current_position}")

        return {
            "success": True,
            "version_id": version_id,
            "current_position": config.current_position,
            "message": f"Redone to position {config.current_position}"
        }

    async def jump_to_position(self, dataset_id: str, position: int, user_id: str) -> dict[str, Any]:
        """
        Jump to a specific position in transformation history.

        Args:
            dataset_id: Dataset identifier
            position: Target position (0-indexed)
            user_id: User identifier (for authorization)

        Returns:
            Dictionary with success, version_id, current_position, message

        Raises:
            NotFoundError: If transformation config not found
            PermissionDeniedError: If user doesn't own the dataset
            ValidationError: If position is invalid
        """
        # Get transformation config
        config = await self.transformation_service.get_transformation_config(dataset_id)
        if not config:
            raise NotFoundError(
                resource_type="Transformation config",
                resource_id=dataset_id,
                message=f"Transformation config not found for dataset {dataset_id}"
            )

        # Check ownership
        if config.user_id != user_id:
            raise PermissionDeniedError(
                message=f"User {user_id} does not own dataset {dataset_id}"
            )

        # Validate position
        if position < 0 or position >= len(config.transformation_steps):
            raise ValidationError(
                message=f"Invalid position {position}",
                details={
                    "position": position,
                    "valid_range": f"0-{len(config.transformation_steps) - 1}"
                }
            )

        # Update position
        config.current_position = position

        # Get version at new position
        target_step = config.transformation_steps[config.current_position]
        version_id = target_step.version_id

        if version_id:
            # Update dataset file_path to point to this version
            dataset = await DatasetMetadata.find_one({
                "dataset_id": dataset_id,
                "user_id": user_id
            })

            if dataset:
                # Get version metadata to update file_path (no need to fetch content)
                version = await self.versioning_service.get_version(version_id, mark_accessed=False)
                if version:
                    # Bring the restored version's shape with the move so BOTH twins
                    # describe the restored file — record_new_file copies these onto the
                    # UserData twin, and a stale count silently mis-drives the training
                    # mode recommendation (model_training reads num_rows/num_columns off
                    # the twin). #629, same twin-drift class as #467/#524.
                    dataset.num_rows = version.num_rows
                    dataset.num_columns = version.num_columns
                    dataset.columns = version.columns
                    # Move file_path, s3_url AND the dual-written UserData twin
                    # together (#629) — setting file_path alone left the twin (which
                    # training reads by ObjectId) and s3_url at the pre-undo file, so
                    # training silently used the state the user just navigated away
                    # from, the same twin-drift #467 fixed for forward writers.
                    await record_new_file(dataset, version.s3_url)
                    logger.info(f"Moved dataset {dataset_id} to version url {version.s3_url}")

        # Save config
        await config.save()
        logger.info(f"Jumped to position {position} for dataset {dataset_id}")

        return {
            "success": True,
            "version_id": version_id,
            "current_position": config.current_position,
            "message": f"Jumped to position {position}"
        }

    async def get_history(self, dataset_id: str, user_id: str) -> dict[str, Any]:
        """
        Get full transformation history with current position.

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier (for authorization)

        Returns:
            Dictionary matching schemas.HistoryDataResponse: history entries,
            current_position, can_undo, can_redo

        Raises:
            NotFoundError: If transformation config not found
            PermissionDeniedError: If user doesn't own the dataset
        """
        # Get transformation config
        config = await self.transformation_service.get_transformation_config(dataset_id)
        if not config:
            raise NotFoundError(
                resource_type="Transformation config",
                resource_id=dataset_id,
                message=f"Transformation config not found for dataset {dataset_id}"
            )

        # Check ownership
        if config.user_id != user_id:
            raise PermissionDeniedError(
                message=f"User {user_id} does not own dataset {dataset_id}"
            )

        # Return history in the API contract shape (schemas.HistoryDataResponse);
        # previously this returned a transformation_steps list that did not
        # match the response model, so GET /history always failed validation
        return {
            "dataset_id": dataset_id,
            "history": [
                {
                    "position": position,
                    "transformation_type": step.transformation_type,
                    "description": self._describe_step(step),
                    "timestamp": step.applied_at.isoformat(),
                    "affected_columns": (
                        [step.column] if step.column else list(step.columns or [])
                    ),
                    "rows_affected": step.rows_affected,
                    "version_id": step.version_id,
                }
                for position, step in enumerate(config.transformation_steps)
            ],
            "current_position": config.current_position,
            "can_undo": config.can_undo(),
            "can_redo": config.can_redo()
        }

    @staticmethod
    def _describe_step(step) -> str:
        """Build a human-readable description of a transformation step."""
        # transformation_type may surface as a TransformationType enum member;
        # str() on a str-Enum yields 'TransformationType.X', so use .value
        raw_type = step.transformation_type
        label = getattr(raw_type, "value", raw_type).replace("_", " ")
        columns = [step.column] if step.column else list(step.columns or [])
        if columns:
            return f"Applied {label} to {', '.join(columns)}"
        return f"Applied {label}"

    async def clear_history(self, dataset_id: str, user_id: str) -> bool:
        """
        Clear all transformation history.

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier (for authorization)

        Returns:
            True if history cleared successfully

        Raises:
            NotFoundError: If transformation config not found
            PermissionDeniedError: If user doesn't own the dataset
        """
        # Get transformation config
        config = await self.transformation_service.get_transformation_config(dataset_id)
        if not config:
            raise NotFoundError(
                resource_type="Transformation config",
                resource_id=dataset_id,
                message=f"Transformation config not found for dataset {dataset_id}"
            )

        # Check ownership
        if config.user_id != user_id:
            raise PermissionDeniedError(
                message=f"User {user_id} does not own dataset {dataset_id}"
            )

        # Clear history
        config.transformation_steps = []
        config.current_position = -1

        # Save config
        await config.save()
        logger.info(f"Cleared transformation history for dataset {dataset_id}")

        return True
