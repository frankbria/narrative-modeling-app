"""
History service for undo/redo transformation operations.

Handles navigation through transformation history, restoring previous dataset versions.
"""

import contextlib
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from app.services.dataset_lease import LeaseBusy
from app.services.dataset_link import (
    DATASET_BUSY,
    ensure_metadata_twin,
    history_key,
    holding_the_dataset,
    record_new_file,
)
from app.services.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.services.versioning_service import VersioningService

if TYPE_CHECKING:
    from app.services.transformation_service import TransformationService

logger = logging.getLogger(__name__)


_OUTSIDE_EDIT = (
    "the dataset has since been changed by an edit that is not in this history, "
    "and going back would discard that change"
)


def _cannot_undo(config: Any) -> str:
    """Why undo is refused: there is nothing before the start, the dataset as it was
    before the first step was never saved (#962), or an outside edit stands in the way
    (#851)."""
    if config.current_position < 0:
        return "Cannot undo: already at the beginning of history"
    if config.current_position == 0 and config.undo_floor == 0:
        return "Cannot undo: already at the beginning of history (the data from before this step was not saved)"
    return f"Cannot undo: {_OUTSIDE_EDIT}"


def _undone_to(position: int) -> str:
    if position < 0:
        return "Undone to the dataset as it was before its first step"
    return f"Undone to position {position}"


def _version_at(config: Any) -> str | None:
    """The version the cursor points at: a step's, or before the first step the one the
    dataset was at then (#962)."""
    if config.current_position < 0:
        return config.base_version_id
    return config.transformation_steps[config.current_position].version_id


