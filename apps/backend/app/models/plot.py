from beanie import Document, Link
from pydantic import HttpUrl
from typing import Optional
from datetime import datetime
from models.user_data import UserData


class Plot(Document):
    userId: str
    datasetId: Optional[Link[UserData]]
    type: Optional[str]  # e.g., "histogram", "scatter"
    imageUrl: HttpUrl
    metadata: Optional[dict] = None
    generatedAt: datetime = datetime.utcnow()

    class Settings:
        name = "plots"
