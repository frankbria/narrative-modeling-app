from beanie import Document, Link
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from models.user_data import UserData
from models.plot import Plot


class AnalyticsResult(Document):
    userId: str
    datasetId: Link[UserData]
    createdAt: datetime = datetime.utcnow()
    analysisType: str  # e.g., "EDA", "regression", "clustering"
    config: Optional[dict] = None
    result: Optional[dict] = None
    plotRefs: Optional[List[Link[Plot]]] = None
    summaryText: Optional[str] = None

    class Settings:
        name = "analytics_results"
