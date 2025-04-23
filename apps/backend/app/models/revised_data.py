from beanie import Document, Link, Indexed
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from shared.models.user_data import UserData, SchemaField


def get_current_time() -> datetime:
    return datetime.now(timezone.utc)


class RevisedData(Document):
    """Model for storing revised versions of user data files"""

    user_id: str = Indexed(str)
    original_data: Link[UserData]  # Reference to the original dataset
    filename: str  # New filename for the revised version
    s3_url: str  # New S3 URL for the revised file
    num_rows: int  # Updated number of rows
    num_columns: int  # Updated number of columns
    data_schema: List[SchemaField]  # Updated schema
    revision_notes: Optional[str] = None  # Optional notes about what was revised
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)

    class Settings:
        name = "revised_data"
        indexes = ["user_id", "original_data", "created_at"]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
