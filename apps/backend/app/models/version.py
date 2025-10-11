"""
Data versioning and lineage tracking models.

This module provides models for tracking dataset versions and transformation lineage,
enabling reproducibility and historical analysis of data transformations and model training.
"""

from beanie import Document, Indexed
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from beanie import PydanticObjectId
import hashlib


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(timezone.utc)


class TransformationStep(BaseModel):
    """Details of a single transformation step applied to data."""

    step_type: str = Field(..., description="Type of transformation: drop_missing, encode, scale, etc.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Transformation parameters")
    affected_columns: List[str] = Field(default_factory=list, description="Columns affected by this transformation")
    rows_affected: Optional[int] = Field(None, description="Number of rows affected (e.g., dropped)")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")

    @field_validator('step_type')
    @classmethod
    def validate_step_type(cls, v: str) -> str:
        """Validate step_type is one of known transformation types."""
        allowed_types = {
            'drop_missing', 'impute', 'encode', 'scale', 'normalize',
            'feature_engineering', 'outlier_removal', 'custom'
        }
        if v not in allowed_types:
            raise ValueError(f"step_type must be one of {allowed_types}, got: {v}")
        return v


class DatasetVersion(Document):
    """
    Dataset version tracking document.

    Each version represents a snapshot of a dataset at a particular point in time,
    including its content hash, metadata, and lineage information.

    Versions are created:
    - On initial upload (version 1)
    - After each transformation (incremental version)
    - When explicitly saved by user
    """

    # Version identification
    version_id: Indexed(str) = Field(..., description="Unique version identifier (UUID)")
    dataset_id: Indexed(str) = Field(..., description="Parent dataset identifier")
    version_number: int = Field(..., ge=1, description="Sequential version number")

    # Ownership
    user_id: Indexed(str) = Field(..., description="User who owns this version")

    # Content identification
    content_hash: str = Field(..., description="SHA-256 hash of file content for deduplication")
    file_size: int = Field(..., ge=0, description="File size in bytes")

    # Storage location
    file_path: str = Field(..., description="Storage path (e.g., S3 key)")
    s3_url: str = Field(..., description="S3 URL for version access")

    # Version metadata
    description: Optional[str] = Field(None, description="User-provided version description")
    tags: List[str] = Field(default_factory=list, description="User-defined tags for version")

    # Dataset characteristics at this version
    num_rows: int = Field(..., ge=0, description="Number of rows")
    num_columns: int = Field(..., ge=0, description="Number of columns")
    columns: List[str] = Field(default_factory=list, description="Column names")
    schema_hash: str = Field(..., description="Hash of schema for change detection")

    # Lineage tracking
    parent_version_id: Optional[str] = Field(None, description="Parent version if derived")
    transformation_lineage_id: Optional[str] = Field(None, description="Link to transformation lineage")
    is_base_version: bool = Field(default=False, description="Whether this is the original uploaded version")

    # Usage tracking
    used_in_training: List[str] = Field(default_factory=list, description="List of model training job IDs")
    access_count: int = Field(default=0, ge=0, description="Number of times accessed")
    last_accessed_at: Optional[datetime] = None

    # Lifecycle management
    is_pinned: bool = Field(default=False, description="Whether version is pinned (not auto-deleted)")
    retention_days: Optional[int] = Field(None, ge=1, description="Days to retain (None = indefinite)")
    expires_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time)
    created_by: str = Field(..., description="User who created this version")

    class Settings:
        name = "dataset_versions"
        indexes = [
            "version_id",
            "dataset_id",
            "user_id",
            "content_hash",
            "created_at",
            [("dataset_id", 1), ("version_number", -1)],
            [("user_id", 1), ("created_at", -1)],
            [("dataset_id", 1), ("is_base_version", 1)]
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    @staticmethod
    def compute_content_hash(content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def compute_schema_hash(columns: List[str], dtypes: Dict[str, str]) -> str:
        """Compute hash of schema for change detection."""
        schema_str = ",".join([f"{col}:{dtypes.get(col, 'unknown')}" for col in sorted(columns)])
        return hashlib.sha256(schema_str.encode()).hexdigest()

    def mark_accessed(self) -> None:
        """Mark version as accessed and update counters."""
        self.access_count += 1
        self.last_accessed_at = get_current_time()

    def link_to_training(self, training_job_id: str) -> None:
        """Link this version to a training job."""
        if training_job_id not in self.used_in_training:
            self.used_in_training.append(training_job_id)

    def pin_version(self) -> None:
        """Pin this version to prevent auto-deletion."""
        self.is_pinned = True
        self.expires_at = None

    def unpin_version(self) -> None:
        """Unpin this version, allowing auto-deletion based on retention policy."""
        self.is_pinned = False


class TransformationLineage(Document):
    """
    Transformation lineage tracking document.

    Records the complete history of transformations applied between dataset versions,
    enabling reproducibility and transformation analysis.
    """

    # Lineage identification
    lineage_id: Indexed(str) = Field(..., description="Unique lineage identifier (UUID)")

    # Version relationships
    parent_version_id: Indexed(str) = Field(..., description="Source dataset version")
    child_version_id: Indexed(str) = Field(..., description="Result dataset version")
    dataset_id: Indexed(str) = Field(..., description="Dataset identifier")

    # Ownership
    user_id: Indexed(str) = Field(..., description="User who performed transformation")

    # Transformation details
    transformation_steps: List[TransformationStep] = Field(
        default_factory=list,
        description="Ordered list of transformation steps"
    )
    transformation_config_id: Optional[str] = Field(
        None,
        description="Reference to full TransformationConfig if stored separately"
    )

    # Impact metrics
    total_execution_time: Optional[float] = Field(None, description="Total execution time in seconds")
    rows_before: int = Field(..., ge=0, description="Row count before transformation")
    rows_after: int = Field(..., ge=0, description="Row count after transformation")
    columns_before: int = Field(..., ge=0, description="Column count before transformation")
    columns_after: int = Field(..., ge=0, description="Column count after transformation")
    data_loss_percentage: float = Field(default=0.0, ge=0, le=100, description="Percentage of data lost")

    # Quality tracking
    quality_before: Optional[Dict[str, Any]] = Field(None, description="Quality metrics before transformation")
    quality_after: Optional[Dict[str, Any]] = Field(None, description="Quality metrics after transformation")
    quality_improvement: Optional[float] = Field(None, description="Quality improvement score")

    # Reproducibility
    is_reproducible: bool = Field(default=True, description="Whether transformation can be reproduced")
    reproducibility_notes: Optional[str] = Field(None, description="Notes on reproducibility challenges")

    # Validation
    is_validated: bool = Field(default=False, description="Whether transformation has been validated")
    validation_status: Optional[str] = Field(None, description="Validation status: passed, failed, pending")
    validation_errors: List[str] = Field(default_factory=list, description="Validation error messages")

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time)
    completed_at: Optional[datetime] = None

    class Settings:
        name = "transformation_lineages"
        indexes = [
            "lineage_id",
            "parent_version_id",
            "child_version_id",
            "dataset_id",
            "user_id",
            "created_at",
            [("dataset_id", 1), ("created_at", -1)],
            [("parent_version_id", 1), ("child_version_id", 1)]
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    @field_validator('validation_status')
    @classmethod
    def validate_validation_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate validation_status is one of allowed values."""
        if v is None:
            return v
        allowed_statuses = {'passed', 'failed', 'pending'}
        if v not in allowed_statuses:
            raise ValueError(f"validation_status must be one of {allowed_statuses}, got: {v}")
        return v

    def calculate_data_loss(self) -> float:
        """Calculate data loss percentage."""
        if self.rows_before == 0:
            return 0.0
        rows_lost = self.rows_before - self.rows_after
        return (rows_lost / self.rows_before) * 100

    def mark_completed(self) -> None:
        """Mark lineage as completed."""
        self.completed_at = get_current_time()
        self.data_loss_percentage = self.calculate_data_loss()

    def add_validation_error(self, error: str) -> None:
        """Add a validation error."""
        self.validation_errors.append(error)
        self.validation_status = "failed"
        self.is_validated = True

    def mark_validated(self, passed: bool = True) -> None:
        """Mark lineage as validated."""
        self.is_validated = True
        self.validation_status = "passed" if passed else "failed"

    def get_transformation_summary(self) -> Dict[str, Any]:
        """Get summary of transformations applied."""
        return {
            "total_steps": len(self.transformation_steps),
            "step_types": [step.step_type for step in self.transformation_steps],
            "affected_columns": list(set(
                col for step in self.transformation_steps for col in step.affected_columns
            )),
            "data_loss_percentage": self.data_loss_percentage,
            "execution_time": self.total_execution_time,
            "is_reproducible": self.is_reproducible
        }


class VersionComparison(BaseModel):
    """
    Result of comparing two dataset versions.

    Provides detailed comparison metrics for understanding differences
    between versions.
    """

    version1_id: str
    version2_id: str

    # Dimensional changes
    rows_diff: int = Field(..., description="Difference in row count")
    columns_diff: int = Field(..., description="Difference in column count")

    # Schema changes
    columns_added: List[str] = Field(default_factory=list)
    columns_removed: List[str] = Field(default_factory=list)
    columns_renamed: Dict[str, str] = Field(default_factory=dict)
    dtype_changes: Dict[str, tuple] = Field(default_factory=dict)

    # Content changes
    content_similarity: float = Field(default=0.0, ge=0, le=100, description="Content similarity percentage")
    schema_identical: bool = Field(default=False)

    # Lineage path
    lineage_path: List[str] = Field(
        default_factory=list,
        description="List of lineage IDs connecting versions"
    )
    transformation_count: int = Field(default=0, ge=0)

    # Timestamps
    compared_at: datetime = Field(default_factory=get_current_time)
