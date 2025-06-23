"""
Response schemas for UserData API endpoints
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.user_data import SchemaField, AISummary


class UserDataResponse(BaseModel):
    """Response model for UserData that properly handles MongoDB ID"""
    
    id: str = Field(alias="_id")
    user_id: str
    filename: str
    original_filename: str
    s3_url: str
    num_rows: int
    num_columns: int
    data_schema: List[SchemaField]
    created_at: datetime
    updated_at: datetime
    aiSummary: Optional[AISummary] = None
    
    # PII-related fields
    contains_pii: bool = False
    pii_report: Optional[Dict[str, Any]] = None
    pii_risk_level: Optional[str] = None
    pii_masked: bool = False
    
    # Data processing fields
    is_processed: bool = False
    processed_at: Optional[datetime] = None
    schema: Optional[Dict[str, Any]] = None
    statistics: Optional[Dict[str, Any]] = None
    quality_report: Optional[Dict[str, Any]] = None
    row_count: Optional[int] = None
    columns: Optional[List[str]] = None
    data_preview: Optional[List[Dict[str, Any]]] = None
    file_type: Optional[str] = None
    
    # Onboarding progress
    onboarding_progress: Optional[Dict[str, Any]] = None
    
    # Transformation tracking
    file_path: Optional[str] = None
    transformation_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True
    )