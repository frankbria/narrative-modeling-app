# app/models/plot.py

from beanie import Document, Link
from pydantic import HttpUrl, Field
from typing import Optional
from datetime import datetime, timezone
from shared.models.user_data import UserData


class Plot(Document):
    userId: str
    datasetId: Optional[Link[UserData]]
    type: Optional[str]  # e.g., "histogram", "scatter"
    imageUrl: HttpUrl
    metadata: Optional[dict] = None
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "plots"

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
