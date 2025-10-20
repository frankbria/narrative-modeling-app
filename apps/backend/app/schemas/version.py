"""
Pydantic schemas for Data Versioning API.

These schemas define the request and response models for dataset version
and lineage management endpoints.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.version import TransformationStep


class TransformationStepResponse(BaseModel):
    """Response model for transformation step."""

    step_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    affected_columns: List[str] = Field(default_factory=list)
    rows_affected: Optional[int] = None
    execution_time: Optional[float] = None


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
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    num_rows: int
    num_columns: int
    columns: List[str] = Field(default_factory=list)
    schema_hash: str
    parent_version_id: Optional[str] = None
    transformation_lineage_id: Optional[str] = None
    is_base_version: bool = False
    used_in_training: List[str] = Field(default_factory=list)
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    is_pinned: bool = False
    retention_days: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    created_by: str

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class DatasetVersionCreate(BaseModel):
    """Request model for creating a new dataset version."""

    description: Optional[str] = Field(None, description="Version description")
    tags: List[str] = Field(default_factory=list, description="Version tags")
    transformation_steps: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Transformation steps applied"
    )
    transformation_config_id: Optional[str] = Field(
        None,
        description="Reference to TransformationConfig"
    )


class LineageResponse(BaseModel):
    """Response model for transformation lineage."""

    lineage_id: str
    parent_version_id: str
    child_version_id: str
    dataset_id: str
    user_id: str
    transformation_steps: List[TransformationStepResponse]
    transformation_config_id: Optional[str] = None
    total_execution_time: Optional[float] = None
    rows_before: int
    rows_after: int
    columns_before: int
    columns_after: int
    data_loss_percentage: float = 0.0
    quality_before: Optional[Dict[str, Any]] = None
    quality_after: Optional[Dict[str, Any]] = None
    quality_improvement: Optional[float] = None
    is_reproducible: bool = True
    reproducibility_notes: Optional[str] = None
    is_validated: bool = False
    validation_status: Optional[str] = None
    validation_errors: List[str] = Field(default_factory=list)
    created_at: datetime
    completed_at: Optional[datetime] = None

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
    columns_added: List[str] = Field(default_factory=list)
    columns_removed: List[str] = Field(default_factory=list)
    columns_renamed: Dict[str, str] = Field(default_factory=dict)
    dtype_changes: Dict[str, tuple] = Field(default_factory=dict)
    content_similarity: float = 0.0
    schema_identical: bool = False
    lineage_path: List[str] = Field(default_factory=list)
    transformation_count: int = 0
    compared_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class VersionListResponse(BaseModel):
    """Response model for version list."""

    versions: List[DatasetVersionResponse]
    total: int
    limit: int
    skip: int
    dataset_id: str


class VersionPinRequest(BaseModel):
    """Request model for pinning/unpinning a version."""

    pinned: bool = Field(..., description="Whether to pin or unpin the version")
