"""
Bulk transformation service for processing multiple columns in parallel.

This service handles bulk transformation operations that apply the same
transformation to multiple columns simultaneously with progress tracking.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from threading import Thread
from typing import Any

import pandas as pd
from beanie import PydanticObjectId

from app.middleware.error_handlers import internal_error_message
from app.models.bulk_transformation import (
    BulkJobStatus,
    BulkTransformationJob,
    BulkTransformationProgress,
    BulkTransformationResult,
    ColumnResult,
    ColumnSelectionPattern,
    PatternType,
)
from app.models.dataset import DatasetMetadata, SchemaField
from app.services.dataset_link import ensure_metadata_twin, record_new_file
from app.services.exceptions import NotFoundError, OperationError, ValidationError
from app.services.redis_cache import cache_service
from app.services.transformation_engine.data_utils import (
    get_dataframe_from_s3,
    upload_dataframe_to_s3,
)
from app.services.transformation_engine.transformation_engine import (
    TransformationEngine,
    TransformationType,
)
from app.utils.s3 import downloadable_url

logger = logging.getLogger(__name__)

# Constants for limits and configuration
MAX_COLUMNS_PER_JOB = 100
MAX_CONCURRENT_JOBS_PER_USER = 5
REGEX_TIMEOUT_SECONDS = 2
PROGRESS_UPDATE_FREQUENCY = 5  # Update DB every N columns


def safe_regex_search(pattern: str, text: str, timeout: int = REGEX_TIMEOUT_SECONDS) -> bool:
    """
    Thread-based regex search with timeout protection (cross-platform).

    This approach works on both Unix and Windows systems, unlike signal-based
    timeouts. If the regex takes longer than the timeout, we return False
    to prevent ReDoS attacks.

    Args:
        pattern: Regex pattern to search for
        text: Text to search in
        timeout: Maximum seconds to wait for regex to complete

    Returns:
        True if pattern matches, False if no match or timeout/error
    """
    result: dict[str, Any] = {'match': False, 'error': None}

    def run_regex() -> None:
        try:
            result['match'] = bool(re.search(pattern, text, re.IGNORECASE))
        except re.error as e:
            result['error'] = e

    thread = Thread(target=run_regex, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        # Timeout occurred - thread is still running but we return False
        # Note: Python threads cannot be forcibly killed, but daemon=True
        # ensures they won't block process exit
        logger.warning(f"Regex pattern timed out after {timeout}s: {pattern[:50]}...")
        return False

    if result['error']:
        logger.warning(f"Invalid regex pattern: {pattern} - {result['error']}")
        return False

    return result['match']


@dataclass
class _ColumnRun:
    """What a job's columns produced: the frame after them, and each column's outcome."""

    df: pd.DataFrame
    results: list[ColumnResult] = dataclass_field(default_factory=list)
    succeeded: list[str] = dataclass_field(default_factory=list)
    failed: list[dict[str, Any]] = dataclass_field(default_factory=list)

    def add(self, column: str, new_df: pd.DataFrame, result: ColumnResult) -> None:
        self.results.append(result)
        if result.success:
            self.succeeded.append(column)
            self.df = new_df
        else:
            self.failed.append({"column_name": column, "error": result.error})


def _column_params(
    column: str, global_parameters: dict[str, Any], per_column_params: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """The parameters one column runs with: the job's, then its own overrides."""
    return {**global_parameters, **per_column_params.get(column, {}), "column": column}


def _failed_preview(column: str) -> dict[str, Any]:
    return {
        "column_name": column,
        "success": False,
        "preview_data": None,
        "stats_before": None,
        "stats_after": None,
        "affected_rows": 0,
        # Returned inside a 200 body; never str(e) (#637).
        "error": internal_error_message(f"Preview for column {column!r}"),
        "warnings": [],
    }


