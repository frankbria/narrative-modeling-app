"""
Batch prediction job model
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    BATCH_PREDICTION = "batch_prediction"
    MODEL_TRAINING = "model_training"
    DATA_PROCESSING = "data_processing"


class BatchPredictionConfig(BaseModel):
    """Configuration for batch prediction jobs"""

    model_id: str = Field(description="Model ID to use for predictions")
    input_format: str = Field(default="csv", description="Input data format")
    output_format: str = Field(default="csv", description="Output format")
    include_probabilities: bool = Field(
        default=True, description="Include prediction probabilities"
    )
    include_metadata: bool = Field(default=False, description="Include model metadata")
    include_explanations: bool = Field(
        default=False,
        description="Include per-prediction feature contributions (issue #83)",
    )
    chunk_size: int = Field(
        default=1000, description="Number of records to process per chunk"
    )
    # Optional async-completion webhook (issue #86). On terminal state the server
    # POSTs the job summary to ``webhook_url``, HMAC-SHA256-signed with
    # ``webhook_secret`` (header ``X-Signature``) when a secret is set.
    webhook_url: str | None = Field(
        default=None, description="URL to POST the job summary to on completion"
    )
    # Known limitation (#86): stored plaintext at rest — the server needs the raw
    # key to HMAC-sign the payload at fire time, so it can't be hashed. Masked in
    # API responses (_redact_config); encrypt-at-rest is the future hardening.
    webhook_secret: str | None = Field(
        default=None, description="Secret used to HMAC-sign the webhook payload"
    )


class JobProgress(BaseModel):
    """Job progress tracking"""

    total_records: int = Field(
        default=0, description="Total number of records to process"
    )
    processed_records: int = Field(default=0, description="Number of records processed")
    success_count: int = Field(
        default=0, description="Number of successful predictions"
    )
    error_count: int = Field(default=0, description="Number of prediction errors")
    current_chunk: int = Field(default=0, description="Current chunk being processed")
    total_chunks: int = Field(default=0, description="Total number of chunks")

    @property
    def percentage_complete(self) -> float:
        """Calculate percentage completion"""
        if self.total_records == 0:
            return 0.0
        return (self.processed_records / self.total_records) * 100

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.processed_records == 0:
            return 0.0
        return (self.success_count / self.processed_records) * 100


class BatchJob(Document):
    """Batch job document for async processing"""

    # Identification
    job_id: Annotated[str, Indexed()] = Field(description="Unique job identifier")
    job_type: JobType = Field(description="Type of batch job")

    # Ownership
    user_id: str = Field(description="User who created the job")

    # Job configuration
    config: dict[str, Any] = Field(description="Job-specific configuration")

    # Input/Output
    input_path: str | None = Field(None, description="S3 path to input data")
    output_path: str | None = Field(None, description="S3 path to output data")
    input_size_bytes: int | None = Field(
        None, description="Size of input data in bytes"
    )

    # Status and progress
    status: JobStatus = Field(default=JobStatus.PENDING)
    progress: JobProgress = Field(default_factory=JobProgress)

    # Error handling
    error_message: str | None = None
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Results
    results: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    tags: list[str] = Field(default_factory=list)
    priority: int = Field(
        default=0, description="Job priority (higher = more important)"
    )

    class Settings:
        name = "batch_jobs"
        indexes = ["job_id", "user_id", "status", "job_type", "created_at", "priority"]

    @property
    def duration_seconds(self) -> float | None:
        """Calculate job duration in seconds"""
        if not self.started_at:
            return None

        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    @property
    def estimated_completion(self) -> datetime | None:
        """Estimate completion time based on current progress"""
        if (
            self.status != JobStatus.RUNNING
            or not self.started_at
            or self.progress.processed_records == 0
        ):
            return None

        elapsed = datetime.utcnow() - self.started_at
        rate = self.progress.processed_records / elapsed.total_seconds()
        remaining = self.progress.total_records - self.progress.processed_records

        if rate > 0:
            estimated_remaining = remaining / rate
            return datetime.utcnow() + timedelta(seconds=estimated_remaining)

        return None

    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.status == JobStatus.FAILED and self.retry_count < self.max_retries

    def mark_started(self) -> None:
        """Mark job as started"""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()

    def mark_completed(self, results: dict[str, Any] | None = None) -> None:
        """Mark job as completed"""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if results:
            self.results.update(results)

    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed"""
        self.status = JobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        self.retry_count += 1

    def update_progress(
        self,
        processed_records: int | None = None,
        success_count: int | None = None,
        error_count: int | None = None,
        current_chunk: int | None = None,
    ) -> None:
        """Update job progress"""
        if processed_records is not None:
            self.progress.processed_records = processed_records
        if success_count is not None:
            self.progress.success_count = success_count
        if error_count is not None:
            self.progress.error_count = error_count
        if current_chunk is not None:
            self.progress.current_chunk = current_chunk
