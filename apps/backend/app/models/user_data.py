# app/models/user_data.py

from datetime import UTC, datetime
from typing import Any

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field


def get_current_time() -> datetime:
    return datetime.now(UTC)


class SchemaField(BaseModel):
    field_name: str
    field_type: str  # 'numeric', 'text', 'boolean', 'datetime', 'categorical'
    data_type: str | None = None  # 'nominal', 'ordinal', 'interval', 'ratio'
    inferred_dtype: str
    unique_values: int
    missing_values: int
    example_values: list[Any]
    is_constant: bool
    is_high_cardinality: bool


class AISummary(BaseModel):
    """Model for storing AI-generated summaries of datasets"""

    overview: str
    issues: list[str]
    relationships: list[str]
    suggestions: list[str]
    rawMarkdown: str
    createdAt: datetime = Field(default_factory=get_current_time)


class UserData(Document):
    """Model for storing user uploaded data metadata"""

    user_id: str = Indexed(str)
    filename: str
    original_filename: str  # Original filename from upload
    s3_url: str
    num_rows: int
    num_columns: int
    data_schema: list[SchemaField]
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)
    aiSummary: AISummary | None = None
    
    # PII-related fields
    contains_pii: bool = False
    pii_report: dict[str, Any] | None = None
    pii_risk_level: str | None = None  # "low", "medium", "high"
    pii_masked: bool = False
    
    # Data processing fields
    is_processed: bool = False
    processed_at: datetime | None = None
    schema: dict[str, Any] | None = None  # Inferred schema from data processing
    statistics: dict[str, Any] | None = None  # Calculated statistics
    quality_report: dict[str, Any] | None = None  # Data quality assessment
    row_count: int | None = None  # Actual row count after processing
    columns: list[str] | None = None  # Column names after processing
    data_preview: list[dict[str, Any]] | None = None  # Preview rows
    file_type: str | None = None  # csv, excel, json, etc.
    
    # Onboarding progress
    onboarding_progress: dict[str, Any] | None = None  # User's onboarding tutorial progress
    
    # Transformation tracking
    file_path: str | None = None  # Current file path (S3 key)
    transformation_history: list[dict[str, Any]] = Field(default_factory=list)  # History of transformations applied

    class Settings:
        name = "user_data"
        indexes = ["user_id", "created_at"]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str
        }
    }