@contextlib.asynccontextmanager
async def _holding(dataset_id: str, user_id: str) -> AsyncIterator[None]:
    """The dataset's lease for a move through its history (#1022). Taken before the
    history is read, so an undo that lands during an apply runs after it, on the history
    the apply left. A lease still held when the wait runs out is the route's 400."""
    try:
        async with holding_the_dataset(dataset_id, user_id):
            yield
    except LeaseBusy:
        raise ValidationError(message=DATASET_BUSY, details={"dataset_id": dataset_id})


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

    async def _config(self, dataset_id: str, user_id: str):
        """The dataset's transformation history, owned by `user_id` (#800).

        Looked up by dataset, not by `config_id`: the two are different id spaces, so the
        old `get_transformation_config(dataset_id)` matched nothing and every history
        route answered 404. Scoped to the owner, so another tenant's dataset answers the
        same NotFoundError as an unknown one rather than a distinguishable 403.
        """
        # Under the dataset's own id: a `/datasets` upload has a second one (its upload
        # record's), and the steps are recorded under the first (#851).
        config = await self.transformation_service.get_dataset_config(
            await history_key(dataset_id, user_id), user_id
        )
        if not config:
            raise NotFoundError(
                resource_type="Transformation config",
                resource_id=dataset_id,
                message=f"Transformation config not found for dataset {dataset_id}"
            )
        return config

    async def _move_to_step(self, dataset_id: str, user_id: str, version_id: str | None) -> None:
        """Point the dataset (and its twin) at the version a history step produced.

        Raises rather than returning quietly: a step with nothing to restore used to
        answer 200 and move the cursor while the data stayed where it was (#800 review).
        The caller saves the cursor only after this succeeds.
        """
        # Version metadata only; the move needs its URL and shape, not its content.
        version = await self.versioning_service.get_version(version_id, mark_accessed=False) if version_id else None
        if not version:
            raise ValidationError(
                message="This history step has no saved version, so the data cannot be restored to it",
                details={"version_id": version_id},
            )
        dataset = await ensure_metadata_twin(dataset_id, user_id)
        if not dataset:
            raise NotFoundError(resource_type="Dataset", resource_id=dataset_id)
        # Bring the restored version's shape with the move so BOTH twins describe the
        # restored file — record_new_file copies these onto the UserData twin, and a stale
        # count silently mis-drives the training mode recommendation (model_training reads
        # num_rows/num_columns off the twin). #629, same twin-drift class as #467/#524.
        dataset.num_rows = version.num_rows
        dataset.num_columns = version.num_columns
        dataset.columns = version.columns
        dataset.data_schema = _schema_for(dataset.data_schema, version.columns)
        # Move file_path, s3_url AND the dual-written UserData twin together (#629):
        # setting file_path alone left the twin (which training reads by ObjectId) and
        # s3_url at the pre-navigation file, so training silently used the state the user
        # had just navigated away from, the same twin-drift #467 fixed for forward writers.
        await record_new_file(dataset, version.s3_url, in_history=True)
        logger.info(f"Moved dataset {dataset_id} to version url {version.s3_url}")

    async def undo(self, dataset_id: str, user_id: str) -> dict[str, Any]:
        """Move back one step, holding the dataset's lease (#1022)."""
        async with _holding(dataset_id, user_id):
            return await self._undo(dataset_id, user_id)

    async def _undo(self, dataset_id: str, user_id: str) -> dict[str, Any]:
        """
        Move back one step in transformation history.

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier (for authorization)

        Returns:
            Dictionary with success, version_id, current_position, message

        Raises:
            NotFoundError: If transformation config not found
            ValidationError: If cannot undo (at beginning of history)
        """
        config = await self._config(dataset_id, user_id)

        # Check if can undo
        if not config.can_undo():
            raise ValidationError(
                message=_cannot_undo(config),
                details={"current_position": config.current_position}
            )

        # Decrement position
        config.current_position -= 1
        version_id = _version_at(config)

        await self._move_to_step(dataset_id, user_id, version_id)

        # Save config
        await config.save()
        logger.info(f"Undone transformation for dataset {dataset_id}, position now {config.current_position}")

        return {
            "success": True,
            "version_id": version_id,
            "current_position": config.current_position,
            "message": _undone_to(config.current_position),
        }

    async def redo(self, dataset_id: str, user_id: str) -> dict[str, Any]:
        """Move forward one step, holding the dataset's lease (#1022)."""
        async with _holding(dataset_id, user_id):
            return await self._redo(dataset_id, user_id)

    async def _redo(self, dataset_id: str, user_id: str) -> dict[str, Any]:
        """
        Move forward one step in transformation history.

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier (for authorization)

        Returns:
            Dictionary with success, version_id, current_position, message

        Raises:
            NotFoundError: If transformation config not found
            ValidationError: If cannot redo (at end of history)
        """
        config = await self._config(dataset_id, user_id)

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

        await self._move_to_step(dataset_id, user_id, version_id)

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
        """Move to a step, holding the dataset's lease (#1022)."""
        async with _holding(dataset_id, user_id):
            return await self._jump_to_position(dataset_id, position, user_id)

    async def _jump_to_position(self, dataset_id: str, position: int, user_id: str) -> dict[str, Any]:
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
            ValidationError: If position is invalid
        """
        config = await self._config(dataset_id, user_id)

        # Validate position
        if not 0 <= position < len(config.transformation_steps):
            raise ValidationError(
                message=f"Invalid position {position}",
                details={
                    "position": position,
                    "valid_range": f"0-{len(config.transformation_steps) - 1}"
                }
            )

        if not config.can_reach(position):
            raise ValidationError(
                message=f"Cannot go back to step {position}: {_OUTSIDE_EDIT}",
                details={"position": position},
            )

        # Update position
        config.current_position = position

        # Get version at new position
        target_step = config.transformation_steps[config.current_position]
        version_id = target_step.version_id

        await self._move_to_step(dataset_id, user_id, version_id)

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
        """
        config = await self._config(dataset_id, user_id)

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
        """Build a human-readable description of a transformation step: the one it was
        recorded with (an edit made outside the engine, #923), else one from its type."""
        if step.description:
            return step.description
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
        """
        config = await self._config(dataset_id, user_id)

        # The model's own reset (steps, counters, applied state), plus the cursor it leaves alone.
        config.clear_transformations()
        config.current_position = -1

        # Save config
        await config.save()
        logger.info(f"Cleared transformation history for dataset {dataset_id}")

        return True


def _schema_for(schema: list, columns: list[str] | None) -> list:
    """The schema entries for the columns the restored file has (#1061): an undone
    feature column must not stay described. A version that recorded no columns keeps
    the schema as it is. Redoing the column brings it back without an entry, which
    says less than the file has, never more."""
    if not columns:
        return schema
    return [field for field in schema if field.field_name in columns]

