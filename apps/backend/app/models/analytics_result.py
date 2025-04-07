# \app\models\analytics_result.py

from beanie import Document, Link
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from app.models.user_data import UserData
from app.models.plot import Plot


class AnalyticsResult(Document):
    userId: str
    datasetId: Link[UserData]
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analysisType: str  # e.g., "EDA", "regression", "clustering"
    config: Optional[dict] = None
    result: Optional[dict] = None
    plotRefs: Optional[List[Link[Plot]]] = None
    summaryText: Optional[str] = None

    class Settings:
        name = "analytics_results"
