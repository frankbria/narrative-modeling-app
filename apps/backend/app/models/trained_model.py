# \app\models\trained_model.py

from datetime import UTC, datetime

from beanie import Document, Link
from pydantic import Field, HttpUrl

from app.models.user_data import UserData


class TrainedModel(Document):
    userId: str
    datasetId: Link[UserData] | None
    modelType: str
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    params: dict | None = None
    performance: dict | None = None
    modelFileUrl: HttpUrl | None = None

    class Settings:
        name = "trained_models"

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