def _preview_summary(column_previews: list[dict[str, Any]]) -> dict[str, Any]:
    succeeded = [p for p in column_previews if p["success"]]
    failed = len(column_previews) - len(succeeded)
    return {
        "success": failed == 0,
        "column_previews": column_previews,
        "total_estimated_rows_affected": sum(p["affected_rows"] for p in succeeded),
        "total_columns": len(column_previews),
        "successful_previews": len(succeeded),
        "failed_previews": failed,
        "error": None if failed == 0 else f"{failed} column(s) failed preview",
        "warnings": [],
    }


def _require_valid_request(selected_columns: list[str], transformation_type: str) -> None:
    """Refuse a bulk request before anything is looked up or created."""
    if not selected_columns:
        raise ValidationError(message="selected_columns cannot be empty", field="selected_columns")
    if len(selected_columns) > MAX_COLUMNS_PER_JOB:
        raise ValidationError(
            message=f"Cannot transform more than {MAX_COLUMNS_PER_JOB} columns at once",
            field="selected_columns",
        )
    if len(selected_columns) != len(set(selected_columns)):
        raise ValidationError(message="Duplicate column names in selected_columns", field="selected_columns")
    if transformation_type not in {t.value for t in TransformationType}:
        raise ValidationError(
            message=f"Invalid transformation_type: {transformation_type}", field="transformation_type"
        )


async def _require_job_slot(user_id: str) -> None:
    """Rate limit: a user's unfinished bulk jobs are capped."""
    active_jobs = await BulkTransformationJob.find({
        "user_id": user_id,
        "status": {"$in": [BulkJobStatus.PENDING, BulkJobStatus.RUNNING]},
    }).count()
    if active_jobs >= MAX_CONCURRENT_JOBS_PER_USER:
        raise OperationError(
            message=f"Maximum concurrent bulk transformation jobs ({MAX_CONCURRENT_JOBS_PER_USER}) reached. "
                    "Please wait for existing jobs to complete.",
            operation="apply_bulk_transformation",
            details={"active_jobs": active_jobs, "limit": MAX_CONCURRENT_JOBS_PER_USER},
        )


async def _owned_dataset(user_id: str, dataset_id: str) -> DatasetMetadata:
    """The caller's dataset, named by either of its ids (#856).

    The upload page hands every later stage a `UserData` id; looked up as a
    `DatasetMetadata` id alone, every bulk route answered 404 for it.
    """
    dataset = await ensure_metadata_twin(dataset_id, user_id)
    if not dataset:
        raise NotFoundError(
            resource_type="Dataset",
            resource_id=dataset_id,
            message=f"Dataset {dataset_id} not found or not owned by user",
        )
    return dataset


