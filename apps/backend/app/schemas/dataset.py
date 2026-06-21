"""
Pydantic schemas for Dataset API endpoints.

These schemas define request/response models for dataset operations,
using DatasetMetadata model and maintaining backward compatibility.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Request Schemas

class DatasetUploadResponse(BaseModel):
    """Response schema for dataset upload endpoint."""

    status: str = Field(..., description="Upload status")
    dataset_id: str = Field(..., description="Unique dataset identifier")
    filename: str = Field(..., description="Original filename")
    num_rows: int = Field(..., ge=0, description="Number of rows")
    num_columns: int = Field(..., ge=0, description="Number of columns")
    preview: list[dict[str, Any]] = Field(default_factory=list, description="Preview rows")
    headers: list[str] = Field(default_factory=list, description="Column headers")
    data_schema_fields: list[dict[str, Any]] = Field(default_factory=list, description="Data schema", alias="schema")
    s3_url: str = Field(..., description="S3 URL for file access")
    file_size: int | None = Field(None, description="File size in bytes")
    file_type: str | None = Field(None, description="File type")

    model_config = {
        "populate_by_name": True
    }

    # PII report (for backward compatibility)
    pii_report: dict[str, Any] | None = None

    # Legacy fields (for backward compatibility)
    file_id: str | None = None
    previewData: list[list[Any]] | None = None
    fileName: str | None = None
    fileType: str | None = None
    id: str | None = None


class DatasetListItem(BaseModel):
    """Schema for dataset list item."""

    dataset_id: str = Field(..., description="Unique dataset identifier")
    filename: str = Field(..., description="Storage filename")
    original_filename: str = Field(..., description="Original filename from upload")
    file_type: str = Field(..., description="File type")
    num_rows: int = Field(..., ge=0, description="Number of rows")
    num_columns: int = Field(..., ge=0, description="Number of columns")
    file_size: int | None = Field(None, description="File size in bytes")
    is_processed: bool = Field(..., description="Whether dataset is processed")
    contains_pii: bool = Field(default=False, description="Whether dataset contains PII")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class DatasetListResponse(BaseModel):
    """Response schema for list datasets endpoint."""

    datasets: list[DatasetListItem] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="Total number of datasets")


class DatasetDetailResponse(BaseModel):
    """Response schema for dataset detail endpoint."""

    dataset_id: str = Field(..., description="Unique dataset identifier")
    filename: str = Field(..., description="Storage filename")
    original_filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type")
    file_path: str = Field(..., description="Storage path")
    s3_url: str = Field(..., description="S3 URL")
    file_size: int | None = None

    # Dataset dimensions
    num_rows: int = Field(..., ge=0)
    num_columns: int = Field(..., ge=0)
    columns: list[str] = Field(default_factory=list)

    # Schema and statistics
    data_schema: list[dict[str, Any]] = Field(default_factory=list)
    inferred_schema: dict[str, Any] | None = None
    statistics: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    data_preview: list[dict[str, Any]] | None = None

    # AI analysis
    ai_summary: dict[str, Any] | None = None

    # PII report
    pii_report: dict[str, Any] | None = None

    # Processing status
    is_processed: bool = Field(..., description="Whether initial processing is complete")
    processed_at: datetime | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Version
    version: str = Field(..., description="Dataset version")


class DatasetUpdateRequest(BaseModel):
    """Request schema for dataset update endpoint."""

    statistics: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    inferred_schema: dict[str, Any] | None = None
    ai_summary: dict[str, Any] | None = None
    pii_report: dict[str, Any] | None = None


class DatasetDeleteResponse(BaseModel):
    """Response schema for dataset delete endpoint."""

    status: str = Field(..., description="Delete status")
    dataset_id: str = Field(..., description="Deleted dataset ID")
    message: str = Field(..., description="Success message")


class DatasetProcessingRequest(BaseModel):
    """Request schema for marking dataset as processed."""

    statistics: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    inferred_schema: dict[str, Any] | None = None


class DatasetProcessingResponse(BaseModel):
    """Response schema for dataset processing operation."""

    dataset_id: str = Field(..., description="Dataset ID")
    is_processed: bool = Field(..., description="Processing status")
    processed_at: datetime = Field(..., description="Processing timestamp")
    statistics: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None


class DatasetSchemaResponse(BaseModel):
    """Response schema for dataset schema endpoint."""

    dataset_id: str = Field(..., description="Dataset ID")
    # `schema` shadows Pydantic's deprecated `BaseModel.schema()`; it is part of
    # the public response contract and cannot be renamed.
    schema: list[dict[str, Any]] = Field(  # type: ignore[assignment]
        ..., description="Field-level schema"
    )
    num_fields: int = Field(..., ge=0, description="Number of fields in schema")


class DatasetPreviewResponse(BaseModel):
    """Response schema for dataset preview endpoint."""

    dataset_id: str = Field(..., description="Dataset ID")
    preview: list[dict[str, Any]] = Field(..., description="Preview rows")
    total_rows: int = Field(..., ge=0, description="Total number of rows in dataset")
    preview_rows: int = Field(..., ge=0, description="Number of preview rows returned")
