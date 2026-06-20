"""
Bulk transformation service for processing multiple columns in parallel.

This service handles bulk transformation operations that apply the same
transformation to multiple columns simultaneously with progress tracking.
"""

import asyncio
import logging
import re
import time
from datetime import UTC, datetime
from threading import Thread
from typing import Any

import pandas as pd
from beanie import PydanticObjectId

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


class BulkTransformationService:
    """Service for bulk transformation operations on multiple columns."""

    def __init__(self):
        """Initialize service with transformation engine."""
        self.engine = TransformationEngine()
        # Track active background tasks for proper cleanup and cancellation
        self._active_tasks: dict[str, asyncio.Task] = {}

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

        per_column_params = per_column_params or {}

        try:
            # Load data from S3
            file_path = dataset.file_path or dataset.s3_url
            df = await get_dataframe_from_s3(file_path)

            # Validate selected columns exist
            invalid_columns = [c for c in selected_columns if c not in df.columns]
            if invalid_columns:
                raise OperationError(
                    message=f"Invalid columns: {invalid_columns}",
                    operation="preview_bulk_transformation",
                    details={"invalid_columns": invalid_columns}
                )

            # Preview each column
            column_previews = []
            total_estimated_rows = 0
            successful = 0
            failed = 0

            for column in selected_columns:
                # Get column-specific parameters
                params = {**global_parameters}
                if column in per_column_params:
                    params.update(per_column_params[column])

                # Add column to params if transformation expects it
                params["column"] = column

                try:
                    result = self.engine.preview_transformation(
                        df=df,
                        transformation_type=TransformationType(transformation_type),
                        parameters=params,
                        n_rows=preview_rows
                    )

                    column_previews.append({
                        "column_name": column,
                        "success": result.success,
                        "preview_data": result.preview_data,
                        "stats_before": result.stats_before,
                        "stats_after": result.stats_after,
                        "affected_rows": result.affected_rows,
                        "error": result.error,
                        "warnings": result.warnings,
                    })

                    if result.success:
                        successful += 1
                        total_estimated_rows += result.affected_rows
                    else:
                        failed += 1

                except Exception as e:
                    logger.error(f"Preview failed for column {column}: {e}")
                    column_previews.append({
                        "column_name": column,
                        "success": False,
                        "preview_data": None,
                        "stats_before": None,
                        "stats_after": None,
                        "affected_rows": 0,
                        "error": str(e),
                        "warnings": [],
                    })
                    failed += 1

            return {
                "success": failed == 0,
                "column_previews": column_previews,
                "total_estimated_rows_affected": total_estimated_rows,
                "total_columns": len(selected_columns),
                "successful_previews": successful,
                "failed_previews": failed,
                "error": None if failed == 0 else f"{failed} column(s) failed preview",
                "warnings": [],
            }

        except Exception as e:
            logger.error(f"Bulk preview failed: {e}")
            raise OperationError(
                message="Failed to preview bulk transformation",
                operation="preview_bulk_transformation",
                original_error=e,
                details={"dataset_id": dataset_id}
            )

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
        # Input validation
        if not selected_columns:
            raise ValidationError(
                message="selected_columns cannot be empty",
                field="selected_columns"
            )

        if len(selected_columns) > MAX_COLUMNS_PER_JOB:
            raise ValidationError(
                message=f"Cannot transform more than {MAX_COLUMNS_PER_JOB} columns at once",
                field="selected_columns"
            )

        # Check for duplicate columns
        if len(selected_columns) != len(set(selected_columns)):
            raise ValidationError(
                message="Duplicate column names in selected_columns",
                field="selected_columns"
            )

        # Validate transformation type
        try:
            TransformationType(transformation_type)
        except ValueError:
            raise ValidationError(
                message=f"Invalid transformation_type: {transformation_type}",
                field="transformation_type"
            )

        # Rate limiting - check user's active jobs
        active_jobs = await BulkTransformationJob.find({
            "user_id": user_id,
            "status": {"$in": [BulkJobStatus.PENDING, BulkJobStatus.RUNNING]}
        }).count()

        if active_jobs >= MAX_CONCURRENT_JOBS_PER_USER:
            raise OperationError(
                message=f"Maximum concurrent bulk transformation jobs ({MAX_CONCURRENT_JOBS_PER_USER}) reached. "
                        "Please wait for existing jobs to complete.",
                operation="apply_bulk_transformation",
                details={"active_jobs": active_jobs, "limit": MAX_CONCURRENT_JOBS_PER_USER}
            )

        # Verify dataset exists
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

        # Create job
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
            # Mark job as started
            job.mark_started()
            await job.save()

            # Load dataset
            dataset = await DatasetMetadata.find_one({
                "dataset_id": job.dataset_id,
                "user_id": job.user_id
            })

            if not dataset:
                job.mark_failed("Dataset not found")
                await job.save()
                return

            # Load data from S3
            file_path = dataset.file_path or dataset.s3_url
            df = await get_dataframe_from_s3(file_path)

            # Track results
            column_results: list[ColumnResult] = []
            successful_columns: list[str] = []
            failed_columns: list[dict[str, Any]] = []

            # Process columns sequentially for DataFrame modifications
            for i, column in enumerate(job.selected_columns):
                # Check for cancellation by reloading job status from DB
                # This ensures we detect cancellation requests promptly
                current_job = await BulkTransformationJob.find_one({"job_id": job.job_id})
                if not current_job:
                    logger.warning(f"Job {job.job_id} was deleted, stopping processing")
                    return
                if current_job.status == BulkJobStatus.CANCELLED:
                    logger.info(f"Job {job.job_id} was cancelled, stopping processing")
                    return

                # Sync progress from database to avoid overwriting external updates
                # but keep our local progress tracking for the current batch
                job.progress = current_job.progress
                job.update_progress(current_column=column)

                # Apply transformation and get result
                new_df, apply_result = await self._apply_column_transformation(
                    df=df,
                    column=column,
                    transformation_type=job.transformation_type,
                    global_parameters=job.global_parameters,
                    per_column_params=job.per_column_params,
                )

                column_results.append(apply_result)

                if apply_result.success:
                    successful_columns.append(column)
                    df = new_df
                else:
                    failed_columns.append({
                        "column_name": column,
                        "error": apply_result.error,
                    })

                    if job.stop_on_error:
                        job.mark_failed(f"Stopped at column {column}: {apply_result.error}")
                        await job.save()
                        return

                # Update progress in memory
                job.update_progress(
                    processed_columns=i + 1,
                    successful_columns=len(successful_columns),
                    failed_columns=len(failed_columns),
                )

                # Batch database updates: save every N columns or on the last column
                is_last_column = (i == len(job.selected_columns) - 1)
                should_save = (i + 1) % PROGRESS_UPDATE_FREQUENCY == 0 or is_last_column
                if should_save:
                    await job.save()

            # Calculate total time
            total_time_ms = int((time.time() - start_time) * 1000)
            total_rows_affected = sum(r.affected_rows for r in column_results if r.success)

            # Create result
            result = BulkTransformationResult(
                successful_columns=successful_columns,
                failed_columns=failed_columns,
                column_results=column_results,
                total_time_ms=total_time_ms,
                total_rows_affected=total_rows_affected,
            )

            # Save transformed data to S3 if any columns succeeded
            if successful_columns:
                timestamp = datetime.now(UTC).timestamp()
                new_file_path = await upload_dataframe_to_s3(
                    df,
                    f"transformed/{job.user_id}/{job.dataset_id}_bulk_{timestamp}.parquet"
                )

                # Update dataset
                dataset.file_path = new_file_path
                dataset.num_rows = len(df)
                dataset.num_columns = len(df.columns)
                dataset.columns = df.columns.tolist()
                dataset.update_timestamp()
                await dataset.save()

                # Clear cache
                await cache_service.delete_pattern(f"stats_{job.dataset_id}_*")

                job.output_file_path = new_file_path

            # Mark job status
            if failed_columns:
                job.mark_partially_completed(result)
            else:
                job.mark_completed(result)

            await job.save()

        except Exception as e:
            logger.exception(f"Bulk transformation job {job.job_id} failed: {e}")
            job.mark_failed(str(e))
            await job.save()

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

            # Then apply the actual transformation
            apply_result = self.engine.apply_transformation(
                df=df,
                transformation_type=TransformationType(transformation_type),
                parameters=params,
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            if apply_result.success and apply_result.transformed_data:
                new_df = pd.DataFrame(apply_result.transformed_data)
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

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Failed to apply transformation to column {column}: {e}")
            return df, ColumnResult(
                column_name=column,
                success=False,
                affected_rows=0,
                error=str(e),
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
