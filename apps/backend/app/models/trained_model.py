from beanie import Document, Link
from pydantic import HttpUrl
from typing import Optional
from datetime import datetime
from models.user_data import UserData


class TrainedModel(Document):
    userId: str
    datasetId: Optional[Link[UserData]]
    modelType: str
    createdAt: datetime = datetime.utcnow()
    params: Optional[dict] = None
    performance: Optional[dict] = None
    modelFileUrl: Optional[HttpUrl] = None

    class Settings:
        name = "trained_models"
