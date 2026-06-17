"""
Training job document for tracking AutoML training progress and results.

A ``TrainingJob`` is created when ``POST /api/v1/ml/train`` is called and is
updated as the background training task runs. It is the source of truth for the
``GET /api/v1/ml/{model_id}/status`` endpoint: status, per-algorithm progress,
the model comparison table, the selected best model, and any error.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field

from app.models.batch_job import JobStatus

LogLevel = Literal["info", "warning", "error"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Treat a naive datetime as UTC (MongoDB round-trips drop the tzinfo)."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class TrainingLogEntry(BaseModel):
    """One timestamped log line emitted during a training run."""

    timestamp: datetime = Field(default_factory=_utcnow)
    level: LogLevel
    message: str
    stage: Optional[str] = None


class TrainingProgress(BaseModel):
    """Per-algorithm progress for a training job."""

    completed_algorithms: int = Field(default=0)
    total_algorithms: int = Field(default=0)
    current_algorithm: Optional[str] = None
    current_stage: Optional[str] = None

    @property
    def fraction(self) -> float:
        """Completion as a 0.0-1.0 fraction (0.0 when total is unknown)."""
        if self.total_algorithms <= 0:
            return 0.0
        return max(0.0, min(self.completed_algorithms / self.total_algorithms, 1.0))

    @property
    def percentage(self) -> float:
        """Completion as a 0-100 percentage rounded to two decimals."""
        return round(self.fraction * 100, 2)


class ModelComparisonEntry(BaseModel):
    """One row of the model comparison table."""

    algorithm: str
    cv_score: Optional[float] = None
    test_score: Optional[float] = None
    training_time: Optional[float] = None


class TrainingJob(Document):
    """Tracks the lifecycle of an AutoML training run."""

    # Identification (model_id doubles as the resulting MLModel id on success)
    model_id: Indexed(str) = Field(description="Unique training/model identifier")
    user_id: Indexed(str)
    dataset_id: str
    target_column: str

    # Status and progress
    status: JobStatus = Field(default=JobStatus.PENDING)
    progress: TrainingProgress = Field(default_factory=TrainingProgress)

    # Results
    algorithm_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    model_comparison: List[ModelComparisonEntry] = Field(default_factory=list)
    best_model_id: Optional[str] = None
    best_algorithm: Optional[str] = None
    best_model_explanation: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)

    # Live monitoring (issue #76)
    logs: List[TrainingLogEntry] = Field(default_factory=list)
    cancellation_requested: bool = False

    # Error handling
    error: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Settings:
        name = "training_jobs"
        indexes = [
            "model_id",
            "user_id",
            "status",
            "created_at",
            # Serves the jobs-list query exactly: filter by owner (+ status),
            # newest first — the dashboard polls this every 10 seconds.
            [("user_id", 1), ("status", 1), ("created_at", -1)],
        ]

    # -- lifecycle helpers -------------------------------------------------

    def mark_started(self, total_algorithms: int = 0) -> None:
        """Transition the job to RUNNING and record the algorithm count."""
        self.status = JobStatus.RUNNING
        self.started_at = _utcnow()
        self.updated_at = self.started_at
        self.progress.total_algorithms = total_algorithms
        self.progress.completed_algorithms = 0

    def update_progress(
        self,
        completed_algorithms: Optional[int] = None,
        total_algorithms: Optional[int] = None,
        current_algorithm: Optional[str] = None,
    ) -> None:
        """Update progress counters; only provided fields are changed.

        Counters are floored at 0 so a stray negative value can never surface as
        negative progress in the status payload.
        """
        if total_algorithms is not None:
            self.progress.total_algorithms = max(0, total_algorithms)
        if completed_algorithms is not None:
            self.progress.completed_algorithms = max(0, completed_algorithms)
        if current_algorithm is not None:
            self.progress.current_algorithm = current_algorithm
        self.updated_at = _utcnow()

    def mark_completed(
        self,
        *,
        best_model_id: Optional[str] = None,
        best_algorithm: Optional[str] = None,
        best_model_explanation: Optional[str] = None,
        model_comparison: Optional[List[ModelComparisonEntry]] = None,
        algorithm_recommendations: Optional[List[Dict[str, Any]]] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Transition the job to COMPLETED and attach results."""
        self.status = JobStatus.COMPLETED
        self.completed_at = _utcnow()
        self.updated_at = self.completed_at
        self.progress.current_algorithm = None
        self.progress.completed_algorithms = self.progress.total_algorithms
        if best_model_id is not None:
            self.best_model_id = best_model_id
        if best_algorithm is not None:
            self.best_algorithm = best_algorithm
        if best_model_explanation is not None:
            self.best_model_explanation = best_model_explanation
        if model_comparison is not None:
            self.model_comparison = model_comparison
        if algorithm_recommendations is not None:
            self.algorithm_recommendations = algorithm_recommendations
        if metrics is not None:
            self.metrics = metrics

    def mark_failed(self, error: str) -> None:
        """Transition the job to FAILED and record the error message."""
        self.status = JobStatus.FAILED
        self.completed_at = _utcnow()
        self.updated_at = self.completed_at
        self.error = error

    def mark_cancelled(self) -> None:
        """Transition the job to CANCELLED and freeze its progress."""
        self.status = JobStatus.CANCELLED
        self.completed_at = _utcnow()
        self.updated_at = self.completed_at
        self.progress.current_algorithm = None
        # A terminal job is not in any pipeline stage; leaving "training" here
        # would mislead the status endpoint's stage badge.
        self.progress.current_stage = None

    def add_log(
        self, level: LogLevel, message: str, stage: Optional[str] = None
    ) -> TrainingLogEntry:
        """Append a timestamped log entry and bump ``updated_at``.

        Returns the entry so callers persisting with a partial update can
        ``$push`` exactly this entry instead of rewriting the whole array.
        """
        entry = TrainingLogEntry(level=level, message=message, stage=stage)
        self.logs.append(entry)
        self.updated_at = _utcnow()
        return entry

    # -- timing ------------------------------------------------------------

    @property
    def elapsed_seconds(self) -> Optional[float]:
        """Seconds since the job started (frozen at completion; None if unstarted)."""
        if self.started_at is None:
            return None
        end = _as_utc(self.completed_at) if self.completed_at else _utcnow()
        return (end - _as_utc(self.started_at)).total_seconds()

    @property
    def estimated_remaining_seconds(self) -> Optional[float]:
        """Naive linear time-remaining estimate for a running job.

        Extrapolates from elapsed time and the completed-algorithm fraction;
        ``None`` unless the job is RUNNING with progress strictly between 0 and 1.
        """
        if self.status != JobStatus.RUNNING:
            return None
        elapsed = self.elapsed_seconds
        fraction = self.progress.fraction
        if elapsed is None or not 0.0 < fraction < 1.0:
            return None
        return elapsed / fraction - elapsed
