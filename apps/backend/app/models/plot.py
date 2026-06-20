# app/models/plot.py

from datetime import UTC, datetime

from beanie import Document, Link
from pydantic import Field, HttpUrl

from app.models.user_data import UserData


class Plot(Document):
    userId: str
    datasetId: Link[UserData] | None
    type: str | None  # e.g., "histogram", "scatter"
    imageUrl: HttpUrl
    metadata: dict | None = None
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "plots"

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
