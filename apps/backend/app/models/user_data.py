# app/models/user_data.py

from beanie import Document
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from datetime import datetime, timezone


class SchemaField(BaseModel):
    name: str
    type: str  # e.g., "string", "number"


class UserData(Document):
    userId: str
    name: Optional[str]
    uploadDate: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_data: dict = Field(..., alias="schema")
    fileUrl: HttpUrl
    previewRows: Optional[List[dict]] = None
    metadata: Optional[dict] = None

    class Settings:
        name = "users_data"

    class Config:
        allow_population_by_field_name = True
