"""
Transformation service for TransformationConfig operations.

This service handles transformation configuration operations using the new
TransformationConfig model, delegating actual transformation execution to
the existing TransformationEngine.
"""

import logging
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC
from typing import Any

import pandas as pd

from app.models.transformation import (
    TransformationConfig,
    TransformationStep,
    TransformationValidation,
)
from app.services.base_service import BaseService
from app.services.data_processing.quality_assessment import QualityAssessmentService
from app.services.dataset_lease import LeaseBusy
from app.services.dataset_link import (
    DATASET_BUSY,
    close_history,
    ensure_metadata_twin,
    holding_the_dataset,
    record_new_file,
)
from app.services.exceptions import NotFoundError, OperationError
from app.services.transformation_engine.transformation_engine import (
    TransformationEngine,
    TransformationResult,
    TransformationType,
)
from app.utils.s3 import downloadable_url

logger = logging.getLogger(__name__)


def _name_step(result: TransformationResult, number: int, step_type: TransformationType) -> TransformationResult:
    result.error = f"Step {number} ({step_type.value}) failed: {result.error}"
    return result


@dataclass
class _RanStep:
    """One transformation as it ran: what it was asked to do, and the frame either side."""

    transformation_type: str
    parameters: dict[str, Any]
    before: pd.DataFrame
    after: pd.DataFrame
    result: Any
    elapsed_ms: int
    description: str | None = None


class _StepFailed(Exception):
    """A transformation reported failure; the message is the one the caller is shown."""


#: The change was applied but its steps could not be recorded, so it cannot be undone (#1060).
STEPS_NOT_RECORDED = (
    "The change was applied, but it could not be added to the undo history, so it cannot be undone."
)


def _failed(dataset_id: str, started: float, error: str) -> dict[str, Any]:
    """The answer for an apply that wrote nothing, with the reason to show."""
    return {
        "success": False,
        "dataset_id": dataset_id,
        "transformation_id": "",
        "execution_time_ms": _elapsed_ms(started),
        "error": error,
    }


def _elapsed_ms(started: float) -> int:
    import time

    return int((time.time() - started) * 1000)


