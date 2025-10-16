"""
Dataset metadata model for MongoDB.

This model focuses on dataset-related information including file metadata,
schema, statistics, and quality assessments. It replaces the dataset-specific
fields from the legacy UserData model.
"""

from beanie import Document, Indexed
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from beanie import PydanticObjectId


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(timezone.utc)


class SchemaField(BaseModel):
    """Schema information for a single column/field."""

    field_name: str = Field(..., description="Name of the field/column")
    field_type: str = Field(..., description="Field type: numeric, text, boolean, datetime, categorical")
    data_type: Optional[str] = Field(None, description="Statistical data type: nominal, ordinal, interval, ratio")
    inferred_dtype: str = Field(..., description="Inferred data type from pandas (e.g., int64, float64, object)")
    unique_values: int = Field(..., ge=0, description="Number of unique values")
    missing_values: int = Field(..., ge=0, description="Number of missing values")
    example_values: List[Any] = Field(default_factory=list, description="Sample values from the field")
    is_constant: bool = Field(default=False, description="Whether all values are the same")
    is_high_cardinality: bool = Field(default=False, description="Whether field has high cardinality")

    @field_validator('field_type')
    @classmethod
    def validate_field_type(cls, v: str) -> str:
        """Validate field_type is one of allowed values."""
        allowed_types = {'numeric', 'text', 'boolean', 'datetime', 'categorical'}
        if v not in allowed_types:
            raise ValueError(f"field_type must be one of {allowed_types}, got: {v}")
        return v

    @field_validator('data_type')
    @classmethod
    def validate_data_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate data_type is one of allowed values."""
        if v is None:
            return v
        allowed_types = {'nominal', 'ordinal', 'interval', 'ratio'}
        if v not in allowed_types:
            raise ValueError(f"data_type must be one of {allowed_types}, got: {v}")
        return v


class AISummary(BaseModel):
    """AI-generated summary of dataset contents."""

    overview: str = Field(..., description="High-level overview of the dataset")
    issues: List[str] = Field(default_factory=list, description="Identified data quality issues")
    relationships: List[str] = Field(default_factory=list, description="Identified relationships between columns")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions for data improvement")
    raw_markdown: str = Field(..., alias="rawMarkdown", description="Raw markdown version of summary")
    created_at: datetime = Field(default_factory=get_current_time, alias="createdAt")

    model_config = {
        "populate_by_name": True
    }


class PIIReport(BaseModel):
    """PII detection and risk assessment report."""

    contains_pii: bool = Field(default=False, description="Whether PII was detected")
    pii_fields: List[str] = Field(default_factory=list, description="List of fields containing PII")
    risk_level: str = Field(default="low", description="Overall PII risk level: low, medium, high")
    detection_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed PII detection results")
    masked: bool = Field(default=False, description="Whether PII has been masked")
    masked_at: Optional[datetime] = None

    @field_validator('risk_level')
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        """Validate risk_level is one of allowed values."""
        allowed_levels = {'low', 'medium', 'high'}
        if v not in allowed_levels:
            raise ValueError(f"risk_level must be one of {allowed_levels}, got: {v}")
        return v


class DatasetMetadata(Document):
    """
    Dataset metadata document.

    Stores comprehensive metadata about uploaded datasets including file information,
    schema, statistics, quality assessments, and PII detection results.

    This model replaces the dataset-specific fields from the legacy UserData model,
    providing focused responsibility for dataset metadata management.
    """

    # Ownership and identification
    user_id: Indexed(str) = Field(..., description="User who owns this dataset")
    dataset_id: Indexed(str) = Field(..., description="Unique dataset identifier")

    # File metadata
    filename: str = Field(..., description="Storage filename (may be generated)")
    original_filename: str = Field(..., description="Original filename from upload")
    file_type: str = Field(..., description="File type: csv, excel, json, parquet")
    file_path: str = Field(..., description="Storage path (e.g., S3 key)")
    s3_url: str = Field(..., description="S3 URL for file access")
    file_size: Optional[int] = Field(None, ge=0, description="File size in bytes")

    # Dataset dimensions
    num_rows: int = Field(..., ge=0, description="Number of rows in dataset")
    num_columns: int = Field(..., ge=0, description="Number of columns in dataset")
    columns: List[str] = Field(default_factory=list, description="Column names")

    # Schema information
    data_schema: List[SchemaField] = Field(default_factory=list, description="Detailed schema for each field")
    inferred_schema: Optional[Dict[str, Any]] = Field(None, alias="schema", description="Full inferred schema from processing")

    # Statistics and quality
    statistics: Optional[Dict[str, Any]] = Field(None, description="Calculated statistics for each column")
    quality_report: Optional[Dict[str, Any]] = Field(None, description="Data quality assessment results")
    data_preview: Optional[List[Dict[str, Any]]] = Field(None, description="Preview rows (first N rows)")

    # AI analysis
    ai_summary: Optional[AISummary] = Field(None, alias="aiSummary")

    # PII detection
    pii_report: Optional[PIIReport] = None

    # Processing status
    is_processed: bool = Field(default=False, description="Whether initial processing is complete")
    processed_at: Optional[datetime] = None

    # Onboarding
    onboarding_progress: Optional[Dict[str, Any]] = Field(None, description="User's onboarding tutorial progress")

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)

    # Version tracking
    version: str = Field(default="1.0.0", description="Dataset version (major.minor.patch)")
    parent_dataset_id: Optional[str] = Field(None, description="Parent dataset if this is derived")

    class Settings:
        name = "dataset_metadata"
        indexes = [
            # Single field indexes for basic queries
            "user_id",
            "dataset_id",
            "created_at",
            "is_processed",
            # Compound indexes for common query patterns
            [("user_id", 1), ("created_at", -1)],  # List user datasets chronologically
            [("user_id", 1), ("dataset_id", 1)],  # Unique lookup
            [("user_id", 1), ("is_processed", 1)],  # Filter unprocessed datasets
            [("user_id", 1), ("is_processed", 1), ("created_at", -1)],  # Processed datasets chronologically
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    @field_validator('file_type')
    @classmethod
    def validate_file_type(cls, v: str) -> str:
        """Validate file_type is one of supported types."""
        allowed_types = {'csv', 'excel', 'json', 'parquet', 'xlsx', 'xls'}
        if v.lower() not in allowed_types:
            raise ValueError(f"file_type must be one of {allowed_types}, got: {v}")
        return v.lower()

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = get_current_time()

    def mark_processed(self) -> None:
        """Mark dataset as processed and update timestamp."""
        self.is_processed = True
        self.processed_at = get_current_time()
        self.update_timestamp()

    def get_column_schema(self, column_name: str) -> Optional[SchemaField]:
        """Get schema information for a specific column."""
        for field in self.data_schema:
            if field.field_name == column_name:
                return field
        return None

    def has_pii(self) -> bool:
        """Check if dataset contains PII."""
        return self.pii_report is not None and self.pii_report.contains_pii

    def get_pii_risk_level(self) -> str:
        """Get PII risk level, defaulting to 'low' if no report."""
        if self.pii_report is None:
            return "low"
        return self.pii_report.risk_level
