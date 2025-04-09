# app/models/user_data.py

from beanie import Document, Indexed
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone


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


class UserData(Document):
    """Model for storing user uploaded data metadata"""

    user_id: str = Indexed(str)
    filename: str
    s3_url: str
    num_rows: int
    num_columns: int
    data_schema: List[SchemaField]
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)

    class Settings:
        name = "user_data"
        indexes = ["user_id", "created_at"]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