class TransformationService(BaseService[TransformationConfig]):
    """Service for transformation operations using TransformationConfig."""

    model_class = TransformationConfig
    resource_name = "TransformationConfig"

    def __init__(self):
        """Initialize service with transformation engine."""
        self.engine = TransformationEngine()
        self.quality_service = QualityAssessmentService()

    @staticmethod
    def _infer_column_types(df: pd.DataFrame) -> dict[str, str]:
        """Coarse pandas-dtype -> quality-assessment type map (issue #102).

        Enough for trend scoring; specialised email/phone detection isn't needed here.
        """
        types: dict[str, str] = {}
        for col in df.columns:
            dtype = df[col].dtype
            if pd.api.types.is_integer_dtype(dtype):
                types[col] = "integer"
            elif pd.api.types.is_float_dtype(dtype):
                types[col] = "float"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                types[col] = "datetime"
            elif pd.api.types.is_bool_dtype(dtype):
                types[col] = "boolean"
            else:
                types[col] = "string"
        return types

    async def _assess_quality_dict(self, df: pd.DataFrame) -> dict[str, Any] | None:
        """Best-effort quality report as a JSON-native dict, or None on failure."""
        try:
            report = await self.quality_service.assess_quality(
                df, self._infer_column_types(df)
            )
            return report.model_dump(mode="json")
        except Exception as exc:  # never break the transformation on a quality error
            logger.warning(f"Quality assessment skipped during versioning: {exc}")
            return None

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
        transformation_steps: list[TransformationStep] | None = None,
        current_file_path: str | None = None,
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

    async def _version_for(
        self,
        dataset: Any,
        dataset_id: str,
        user_id: str,
        df: Any,
        transformed_df: Any,
        transformation_type: str,
        parameters: dict[str, Any],
        rows_affected: int,
        execution_time_ms: int,
        config_id: str,
        derived_from: str | None = None,
    ) -> str | None:
        """Record the transformed frame as a dataset version (lineage + quality trend);
        the version id the history step points at, None when there is no parent version.

        `derived_from` is the version the step before this one wrote, in the same apply.
        """

        # Create dataset version for transformation BEFORE adding step
        # Get parent version (most recent version for this dataset)
        from app.models.version import DatasetVersion
        from app.services.versioning_service import versioning_service
        # Owner-scoped (#559): the service now refuses a foreign parent, so an
        # unscoped "latest" here would turn a stray row into a denial.
        parent_version = await self._parent_version(
            DatasetVersion, dataset, user_id, await self._known_parent(derived_from, config_id)
        )

        version_id = None
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

            # Build transformation steps for lineage.
            # Use the TransformationStep schema field names (step_type/affected_columns/
            # rows_affected); the previous dict used transformation_type/column/columns,
            # which raised a ValidationError that aborted every versioned transform.
            affected_columns = [
                c for c in (parameters.get("column"), *(parameters.get("columns") or []))
                if c
            ]
            transformation_steps = [
                {
                    "step_type": transformation_type,
                    "parameters": parameters,
                    "affected_columns": affected_columns,
                    "rows_affected": rows_affected,
                    # TransformationStep.execution_time is documented in seconds.
                    "execution_time": execution_time_ms / 1000
                }
            ]

            # Quality trend tracking (issue #102, AC3): assess before/after,
            # best-effort — a quality failure must never break the transformation.
            quality_before = await self._assess_quality_dict(df)
            quality_after = await self._assess_quality_dict(transformed_df)

            version_id = await self._lineage_version(
                versioning_service,
                dict(
                    parent_version_id=parent_version.version_id,
                    transformed_content=transformed_content,
                    transformation_steps=transformation_steps,
                    dataset_metadata=dataset,
                    user_id=user_id,
                    description=f"Applied {transformation_type} transformation",
                    transformation_config_id=config_id,
                    quality_before=quality_before,
                    quality_after=quality_after,
                ),
            )
        return version_id

    @staticmethod
    async def _lineage_version(versioning_service: Any, version_args: dict[str, Any]) -> str | None:
        """Write the transformation's version; None if it cannot be written.

        Best-effort, like the base version: a failed lineage copy must not fail the
        user's transformation, which has already been written. The step is then recorded
        without a version, and undo says so instead of restoring nothing (#800, #850).
        """
        try:
            version, _lineage = await versioning_service.create_transformation_version(**version_args)
        except Exception:
            logger.warning("No version for this transformation; undo cannot restore to it", exc_info=True)
            return None
        return version.version_id

    async def _parent_version(
        self, version_model: Any, dataset: Any, user_id: str, known: str | None = None
    ) -> Any:
        """The version the frame being transformed is.

        `known` is its id when the history says which one that is. Otherwise the latest
        version, or a base version made now if there is none. The latest is right for a
        dataset that has only moved forward; after an undo it is the version that was
        undone, and the lineage then said a result came from data the user had taken
        back (#852).
        """
        owned = {"dataset_id": dataset.dataset_id, "user_id": user_id}
        if known:
            at_cursor = await version_model.find_one({**owned, "version_id": known})
            if at_cursor:
                return at_cursor
        latest = await version_model.find(owned).sort("-version_number").first_or_none()
        return latest or await self._base_version(dataset, user_id)

    async def _known_parent(self, derived_from: str | None, config_id: str) -> str | None:
        """The version this step derives from, when it is known: the one the step before
        it wrote in the same apply, else the one at the history's cursor."""
        return derived_from or await self._version_at_cursor(config_id)

    async def _version_at_cursor(self, config_id: str) -> str | None:
        """The version the dataset's history says it is at now: the step at the cursor,
        or the base when every step has been undone. None when the history does not
        know (no step yet and no base, or a step whose version was never written)."""
        config = await self.get_by_id(config_id, check_ownership=False)
        if config is None:
            return None
        if config.current_position < 0:
            return config.base_version_id
        return config.transformation_steps[config.current_position].version_id

    async def _base_version(self, dataset: Any, user_id: str) -> Any:
        """Version 1 for a dataset that has none, from its current (untransformed) file.

        A UI upload's twin starts without one (#850), as does a dataset the feature builder
        made; without it every history step has no version and undo refuses. The hash is
        taken from the stored object's own bytes, so a no-op first transformation cannot
        deduplicate onto it (#857 review). Best-effort, retried on the next apply.
        """
        from app.services.s3_service import s3_service
        from app.services.versioning_service import versioning_service
        from app.utils.s3 import downloadable_url, resolve_validated_object

        try:
            _, key = resolve_validated_object(downloadable_url(dataset.file_path, dataset.s3_url))
            return await versioning_service.create_base_version(
                dataset_metadata=dataset,
                file_content=await s3_service.download_file_bytes(key),
                user_id=user_id,
            )
        except Exception:
            logger.warning("No base version for dataset %s", dataset.dataset_id, exc_info=True)
            return None

    async def _history_config_id(
        self, dataset_id: str, user_id: str, timestamp: float, file_path: str
    ) -> str:
        """The dataset's history config, created on its first transformation (#800).
        Minting one per call left every config a one-step history that no lookup by
        dataset could assemble."""
        existing = await self.get_dataset_config(dataset_id, user_id)
        if existing:
            return existing.config_id
        config_id = f"config_{dataset_id}_{int(timestamp)}"
        await self.create_transformation_config(
            user_id=user_id, dataset_id=dataset_id, config_id=config_id, current_file_path=file_path
        )
        return config_id

    async def get_transformation_config(
        self,
        config_id: str
    ) -> TransformationConfig | None:
        """
        Retrieve transformation configuration by config ID.

        Args:
            config_id: Configuration identifier

        Returns:
            TransformationConfig instance or None if not found
        """
        return await self.get_by_id(config_id, check_ownership=False)

    async def get_dataset_config(
        self, dataset_id: str, user_id: str
    ) -> TransformationConfig | None:
        """The dataset's history config: its newest, owned by `user_id` (#800).

        Steps accumulate in one config per dataset (`apply_transformation` reuses it), so
        undo/redo move through one ordered list. Datasets transformed before #800 hold one
        config per step; the newest is the current state.
        """
        return await TransformationConfig.find(
            TransformationConfig.dataset_id == dataset_id,
            TransformationConfig.user_id == user_id,
        ).sort("-created_at").first_or_none()

    async def list_transformation_configs(
        self,
        dataset_id: str
    ) -> list[TransformationConfig]:
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
        ).sort("-created_at").to_list()

    async def add_transformation_step(
        self,
        config_id: str,
        transformation_type: str,
        column: str | None = None,
        columns: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        version_id: str | None = None,
        description: str | None = None,
    ) -> TransformationConfig:
        """
        Add a transformation step to configuration.

        Args:
            config_id: Configuration identifier
            transformation_type: Type of transformation
            column: Single column to transform (optional)
            columns: Multiple columns to transform (optional)
            parameters: Transformation parameters (optional)
            version_id: Dataset version ID after this transformation (optional)
            description: What the history lists for the step (optional)

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
            parameters=parameters,
            version_id=version_id,
            description=description,
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
            True when deleted

        Raises:
            NotFoundError: If the resource doesn't exist or isn't the caller's (#985)
        """
        return await self.delete(config_id, user_id, soft_delete=False)

    async def get_applied_configs(
        self,
        dataset_id: str
    ) -> list[TransformationConfig]:
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
            TransformationConfig.is_applied
        ).sort("-created_at").to_list()

    async def preview_transformation(
        self,
        user_id: str,
        dataset_id: str,
        steps: list[tuple[TransformationType, dict[str, Any]]],
        preview_rows: int = 10
    ) -> dict[str, Any]:
        """
        Preview a pipeline without applying it: every step but the last runs on the
        whole frame, in order, and the last is previewed on the result (#855).

        Args:
            user_id: User identifier (for ownership verification)
            dataset_id: Dataset identifier
            steps: (transformation type, parameters) pairs, in pipeline order
            preview_rows: Number of rows to preview

        Returns:
            Preview result with before/after samples

        Raises:
            NotFoundError: If dataset not found or user doesn't own it
            OperationError: If transformation preview fails
        """
        from app.services.transformation_engine.data_utils import get_dataframe_from_s3

        # Get dataset with ownership verification
        # Either id space: a UI upload's UserData id resolves to its twin (#850).
        dataset = await ensure_metadata_twin(dataset_id, user_id)

        if not dataset:
            raise NotFoundError(
                resource_type="Dataset",
                resource_id=dataset_id,
                message=f"Dataset {dataset_id} not found or not owned by user"
            )

        try:
            # Load data from S3
            file_path = downloadable_url(dataset.file_path, dataset.s3_url)  # a raw key must not reach the URL-only downloader (#466)
            df = await get_dataframe_from_s3(file_path)

            result = self._preview_steps(df, steps, preview_rows)

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
                details={"dataset_id": dataset_id, "steps": [t.value for t, _ in steps]}
            )

    def _preview_steps(
        self, df: pd.DataFrame, steps: list[tuple[TransformationType, dict[str, Any]]], n_rows: int
    ) -> TransformationResult:
        """Apply every step but the last in order, then preview the last on the result.
        A failure names its step, so the user knows which node to fix. `stats_before`
        describes the untransformed rows, which is what the Before table shows."""
        *earlier, (last_type, last_parameters) = steps
        before = self.engine._calculate_stats(df.head(n_rows))
        for number, (step_type, parameters) in enumerate(earlier, start=1):
            frame, result = self.engine.apply_transformation_frame(df, step_type, parameters)
            if frame is None:
                return _name_step(result, number, step_type)
            df = frame
        result = self.engine.preview_transformation(
            df=df, transformation_type=last_type, parameters=last_parameters, n_rows=n_rows
        )
        if not result.success:
            return _name_step(result, len(steps), last_type)
        result.stats_before = before
        return result

    async def apply_transformation(
        self,
        user_id: str,
        dataset_id: str,
        transformation_type: str,
        parameters: dict[str, Any]
    ) -> dict[str, Any]:
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
        return await self.apply_pipeline(user_id, dataset_id, [(transformation_type, parameters)])

    async def apply_pipeline(
        self, user_id: str, dataset_id: str, steps: list[tuple[str, dict[str, Any]]]
    ) -> dict[str, Any]:
        """Apply `steps` in order, each as its own history step and version (#851).

        All or nothing: every step is run on the frame first, and nothing is written
        unless all of them succeed. Then each is recorded exactly as a single apply is,
        so undo walks back through a pipeline (or a recipe) one transformation at a
        time. Before #851 the pipeline route moved the dataset with no step at all, and
        an undo afterwards restored a version from before it.

        One apply at a time for a dataset (#853). Two at once both transformed the same
        starting file, and a first pair also created two histories. The second now waits
        for the first and transforms what it wrote; if the first is still running when
        the wait runs out, the second is reported as failed and nothing is written.

        Raises:
            NotFoundError: If dataset not found or user doesn't own it
            OperationError: If a transformation raises while it runs
        """
        import time

        started = time.time()
        try:
            async with holding_the_dataset(dataset_id, user_id):
                return await self._apply_holding_the_lease(user_id, dataset_id, steps, started)
        except LeaseBusy:
            return _failed(dataset_id, started, DATASET_BUSY)

    async def _apply_holding_the_lease(
        self, user_id: str, dataset_id: str, steps: list[tuple[str, dict[str, Any]]], started: float
    ) -> dict[str, Any]:
        """`apply_pipeline`'s work. The dataset is read here, with the lease held, so it
        is the file as the apply before this one left it."""
        from app.services.transformation_engine.data_utils import get_dataframe_from_s3

        # Either id space: a UI upload's UserData id resolves to its twin (#850).
        dataset = await ensure_metadata_twin(dataset_id, user_id)
        if not dataset:
            raise NotFoundError(
                resource_type="Dataset",
                resource_id=dataset_id,
                message=f"Dataset {dataset_id} not found or not owned by user {user_id}"
            )
        try:
            # a raw key must not reach the URL-only downloader (#466)
            df = await get_dataframe_from_s3(downloadable_url(dataset.file_path, dataset.s3_url))
            if len(steps) > 1:
                # Dry run, so nothing is written unless every step succeeds. The steps are
                # run again below rather than kept: a pipeline then never holds more than
                # two frames, where keeping them would hold one per step.
                deque(self._run(df, steps), maxlen=0)
            # Recorded under the dataset's own id, whichever id the request named it by:
            # keyed on the request's, the same dataset grew one history per id space,
            # and an undo in one discarded the steps listed in the other (#851).
            return await self._record_steps(
                dataset, dataset.dataset_id, user_id, self._run(df, steps), started
            )
        except _StepFailed as failed:
            return _failed(dataset_id, started, str(failed))
        except ValueError as e:
            raise OperationError(
                message="Failed to apply transformation",
                operation="apply_transformation",
                original_error=e,
                details={"dataset_id": dataset_id, "user_id": user_id},
            )

    def _run(self, df: pd.DataFrame, steps: list[tuple[str, dict[str, Any]]]) -> Iterator["_RanStep"]:
        """Run each step on the frame the one before it produced.

        Raises _StepFailed at the first step that reports failure. A single step keeps
        the engine's own message; in a longer pipeline the message names the step."""
        import time

        for transformation_type, parameters in steps:
            step_started = time.time()  # each step's own time, not the pipeline's so far
            # Keep the DataFrame across steps, no per-step list-of-dicts round-trip (#542).
            after, result = self.engine.apply_transformation_frame(
                df=df, transformation_type=TransformationType(transformation_type), parameters=parameters
            )
            if not result.success or after is None:
                raise _StepFailed(
                    result.error if len(steps) == 1
                    else f"Transformation '{transformation_type}' failed: {result.error}"
                )
            yield _RanStep(transformation_type, parameters, df, after, result, _elapsed_ms(step_started))
            df = after

    async def _record_steps(
        self, dataset: Any, dataset_id: str, user_id: str, ran: Iterator["_RanStep"], started: float
    ) -> dict[str, Any]:
        """Record what ran: a version per step, then the history steps and one move.

        Storage first, the database after. Every version and the dataset's new file are
        written before any history step is recorded or the dataset is moved, so a failed
        upload part-way through a pipeline leaves the dataset and its history exactly as
        they were. Only the last step's frame becomes a `transformed/` file: undo restores
        the earlier ones from their versions.
        """
        from datetime import datetime

        done: dict[str, Any] = {
            "success": True,
            "dataset_id": dataset_id,
            "transformation_id": "",
            "affected_rows": 0,
            "affected_columns": [],
            "warnings": [],
            "schema": {},
        }
        timestamp = datetime.now(UTC).timestamp()
        recorded, last = await self._write_versions(dataset, dataset_id, user_id, ran, done, timestamp)
        if last is not None:
            await self._move_to(dataset, dataset_id, user_id, recorded, last, done, timestamp)
        # else nothing was asked for (auto-clean with every option off): nothing to write.
        return {**done, "execution_time_ms": _elapsed_ms(started)}

    async def _write_versions(
        self, dataset: Any, dataset_id: str, user_id: str, ran: Iterator["_RanStep"],
        done: dict[str, Any], timestamp: float,
    ) -> tuple[list[dict[str, Any]], pd.DataFrame | None]:
        """Write each step's version; the history steps to record, and the last frame."""
        recorded: list[dict[str, Any]] = []
        last: pd.DataFrame | None = None
        written: str | None = None
        for step in ran:
            if not recorded:
                done["transformation_id"] = await self._history_config_id(
                    dataset_id, user_id, timestamp, dataset.s3_url
                )
            # The cursor does not move until every version is written, so a later step
            # of the same apply derives from the last version this apply wrote. A step
            # whose version could not be written is passed over, not derived from.
            recorded.append(await self._versioned(dataset, dataset_id, user_id, step, done, written))
            written = recorded[-1]["version_id"] or written
            if len(recorded) == 1:
                await self._remember_the_start(done["transformation_id"], dataset, recorded[0]["version_id"])
            last = step.after
        return recorded, last

    async def _remember_the_start(self, config_id: str, dataset: Any, first_version_id: str | None) -> None:
        """Record the version the dataset was at before the first step of its history,
        so that step can be undone (#962). Only when that is certain.

        Best effort: a transformation is not failed because its undo could not be
        prepared. Without the record the first step stays where it is, as before.
        """
        try:
            base = await self._version_before(config_id, dataset, first_version_id)
            if base:
                await TransformationConfig.find_one(TransformationConfig.config_id == config_id).update(
                    {"$set": {"base_version_id": base}}
                )
        except Exception:
            logger.warning("Could not record the starting version of history %s", config_id, exc_info=True)

    async def _version_before(self, config_id: str, dataset: Any, first_version_id: str | None) -> str | None:
        """The version the dataset was at before its first step, if that is known.

        The first step's parent is the latest version, which is the file being
        transformed only if the dataset has never moved before: then it is the upload
        itself. A dataset already moved by an edit the history holds no step for has no
        version of its current file, so there is no answer. A history that was undone
        to its start keeps the base it has: that is the file the dataset was restored to.
        """
        from app.services.versioning_service import versioning_service

        config = await self.get_by_id(config_id, check_ownership=False)
        if not self._starts_from_the_upload(config, dataset) or not first_version_id:
            return None
        first = await versioning_service.get_version(first_version_id, mark_accessed=False)
        parent_id = getattr(first, "parent_version_id", None)
        parent = await versioning_service.get_version(parent_id, mark_accessed=False) if parent_id else None
        # The upload's own version, and nothing else: an apply that failed part-way can
        # leave a step's version behind as the latest, and a retry would derive from it.
        return parent_id if getattr(parent, "is_base_version", False) else None

    @staticmethod
    def _starts_from_the_upload(config: Any, dataset: Any) -> bool:
        """A history with no step yet and no base recorded, on a dataset that has never
        moved off the file it was uploaded as."""
        if config is None or config.current_position != -1 or config.base_version_id:
            return False
        return not getattr(dataset, "source_s3_url", None)

    async def _move_to(
        self, dataset: Any, dataset_id: str, user_id: str, recorded: list[dict[str, Any]],
        last: pd.DataFrame, done: dict[str, Any], timestamp: float,
    ) -> None:
        """Upload the final frame, move the dataset to it, then record the steps.

        The move comes first (#1060): recorded first, a move that then failed left a
        history whose steps and `current_file_path` named a file the dataset was never
        on, and the upload cleanup kept that file as owned. Now a failed move records
        nothing, and the cleanup deletes the file."""
        from app.services.transformation_engine.data_utils import upload_dataframe_to_s3

        new_file_path = await upload_dataframe_to_s3(
            last, f"transformed/{user_id}/{dataset_id}_{timestamp}.parquet"
        )
        done["schema"] = {str(col): str(dtype) for col, dtype in last.dtypes.items()}
        done["file_path"] = new_file_path
        # Move the dataset AND its dual-written UserData twin to the transformed
        # artifact (#276, #467): leaving s3_url stale served pre-transform data, and
        # moving only this side severed the (user_id, s3_url) join the twin lives on.
        # in_history: this move has its steps, so it must not close the history (#851).
        await record_new_file(dataset, new_file_path, in_history=True)
        try:
            for step_fields in recorded:
                await self.add_transformation_step(config_id=done["transformation_id"], **step_fields)
            await self.mark_transformations_applied(config_id=done["transformation_id"], file_path=new_file_path)
        except Exception:
            # The dataset is on the new file, so the change happened: say so, and close
            # the history behind it as for any edit no step describes (#851).
            logger.exception("Could not record the steps of an applied transformation on %s", dataset_id)
            await close_history(dataset)
            done["warnings"].append(STEPS_NOT_RECORDED)

    async def _versioned(
        self, dataset: Any, dataset_id: str, user_id: str, step: "_RanStep", done: dict[str, Any],
        derived_from: str | None = None,
    ) -> dict[str, Any]:
        """Write one step's version and add it to the totals; the history step to record for it."""
        version_id = await self._version_for(
            dataset, dataset_id, user_id, step.before, step.after, step.transformation_type,
            step.parameters, step.result.affected_rows, step.elapsed_ms, done["transformation_id"],
            derived_from,
        )
        done["affected_rows"] += step.result.affected_rows
        done["affected_columns"] = sorted({*done["affected_columns"], *step.result.affected_columns})
        done["warnings"] += step.result.warnings
        return {
            "transformation_type": step.transformation_type,
            "column": step.parameters.get("column"),
            # With no column named the engine picks them, so list the ones it changed.
            "columns": step.parameters.get("columns") or step.result.affected_columns or None,
            "parameters": step.parameters,
            "version_id": version_id,
            "description": step.description,
        }

    async def record_edit(
        self, dataset: Any, user_id: str, frames: tuple[pd.DataFrame, pd.DataFrame], *,
        kind: str, parameters: dict[str, Any], description: str, rows_affected: int = 0,
    ) -> str:
        """Record an edit made outside the engine as one history step, and move the
        dataset to its result (#923); the new file's URL.

        A bulk transformation, a data-issue fix and a feature column added in place used
        to move the dataset with no step, which closed the history behind them (#851).
        Each is now written exactly as an engine step is: a version, a step listed with
        `description`, and a move that keeps the history open, so undo restores the step
        before it. Undo restores versions and never re-runs a step, so `kind` need not be
        one the engine executes. `parameters["columns"]` names the columns it changed.

        `dataset` is the `DatasetMetadata` (`ensure_metadata_twin`), and the caller holds
        its lease (#853) and has run the edit: `frames` is the file before and after.
        """
        import time

        before, after = frames
        dataset.num_rows, dataset.num_columns, dataset.columns = len(after), len(after.columns), after.columns.tolist()
        result = TransformationResult(
            success=True, affected_rows=rows_affected, affected_columns=list(parameters.get("columns") or [])
        )
        step = _RanStep(kind, parameters, before, after, result, 0, description)
        done = await self._record_steps(dataset, dataset.dataset_id, user_id, iter([step]), time.time())
        return str(done["file_path"])

    async def get_transformation_history(
        self,
        config_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Get transformation history with lineage.

        Args:
            config_id: Configuration identifier
            user_id: The caller; another account's config is not found (#985)

        Returns:
            Transformation history with steps, timestamps, and lineage

        Raises:
            NotFoundError: If config not found, or not the caller's
        """
        config = await self.get_by_id_or_raise(config_id, user_id)

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