class BulkTransformationService:
    """Service for bulk transformation operations on multiple columns."""

    def __init__(self) -> None:
        """Initialize service with transformation engine."""
        self.engine = TransformationEngine()
        # Track active background tasks for proper cleanup and cancellation
        self._active_tasks: dict[str, asyncio.Task[None]] = {}

    def _cleanup_task(self, job_id: str, task: asyncio.Task) -> None:
        """Callback to clean up task reference when done."""
        if job_id in self._active_tasks:
            del self._active_tasks[job_id]

        # Log any unhandled exceptions from the task
        if task.done() and not task.cancelled():
            exc = task.exception()
            if exc:
                logger.error(f"Background task for job {job_id} failed: {exc}")

    async def select_columns_by_pattern(
        self,
        user_id: str,
        dataset_id: str,
        pattern: ColumnSelectionPattern
    ) -> list[dict[str, Any]]:
        """
        Select columns matching a pattern.

        Args:
            user_id: User identifier
            dataset_id: Dataset identifier
            pattern: Column selection pattern

        Returns:
            List of matching columns with metadata

        Raises:
            NotFoundError: If dataset not found
        """
        dataset = await _owned_dataset(user_id, dataset_id)

        matching_columns = []

        for field in dataset.data_schema:
            if self._matches_pattern(field, pattern):
                matching_columns.append({
                    "column_name": field.field_name,
                    "field_type": field.field_type,
                    "missing_values": field.missing_values,
                    "unique_values": field.unique_values,
                    "is_constant": field.is_constant,
                    "is_high_cardinality": field.is_high_cardinality,
                })

        return matching_columns

    def _matches_pattern(
        self,
        field: SchemaField,
        pattern: ColumnSelectionPattern
    ) -> bool:
        """Check if a field matches the selection pattern."""
        criteria = pattern.criteria

        if pattern.pattern_type == PatternType.DATA_TYPE:
            types = criteria.get("types", [])
            return field.field_type in types

        elif pattern.pattern_type == PatternType.NAME_PATTERN:
            regex_pattern = criteria.get("pattern", "")
            return safe_regex_search(regex_pattern, field.field_name)

        elif pattern.pattern_type == PatternType.QUALITY_METRIC:
            metric = criteria.get("metric", "")
            threshold = criteria.get("threshold", 0)
            operator = criteria.get("operator", "gt")  # gt, lt, eq, gte, lte

            if metric == "missing_values":
                value = field.missing_values
            elif metric == "unique_values":
                value = field.unique_values
            elif metric == "is_constant":
                return field.is_constant
            elif metric == "is_high_cardinality":
                return field.is_high_cardinality
            else:
                return False

            return self._compare_value(value, threshold, operator)

        elif pattern.pattern_type == PatternType.CUSTOM:
            # Custom pattern - check all provided criteria
            for key, expected in criteria.items():
                actual = getattr(field, key, None)
                if actual != expected:
                    return False
            return True

        return False

    def _compare_value(self, value: Any, threshold: Any, operator: str) -> bool:
        """Compare values using the specified operator."""
        if operator == "gt":
            return value > threshold
        elif operator == "lt":
            return value < threshold
        elif operator == "eq":
            return value == threshold
        elif operator == "gte":
            return value >= threshold
        elif operator == "lte":
            return value <= threshold
        return False

    async def preview_bulk_transformation(
        self,
        user_id: str,
        dataset_id: str,
        selected_columns: list[str],
        transformation_type: str,
        global_parameters: dict[str, Any],
        per_column_params: dict[str, dict[str, Any]] | None = None,
        preview_rows: int = 10
    ) -> dict[str, Any]:
        """
        Preview bulk transformation on multiple columns.

        Args:
            user_id: User identifier
            dataset_id: Dataset identifier
            selected_columns: List of columns to transform
            transformation_type: Type of transformation
            global_parameters: Global transformation parameters
            per_column_params: Per-column parameter overrides
            preview_rows: Number of rows to preview

        Returns:
            Preview results for each column

        Raises:
            NotFoundError: If dataset not found
            OperationError: If preview fails
        """
        dataset = await _owned_dataset(user_id, dataset_id)

        try:
            # a raw key must not reach the URL-only downloader (#466)
            df = await get_dataframe_from_s3(downloadable_url(dataset.file_path, dataset.s3_url))
            invalid_columns = [c for c in selected_columns if c not in df.columns]
            if invalid_columns:
                raise OperationError(
                    message=f"Invalid columns: {invalid_columns}",
                    operation="preview_bulk_transformation",
                    details={"invalid_columns": invalid_columns}
                )
            return _preview_summary([
                self._preview_column(
                    df, transformation_type,
                    _column_params(column, global_parameters, per_column_params or {}), preview_rows,
                )
                for column in selected_columns
            ])
        except Exception as e:
            logger.exception("Bulk preview failed")
            raise OperationError(
                message=internal_error_message("Bulk transformation preview"),
                operation="preview_bulk_transformation",
                original_error=e,
                details={"dataset_id": dataset_id}
            )

    def _preview_column(
        self, df: pd.DataFrame, transformation_type: str, params: dict[str, Any], preview_rows: int
    ) -> dict[str, Any]:
        """One column's preview; a column that raises is reported, and the rest still run."""
        column = params["column"]
        try:
            result = self.engine.preview_transformation(
                df=df,
                transformation_type=TransformationType(transformation_type),
                parameters=params,
                n_rows=preview_rows
            )
        except Exception:
            logger.exception(f"Preview failed for column {column}")
            return _failed_preview(column)
        return {
            "column_name": column,
            "success": result.success,
            "preview_data": result.preview_data,
            "stats_before": result.stats_before,
            "stats_after": result.stats_after,
            "affected_rows": result.affected_rows,
            "error": result.error,
            "warnings": result.warnings,
        }

    async def apply_bulk_transformation(
        self,
        user_id: str,
        dataset_id: str,
        selected_columns: list[str],
        transformation_type: str,
        global_parameters: dict[str, Any],
        per_column_params: dict[str, dict[str, Any]] | None = None,
        stop_on_error: bool = False
    ) -> BulkTransformationJob:
        """
        Create and start a bulk transformation job.

        Args:
            user_id: User identifier
            dataset_id: Dataset identifier
            selected_columns: List of columns to transform
            transformation_type: Type of transformation
            global_parameters: Global transformation parameters
            per_column_params: Per-column parameter overrides
            stop_on_error: Whether to stop on first error

        Returns:
            Created BulkTransformationJob

        Raises:
            NotFoundError: If dataset not found
            ValidationError: If validation fails
            OperationError: If rate limit exceeded
        """
        _require_valid_request(selected_columns, transformation_type)
        await _require_job_slot(user_id)
        # Resolved before the job exists, so an upload the reader cannot parse (#857) or
        # one the caller does not own is refused with nothing created.
        await _owned_dataset(user_id, dataset_id)

        job_id = f"bulk_{PydanticObjectId()}"
        job = BulkTransformationJob(
            job_id=job_id,
            user_id=user_id,
            dataset_id=dataset_id,
            selected_columns=selected_columns,
            transformation_type=transformation_type,
            global_parameters=global_parameters or {},
            per_column_params=per_column_params or {},
            stop_on_error=stop_on_error,
            status=BulkJobStatus.PENDING,
            progress=BulkTransformationProgress(
                total_columns=len(selected_columns),
                processed_columns=0,
                successful_columns=0,
                failed_columns=0,
            ),
        )

        await job.create()

        # Start processing asynchronously with proper task management
        task = asyncio.create_task(self._process_bulk_job(job))
        self._active_tasks[job_id] = task
        task.add_done_callback(lambda t: self._cleanup_task(job_id, t))

        return job

    async def _process_bulk_job(self, job: BulkTransformationJob) -> None:
        """
        Process a bulk transformation job asynchronously.

        This method runs in the background and updates job progress
        as columns are processed. It checks for cancellation periodically
        and batches database updates for efficiency.
        """
        start_time = time.time()

        try:
            job.mark_started()
            await job.save()

            # Either id space, like the routes that created the job (#856).
            dataset = await ensure_metadata_twin(job.dataset_id, job.user_id)
            if not dataset:
                job.mark_failed("Dataset not found")
                await job.save()
                return

            # a raw key must not reach the URL-only downloader (#466)
            df = await get_dataframe_from_s3(downloadable_url(dataset.file_path, dataset.s3_url))
            run = await self._run_columns(job, df)
            if run is not None:
                await self._finish_job(job, dataset, run, start_time)

        except Exception:
            logger.exception(f"Bulk transformation job {job.job_id} failed")
            # error_message is read back verbatim by the job-status route (#637).
            job.mark_failed(internal_error_message("Bulk transformation job"))
            await job.save()

    async def _run_columns(self, job: BulkTransformationJob, df: pd.DataFrame) -> _ColumnRun | None:
        """Transform the job's columns in order, each on the frame the one before left.

        None when the job ended early and there is nothing to finish: it was cancelled
        or deleted, or a column failed under `stop_on_error` (the job is then FAILED).
        """
        run = _ColumnRun(df)
        for i, column in enumerate(job.selected_columns):
            if not await self._still_wanted(job, column):
                return None
            new_df, result = await self._apply_column_transformation(
                df=run.df,
                column=column,
                transformation_type=job.transformation_type,
                global_parameters=job.global_parameters,
                per_column_params=job.per_column_params,
            )
            run.add(column, new_df, result)
            if not result.success and job.stop_on_error:
                job.mark_failed(f"Stopped at column {column}: {result.error}")
                await job.save()
                return None
            await self._record_progress(job, i, run)
        return run

    async def _still_wanted(self, job: BulkTransformationJob, column: str) -> bool:
        """Re-read the job before each column, so a cancel request is seen promptly."""
        current_job = await BulkTransformationJob.find_one({"job_id": job.job_id})
        if not current_job:
            logger.warning(f"Job {job.job_id} was deleted, stopping processing")
            return False
        if current_job.status == BulkJobStatus.CANCELLED:
            logger.info(f"Job {job.job_id} was cancelled, stopping processing")
            return False
        # Sync progress from database to avoid overwriting external updates
        # but keep our local progress tracking for the current batch
        job.progress = current_job.progress
        job.update_progress(current_column=column)
        return True

    async def _record_progress(self, job: BulkTransformationJob, index: int, run: _ColumnRun) -> None:
        job.update_progress(
            processed_columns=index + 1,
            successful_columns=len(run.succeeded),
            failed_columns=len(run.failed),
        )
        # Batch database updates: save every N columns or on the last column
        is_last_column = index == len(job.selected_columns) - 1
        if (index + 1) % PROGRESS_UPDATE_FREQUENCY == 0 or is_last_column:
            await job.save()

    async def _finish_job(
        self, job: BulkTransformationJob, dataset: DatasetMetadata, run: _ColumnRun, start_time: float
    ) -> None:
        """Write the result, move the dataset to it if any column worked, and close the job."""
        result = BulkTransformationResult(
            successful_columns=run.succeeded,
            failed_columns=run.failed,
            column_results=run.results,
            total_time_ms=int((time.time() - start_time) * 1000),
            total_rows_affected=sum(r.affected_rows for r in run.results if r.success),
        )
        if run.succeeded:
            job.output_file_path = await self._move_dataset(job, dataset, run.df)
        if run.failed:
            job.mark_partially_completed(result)
        else:
            job.mark_completed(result)
        await job.save()

    async def _move_dataset(self, job: BulkTransformationJob, dataset: DatasetMetadata, df: pd.DataFrame) -> str:
        """Upload the transformed frame and point the dataset at it; the new file's URL."""
        timestamp = datetime.now(UTC).timestamp()
        new_file_path = await upload_dataframe_to_s3(
            df, f"transformed/{job.user_id}/{job.dataset_id}_bulk_{timestamp}.parquet"
        )
        # Update dataset — and its dual-written twin (#467, #627). No transaction spans
        # the two documents: if this raises after one side moved, the job is marked
        # failed while the dataset is half-moved (logged at ERROR by the helper;
        # scripts/inventory_dataset_links.py finds it). Accepted, see dataset_link.py.
        dataset.num_rows = len(df)
        dataset.num_columns = len(df.columns)
        dataset.columns = df.columns.tolist()
        await record_new_file(dataset, new_file_path)
        await cache_service.delete_pattern(f"stats_{job.dataset_id}_*")
        return new_file_path

    async def _apply_column_transformation(
        self,
        df: pd.DataFrame,
        column: str,
        transformation_type: str,
        global_parameters: dict[str, Any],
        per_column_params: dict[str, dict[str, Any]],
    ) -> tuple[pd.DataFrame, ColumnResult]:
        """
        Apply transformation to a single column and return the modified DataFrame
        along with the result status.

        Returns:
            Tuple of (modified DataFrame, ColumnResult with success/failure info)
        """
        start_time = time.time()

        # Get column-specific parameters
        params = {**global_parameters}
        if column in per_column_params:
            params.update(per_column_params[column])
        params["column"] = column

        try:
            # First get preview stats
            preview_result = self.engine.preview_transformation(
                df=df,
                transformation_type=TransformationType(transformation_type),
                parameters=params,
                n_rows=10,
            )

            # Then apply the actual transformation (keep the DataFrame, no dict round-trip #542)
            new_df, apply_result = self.engine.apply_transformation_frame(
                df=df,
                transformation_type=TransformationType(transformation_type),
                parameters=params,
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            if apply_result.success and new_df is not None:
                return new_df, ColumnResult(
                    column_name=column,
                    success=True,
                    affected_rows=apply_result.affected_rows,
                    error=None,
                    warnings=apply_result.warnings,
                    execution_time_ms=execution_time_ms,
                    stats_before=preview_result.stats_before,
                    stats_after=preview_result.stats_after,
                )
            else:
                # Apply failed - return original df and failure result
                return df, ColumnResult(
                    column_name=column,
                    success=False,
                    affected_rows=0,
                    error=apply_result.error or "Transformation returned no data",
                    warnings=apply_result.warnings,
                    execution_time_ms=execution_time_ms,
                    stats_before=preview_result.stats_before if preview_result.success else None,
                    stats_after=None,
                )

        except Exception:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"Failed to apply transformation to column {column}")
            return df, ColumnResult(
                column_name=column,
                success=False,
                affected_rows=0,
                error=internal_error_message(f"Transformation of column {column!r}"),
                warnings=[],
                execution_time_ms=execution_time_ms,
            )

    async def get_job_status(
        self,
        job_id: str,
        user_id: str
    ) -> BulkTransformationJob | None:
        """
        Get the status of a bulk transformation job.

        Args:
            job_id: Job identifier
            user_id: User identifier

        Returns:
            BulkTransformationJob or None if not found
        """
        return await BulkTransformationJob.find_one({
            "job_id": job_id,
            "user_id": user_id
        })

    async def list_user_jobs(
        self,
        user_id: str,
        dataset_id: str | None = None,
        status: BulkJobStatus | None = None,
        limit: int = 50
    ) -> list[BulkTransformationJob]:
        """
        List user's bulk transformation jobs.

        Args:
            user_id: User identifier
            dataset_id: Optional dataset filter
            status: Optional status filter
            limit: Maximum number of jobs to return

        Returns:
            List of BulkTransformationJob
        """
        query: dict[str, Any] = {"user_id": user_id}

        if dataset_id:
            query["dataset_id"] = dataset_id
        if status:
            query["status"] = status

        return await BulkTransformationJob.find(
            query
        ).sort("-created_at").limit(limit).to_list()

    async def cancel_job(
        self,
        job_id: str,
        user_id: str
    ) -> bool:
        """
        Cancel a pending or running job.

        This method cancels both the database record and the actual running
        background task if one exists.

        Args:
            job_id: Job identifier
            user_id: User identifier

        Returns:
            True if cancelled, False if not found or already completed
        """
        job = await BulkTransformationJob.find_one({
            "job_id": job_id,
            "user_id": user_id,
            "status": {"$in": [BulkJobStatus.PENDING, BulkJobStatus.RUNNING]}
        })

        if not job:
            return False

        # Cancel the actual background task if it exists
        if job_id in self._active_tasks:
            task = self._active_tasks[job_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Background task for job {job_id} was cancelled")
            except Exception as e:
                logger.warning(f"Error while cancelling task for job {job_id}: {e}")
            finally:
                if job_id in self._active_tasks:
                    del self._active_tasks[job_id]

        job.mark_cancelled()
        await job.save()

        return True

    async def retry_job(
        self,
        job_id: str,
        user_id: str
    ) -> BulkTransformationJob | None:
        """
        Retry a failed job.

        Args:
            job_id: Job identifier
            user_id: User identifier

        Returns:
            Restarted job or None if cannot retry
        """
        job = await BulkTransformationJob.find_one({
            "job_id": job_id,
            "user_id": user_id
        })

        if not job or not job.can_retry():
            return None

        # Reset job state
        job.status = BulkJobStatus.PENDING
        job.started_at = None
        job.completed_at = None
        job.error_message = None
        job.result = None
        job.progress = BulkTransformationProgress(
            total_columns=len(job.selected_columns),
            processed_columns=0,
            successful_columns=0,
            failed_columns=0,
        )

        await job.save()

        # Start processing again with proper task management
        task = asyncio.create_task(self._process_bulk_job(job))
        self._active_tasks[job_id] = task
        task.add_done_callback(lambda t: self._cleanup_task(job_id, t))

        return job


# Singleton instance
bulk_transformation_service = BulkTransformationService()
