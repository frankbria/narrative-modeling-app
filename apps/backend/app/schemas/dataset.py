"""
Pydantic schemas for Dataset API endpoints.

These schemas define request/response models for dataset operations,
using DatasetMetadata model and maintaining backward compatibility.
"""

from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime


# Request Schemas

class DatasetUploadResponse(BaseModel):
    """Response schema for dataset upload endpoint."""

    status: str = Field(..., description="Upload status")
    dataset_id: str = Field(..., description="Unique dataset identifier")
    filename: str = Field(..., description="Original filename")
    num_rows: int = Field(..., ge=0, description="Number of rows")
    num_columns: int = Field(..., ge=0, description="Number of columns")
    preview: List[Dict[str, Any]] = Field(default_factory=list, description="Preview rows")
    headers: List[str] = Field(default_factory=list, description="Column headers")
    data_schema_fields: List[Dict[str, Any]] = Field(default_factory=list, description="Data schema", alias="schema")
    s3_url: str = Field(..., description="S3 URL for file access")

    model_config = {
        "populate_by_name": True
    }

    # PII report (for backward compatibility)
    pii_report: Optional[Dict[str, Any]] = None

    # Legacy fields (for backward compatibility)
    file_id: Optional[str] = None
    previewData: Optional[List[List[Any]]] = None
    fileName: Optional[str] = None
    fileType: Optional[str] = None
    id: Optional[str] = None


class DatasetListItem(BaseModel):
    """Schema for dataset list item."""

    dataset_id: str = Field(..., description="Unique dataset identifier")
    filename: str = Field(..., description="Storage filename")
    original_filename: str = Field(..., description="Original filename from upload")
    file_type: str = Field(..., description="File type")
    num_rows: int = Field(..., ge=0, description="Number of rows")
    num_columns: int = Field(..., ge=0, description="Number of columns")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    is_processed: bool = Field(..., description="Whether dataset is processed")
    contains_pii: bool = Field(default=False, description="Whether dataset contains PII")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class DatasetListResponse(BaseModel):
    """Response schema for list datasets endpoint."""

    datasets: List[DatasetListItem] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="Total number of datasets")


class DatasetDetailResponse(BaseModel):
    """Response schema for dataset detail endpoint."""

    dataset_id: str = Field(..., description="Unique dataset identifier")
    user_id: str = Field(..., description="User who owns the dataset")
    filename: str = Field(..., description="Storage filename")
    original_filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type")
    file_path: str = Field(..., description="Storage path")
    s3_url: str = Field(..., description="S3 URL")
    file_size: Optional[int] = None

    # Dataset dimensions
    num_rows: int = Field(..., ge=0)
    num_columns: int = Field(..., ge=0)
    columns: List[str] = Field(default_factory=list)

    # Schema and statistics
    data_schema: List[Dict[str, Any]] = Field(default_factory=list)
    inferred_schema: Optional[Dict[str, Any]] = None
    statistics: Optional[Dict[str, Any]] = None
    quality_report: Optional[Dict[str, Any]] = None
    data_preview: Optional[List[Dict[str, Any]]] = None

    # AI analysis
    ai_summary: Optional[Dict[str, Any]] = None

    # PII report
    pii_report: Optional[Dict[str, Any]] = None

    # Processing status
    is_processed: bool = Field(..., description="Whether initial processing is complete")
    processed_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Version
    version: str = Field(..., description="Dataset version")


class DatasetUpdateRequest(BaseModel):
    """Request schema for dataset update endpoint."""

    statistics: Optional[Dict[str, Any]] = None
    quality_report: Optional[Dict[str, Any]] = None
    inferred_schema: Optional[Dict[str, Any]] = None
    ai_summary: Optional[Dict[str, Any]] = None
    pii_report: Optional[Dict[str, Any]] = None


class DatasetDeleteResponse(BaseModel):
    """Response schema for dataset delete endpoint."""

    status: str = Field(..., description="Delete status")
    dataset_id: str = Field(..., description="Deleted dataset ID")
    message: str = Field(..., description="Success message")


class DatasetProcessingRequest(BaseModel):
    """Request schema for marking dataset as processed."""

    statistics: Optional[Dict[str, Any]] = None
    quality_report: Optional[Dict[str, Any]] = None
    inferred_schema: Optional[Dict[str, Any]] = None


class DatasetProcessingResponse(BaseModel):
    """Response schema for dataset processing operation."""

    dataset_id: str = Field(..., description="Dataset ID")
    is_processed: bool = Field(..., description="Processing status")
    processed_at: datetime = Field(..., description="Processing timestamp")
