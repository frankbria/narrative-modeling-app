# app/models/user_data.py

from beanie import Document, Indexed
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from beanie import PydanticObjectId


def get_current_time() -> datetime:
    return datetime.now(timezone.utc)


class SchemaField(BaseModel):
    field_name: str
    field_type: str  # 'numeric', 'text', 'boolean', 'datetime', 'categorical'
    data_type: Optional[str] = None  # 'nominal', 'ordinal', 'interval', 'ratio'
    inferred_dtype: str
    unique_values: int
    missing_values: int
    example_values: List[Any]
    is_constant: bool
    is_high_cardinality: bool


class AISummary(BaseModel):
    """Model for storing AI-generated summaries of datasets"""

    overview: str
    issues: List[str]
    relationships: List[str]
    suggestions: List[str]
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
    data_schema: List[SchemaField]
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)
    aiSummary: Optional[AISummary] = None
    
    # PII-related fields
    contains_pii: bool = False
    pii_report: Optional[Dict[str, Any]] = None
    pii_risk_level: Optional[str] = None  # "low", "medium", "high"
    pii_masked: bool = False
    
    # Data processing fields
    is_processed: bool = False
    processed_at: Optional[datetime] = None
    schema: Optional[Dict[str, Any]] = None  # Inferred schema from data processing
    statistics: Optional[Dict[str, Any]] = None  # Calculated statistics
    quality_report: Optional[Dict[str, Any]] = None  # Data quality assessment
    row_count: Optional[int] = None  # Actual row count after processing
    columns: Optional[List[str]] = None  # Column names after processing
    data_preview: Optional[List[Dict[str, Any]]] = None  # Preview rows
    file_type: Optional[str] = None  # csv, excel, json, etc.
    
    # Onboarding progress
    onboarding_progress: Optional[Dict[str, Any]] = None  # User's onboarding tutorial progress
    
    # Transformation tracking
    file_path: Optional[str] = None  # Current file path (S3 key)
    transformation_history: List[Dict[str, Any]] = Field(default_factory=list)  # History of transformations applied

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
