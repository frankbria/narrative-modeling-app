"""
Response schemas for UserData API endpoints
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.user_data import AISummary, SchemaField


class UserDataResponse(BaseModel):
    """Response model for UserData that properly handles MongoDB ID"""
    
    id: str = Field(alias="_id")
    user_id: str
    filename: str
    original_filename: str
    s3_url: str
    num_rows: int
    num_columns: int
    data_schema: list[SchemaField]
    created_at: datetime
    updated_at: datetime
    aiSummary: AISummary | None = None
    
    # PII-related fields
    contains_pii: bool = False
    pii_report: dict[str, Any] | None = None
    pii_risk_level: str | None = None
    pii_masked: bool = False
    
    # Data processing fields
    is_processed: bool = False
    processed_at: datetime | None = None
    # `schema` shadows Pydantic's deprecated `BaseModel.schema()`; it is part of
    # the public response contract and cannot be renamed.
    schema: dict[str, Any] | None = None  # type: ignore[assignment]
    statistics: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    row_count: int | None = None
    columns: list[str] | None = None
    data_preview: list[dict[str, Any]] | None = None
    file_type: str | None = None
    
    # Onboarding progress
    onboarding_progress: dict[str, Any] | None = None
    
    # Transformation tracking
    file_path: str | None = None
    transformation_history: list[dict[str, Any]] = Field(default_factory=list)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True
    )