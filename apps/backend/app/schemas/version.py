"""
Pydantic schemas for Data Versioning API.

These schemas define the request and response models for dataset version
and lineage management endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TransformationStepResponse(BaseModel):
    """Response model for transformation step."""

    model_config = ConfigDict(from_attributes=True)

    step_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    affected_columns: list[str] = Field(default_factory=list)
    rows_affected: int | None = None
    execution_time: float | None = None


class DatasetVersionResponse(BaseModel):
    """Response model for dataset version."""

    version_id: str
    dataset_id: str
    version_number: int
    user_id: str
    content_hash: str
    file_size: int
    file_path: str
    s3_url: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    num_rows: int
    num_columns: int
    columns: list[str] = Field(default_factory=list)
    schema_hash: str
    parent_version_id: str | None = None
    transformation_lineage_id: str | None = None
    is_base_version: bool = False
    used_in_training: list[str] = Field(default_factory=list)
    access_count: int = 0
    last_accessed_at: datetime | None = None
    is_pinned: bool = False
    retention_days: int | None = None
    expires_at: datetime | None = None
    created_at: datetime
    created_by: str

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class DatasetVersionCreate(BaseModel):
    """Request model for creating a new dataset version."""

    description: str | None = Field(None, description="Version description")
    tags: list[str] = Field(default_factory=list, description="Version tags")
    transformation_steps: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Transformation steps applied"
    )
    transformation_config_id: str | None = Field(
        None,
        description="Reference to TransformationConfig"
    )


class LineageResponse(BaseModel):
    """Response model for transformation lineage."""

    model_config = ConfigDict(from_attributes=True)

    lineage_id: str
    parent_version_id: str
    child_version_id: str
    dataset_id: str
    user_id: str
    transformation_steps: list[TransformationStepResponse]
    transformation_config_id: str | None = None
    total_execution_time: float | None = None
    rows_before: int
    rows_after: int
    columns_before: int
    columns_after: int
    data_loss_percentage: float = 0.0
    quality_before: dict[str, Any] | None = None
    quality_after: dict[str, Any] | None = None
    quality_improvement: float | None = None
    is_reproducible: bool = True
    reproducibility_notes: str | None = None
    is_validated: bool = False
    validation_status: str | None = None
    validation_errors: list[str] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class VersionComparisonRequest(BaseModel):
    """Request model for comparing two versions."""

    version1_id: str = Field(..., description="First version ID to compare")
    version2_id: str = Field(..., description="Second version ID to compare")


class VersionComparisonResponse(BaseModel):
    """Response model for version comparison."""

    version1_id: str
    version2_id: str
    rows_diff: int
    columns_diff: int
    columns_added: list[str] = Field(default_factory=list)
    columns_removed: list[str] = Field(default_factory=list)
    columns_renamed: dict[str, str] = Field(default_factory=dict)
    dtype_changes: dict[str, tuple] = Field(default_factory=dict)
    content_similarity: float = 0.0
    schema_identical: bool = False
    lineage_path: list[str] = Field(default_factory=list)
    transformation_count: int = 0
    compared_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class VersionListResponse(BaseModel):
    """Response model for version list."""

    versions: list[DatasetVersionResponse]
    total: int
    limit: int
    skip: int
    dataset_id: str


class VersionPinRequest(BaseModel):
    """Request model for pinning/unpinning a version."""

    pinned: bool = Field(..., description="Whether to pin or unpin the version")
