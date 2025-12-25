"""
Bulk transformation service for processing multiple columns in parallel.

This service handles bulk transformation operations that apply the same
transformation to multiple columns simultaneously with progress tracking.
"""

import asyncio
import re
import time
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import pandas as pd

from app.models.bulk_transformation import (
    BulkTransformationJob,
    BulkTransformationProgress,
    BulkTransformationResult,
    ColumnResult,
    BulkJobStatus,
    PatternType,
    ColumnSelectionPattern,
)
from app.models.dataset import DatasetMetadata, SchemaField
from app.services.transformation_engine.transformation_engine import (
    TransformationEngine,
    TransformationType,
)
from app.services.transformation_engine.data_utils import (
    get_dataframe_from_s3,
    upload_dataframe_to_s3,
)
from app.services.redis_cache import cache_service
from app.services.exceptions import NotFoundError, OperationError
from beanie import PydanticObjectId


logger = logging.getLogger(__name__)

# Maximum concurrent column transformations to avoid memory issues
MAX_CONCURRENT_COLUMNS = 10


class BulkTransformationService:
    """Service for bulk transformation operations on multiple columns."""

    def __init__(self):
        """Initialize service with transformation engine."""
        self.engine = TransformationEngine()

    async def select_columns_by_pattern(
        self,
        user_id: str,
        dataset_id: str,
        pattern: ColumnSelectionPattern
    ) -> List[Dict[str, Any]]:
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
            try:
                return bool(re.search(regex_pattern, field.field_name, re.IGNORECASE))
            except re.error:
                logger.warning(f"Invalid regex pattern: {regex_pattern}")
                return False

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
        selected_columns: List[str],
        transformation_type: str,
        global_parameters: Dict[str, Any],
        per_column_params: Optional[Dict[str, Dict[str, Any]]] = None,
        preview_rows: int = 10
    ) -> Dict[str, Any]:
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
        selected_columns: List[str],
        transformation_type: str,
        global_parameters: Dict[str, Any],
        per_column_params: Optional[Dict[str, Dict[str, Any]]] = None,
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
        """
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

        # Start processing asynchronously
        asyncio.create_task(self._process_bulk_job(job))

        return job

    async def _process_bulk_job(self, job: BulkTransformationJob) -> None:
        """
        Process a bulk transformation job asynchronously.

        This method runs in the background and updates job progress
        as columns are processed.
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
            column_results: List[ColumnResult] = []
            successful_columns: List[str] = []
            failed_columns: List[Dict[str, Any]] = []

            # Use semaphore to limit concurrent processing
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_COLUMNS)

            async def process_column(column: str) -> ColumnResult:
                """Process a single column with semaphore."""
                async with semaphore:
                    return await self._transform_column(
                        df=df,
                        column=column,
                        transformation_type=job.transformation_type,
                        global_parameters=job.global_parameters,
                        per_column_params=job.per_column_params,
                    )

            # Process columns (we'll process sequentially for DataFrame modifications)
            # but track progress along the way
            for i, column in enumerate(job.selected_columns):
                # Update current column
                job.update_progress(current_column=column)
                await job.save()

                # Process column
                result = await self._transform_column(
                    df=df,
                    column=column,
                    transformation_type=job.transformation_type,
                    global_parameters=job.global_parameters,
                    per_column_params=job.per_column_params,
                )

                column_results.append(result)

                if result.success:
                    successful_columns.append(column)
                    # Apply the transformation to the DataFrame
                    df = await self._apply_column_transformation(
                        df=df,
                        column=column,
                        transformation_type=job.transformation_type,
                        global_parameters=job.global_parameters,
                        per_column_params=job.per_column_params,
                    )
                else:
                    failed_columns.append({
                        "column_name": column,
                        "error": result.error,
                    })

                    if job.stop_on_error:
                        job.mark_failed(f"Stopped at column {column}: {result.error}")
                        await job.save()
                        return

                # Update progress
                job.update_progress(
                    processed_columns=i + 1,
                    successful_columns=len(successful_columns),
                    failed_columns=len(failed_columns),
                )
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
                timestamp = datetime.now(timezone.utc).timestamp()
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

    async def _transform_column(
        self,
        df: pd.DataFrame,
        column: str,
        transformation_type: str,
        global_parameters: Dict[str, Any],
        per_column_params: Dict[str, Dict[str, Any]],
    ) -> ColumnResult:
        """
        Transform a single column and return the result.

        This method previews the transformation to gather statistics
        without modifying the original DataFrame.
        """
        start_time = time.time()

        # Get column-specific parameters
        params = {**global_parameters}
        if column in per_column_params:
            params.update(per_column_params[column])
        params["column"] = column

        try:
            # Preview to get stats
            result = self.engine.preview_transformation(
                df=df,
                transformation_type=TransformationType(transformation_type),
                parameters=params,
                n_rows=10,
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return ColumnResult(
                column_name=column,
                success=result.success,
                affected_rows=result.affected_rows,
                error=result.error,
                warnings=result.warnings,
                execution_time_ms=execution_time_ms,
                stats_before=result.stats_before,
                stats_after=result.stats_after,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ColumnResult(
                column_name=column,
                success=False,
                affected_rows=0,
                error=str(e),
                warnings=[],
                execution_time_ms=execution_time_ms,
            )

    async def _apply_column_transformation(
        self,
        df: pd.DataFrame,
        column: str,
        transformation_type: str,
        global_parameters: Dict[str, Any],
        per_column_params: Dict[str, Dict[str, Any]],
    ) -> pd.DataFrame:
        """
        Apply transformation to a single column and return the modified DataFrame.
        """
        # Get column-specific parameters
        params = {**global_parameters}
        if column in per_column_params:
            params.update(per_column_params[column])
        params["column"] = column

        try:
            result = self.engine.apply_transformation(
                df=df,
                transformation_type=TransformationType(transformation_type),
                parameters=params,
            )

            if result.success and result.transformed_data:
                return pd.DataFrame(result.transformed_data)
            return df

        except Exception as e:
            logger.error(f"Failed to apply transformation to column {column}: {e}")
            return df

    async def get_job_status(
        self,
        job_id: str,
        user_id: str
    ) -> Optional[BulkTransformationJob]:
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
        dataset_id: Optional[str] = None,
        status: Optional[BulkJobStatus] = None,
        limit: int = 50
    ) -> List[BulkTransformationJob]:
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
        query: Dict[str, Any] = {"user_id": user_id}

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

        job.mark_cancelled()
        await job.save()

        return True

    async def retry_job(
        self,
        job_id: str,
        user_id: str
    ) -> Optional[BulkTransformationJob]:
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

        # Start processing again
        asyncio.create_task(self._process_bulk_job(job))

        return job


# Singleton instance
bulk_transformation_service = BulkTransformationService()
