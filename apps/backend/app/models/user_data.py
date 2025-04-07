from beanie import Document
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime


class SchemaField(BaseModel):
    name: str
    type: str  # e.g., "string", "number"


class UserData(Document):
    userId: str
    name: Optional[str]
    uploadDate: datetime = datetime.utcnow()
    schema: List[SchemaField]
    fileUrl: HttpUrl
    previewRows: Optional[List[dict]] = None
    metadata: Optional[dict] = None

    class Settings:
        name = "users_data"
