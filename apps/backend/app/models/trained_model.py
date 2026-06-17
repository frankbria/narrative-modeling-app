# \app\models\trained_model.py

from datetime import datetime, timezone
from typing import Optional

from beanie import Document, Link
from pydantic import Field, HttpUrl

from app.models.user_data import UserData


class TrainedModel(Document):
    userId: str
    datasetId: Optional[Link[UserData]]
    modelType: str
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    params: Optional[dict] = None
    performance: Optional[dict] = None
    modelFileUrl: Optional[HttpUrl] = None

    class Settings:
        name = "trained_models"

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
