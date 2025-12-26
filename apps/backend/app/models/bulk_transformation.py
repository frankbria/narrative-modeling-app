"""
Bulk transformation job models for MongoDB.

This model handles bulk operations that apply the same transformation
to multiple columns simultaneously with parallel processing.
"""

import re
from beanie import Document, Indexed
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from beanie import PydanticObjectId
from enum import Enum


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(timezone.utc)


class PatternType(str, Enum):
    """Types of column selection patterns."""
    DATA_TYPE = "data_type"
    NAME_PATTERN = "name_pattern"
    QUALITY_METRIC = "quality_metric"
    CUSTOM = "custom"


class BulkJobStatus(str, Enum):
    """Status of a bulk transformation job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_COMPLETED = "partially_completed"


class ColumnSelectionPattern(BaseModel):
    """Pattern for selecting columns programmatically."""

    pattern_type: PatternType = Field(..., description="Type of selection pattern")
    criteria: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pattern-specific criteria"
    )

    @field_validator('criteria')
    @classmethod
    def validate_criteria(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        """Validate criteria based on pattern type."""
        # Get pattern_type from the data being validated
        pattern_type = info.data.get('pattern_type')

        if pattern_type == PatternType.DATA_TYPE:
            if 'types' not in v:
                raise ValueError("data_type pattern requires 'types' in criteria")
            valid_types = {'numeric', 'text', 'boolean', 'datetime', 'categorical'}
            for t in v['types']:
                if t not in valid_types:
                    raise ValueError(f"Invalid type: {t}. Must be one of {valid_types}")

        elif pattern_type == PatternType.NAME_PATTERN:
            if 'pattern' not in v:
                raise ValueError("name_pattern requires 'pattern' in criteria")
            # Validate that the regex pattern compiles
            try:
                re.compile(v['pattern'])
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")

        elif pattern_type == PatternType.QUALITY_METRIC:
            valid_metrics = {'missing_values', 'is_constant', 'is_high_cardinality', 'unique_values'}
            if 'metric' not in v:
                raise ValueError("quality_metric pattern requires 'metric' in criteria")
            if v['metric'] not in valid_metrics:
                raise ValueError(f"Invalid metric: {v['metric']}. Must be one of {valid_metrics}")

        return v


class ColumnResult(BaseModel):
    """Result for a single column transformation."""

    column_name: str = Field(..., description="Name of the column")
    success: bool = Field(default=True, description="Whether transformation succeeded")
    affected_rows: int = Field(default=0, ge=0, description="Number of rows affected")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    execution_time_ms: int = Field(default=0, ge=0, description="Execution time in milliseconds")
    stats_before: Optional[Dict[str, Any]] = Field(default=None, description="Stats before transformation")
    stats_after: Optional[Dict[str, Any]] = Field(default=None, description="Stats after transformation")


class BulkTransformationProgress(BaseModel):
    """Progress tracking for bulk transformation job."""

    total_columns: int = Field(default=0, ge=0, description="Total number of columns to transform")
    processed_columns: int = Field(default=0, ge=0, description="Number of columns processed")
    successful_columns: int = Field(default=0, ge=0, description="Number of successful transformations")
    failed_columns: int = Field(default=0, ge=0, description="Number of failed transformations")
    current_column: Optional[str] = Field(default=None, description="Currently processing column")

    @property
    def percentage_complete(self) -> float:
        """Calculate percentage completion."""
        if self.total_columns == 0:
            return 0.0
        return (self.processed_columns / self.total_columns) * 100

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.processed_columns == 0:
            return 0.0
        return (self.successful_columns / self.processed_columns) * 100


class BulkTransformationResult(BaseModel):
    """Result of a bulk transformation job."""

    successful_columns: List[str] = Field(
        default_factory=list,
        description="List of successfully transformed columns"
    )
    failed_columns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of failed columns with error details"
    )
    column_results: List[ColumnResult] = Field(
        default_factory=list,
        description="Detailed results per column"
    )
    total_time_ms: int = Field(default=0, ge=0, description="Total execution time in milliseconds")
    total_rows_affected: int = Field(default=0, ge=0, description="Total rows affected across all columns")


class BulkTransformationJob(Document):
    """
    Bulk transformation job document.

    Tracks the state and progress of a bulk transformation operation
    that applies the same transformation to multiple columns.
    """

    # Identification
    job_id: Indexed(str) = Field(..., description="Unique job identifier")
    user_id: Indexed(str) = Field(..., description="User who owns this job")
    dataset_id: Indexed(str) = Field(..., description="Target dataset")

    # Configuration
    selected_columns: List[str] = Field(
        default_factory=list,
        description="List of columns to transform",
        min_length=1,
        max_length=100
    )
    transformation_type: str = Field(..., description="Type of transformation to apply")

    global_parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Global transformation parameters"
    )
    per_column_params: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-column parameter overrides (column_name -> params)"
    )

    # Error handling
    stop_on_error: bool = Field(
        default=False,
        description="Whether to stop on first error"
    )

    @field_validator('selected_columns')
    @classmethod
    def validate_column_names(cls, v: List[str]) -> List[str]:
        """Validate selected column names."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate column names in selected_columns")
        for col in v:
            if not col or not col.strip():
                raise ValueError("Column names cannot be empty")
        return v

    # Status and progress
    status: BulkJobStatus = Field(default=BulkJobStatus.PENDING)
    progress: BulkTransformationProgress = Field(
        default_factory=BulkTransformationProgress
    )

    # Results
    result: Optional[BulkTransformationResult] = Field(
        default=None,
        description="Results after job completion"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if job failed"
    )

    # File paths
    output_file_path: Optional[str] = Field(
        default=None,
        description="Path to transformed dataset"
    )

    # Retry handling
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    updated_at: datetime = Field(default_factory=get_current_time)

    class Settings:
        name = "bulk_transformation_jobs"
        indexes = [
            "job_id",
            "user_id",
            "dataset_id",
            "status",
            "created_at",
            [("user_id", 1), ("status", 1)],
            [("user_id", 1), ("created_at", -1)],
            [("dataset_id", 1), ("status", 1)],
            [("user_id", 1), ("dataset_id", 1), ("status", 1)],  # For filtered job listing
        ]

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = get_current_time()

    def mark_started(self) -> None:
        """Mark job as started."""
        self.status = BulkJobStatus.RUNNING
        self.started_at = get_current_time()
        self.update_timestamp()

    def mark_completed(self, result: BulkTransformationResult) -> None:
        """Mark job as completed."""
        self.status = BulkJobStatus.COMPLETED
        self.completed_at = get_current_time()
        self.result = result
        self.update_timestamp()

    def mark_partially_completed(self, result: BulkTransformationResult) -> None:
        """Mark job as partially completed (some columns failed)."""
        self.status = BulkJobStatus.PARTIALLY_COMPLETED
        self.completed_at = get_current_time()
        self.result = result
        self.update_timestamp()

    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed."""
        self.status = BulkJobStatus.FAILED
        self.completed_at = get_current_time()
        self.error_message = error_message
        self.retry_count += 1
        self.update_timestamp()

    def mark_cancelled(self) -> None:
        """Mark job as cancelled."""
        self.status = BulkJobStatus.CANCELLED
        self.completed_at = get_current_time()
        self.update_timestamp()

    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.status == BulkJobStatus.FAILED and self.retry_count < self.max_retries

    def update_progress(
        self,
        processed_columns: Optional[int] = None,
        successful_columns: Optional[int] = None,
        failed_columns: Optional[int] = None,
        current_column: Optional[str] = None
    ) -> None:
        """Update job progress."""
        if processed_columns is not None:
            self.progress.processed_columns = processed_columns
        if successful_columns is not None:
            self.progress.successful_columns = successful_columns
        if failed_columns is not None:
            self.progress.failed_columns = failed_columns
        if current_column is not None:
            self.progress.current_column = current_column
        self.update_timestamp()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if not self.started_at:
            return None
        end_time = self.completed_at or get_current_time()
        return (end_time - self.started_at).total_seconds()

    @property
    def estimated_remaining_seconds(self) -> Optional[float]:
        """Estimate remaining time based on progress."""
        if (self.status != BulkJobStatus.RUNNING or
            not self.started_at or
            self.progress.processed_columns == 0):
            return None

        elapsed = (get_current_time() - self.started_at).total_seconds()
        rate = self.progress.processed_columns / elapsed
        remaining = self.progress.total_columns - self.progress.processed_columns

        if rate > 0:
            return remaining / rate
        return None
