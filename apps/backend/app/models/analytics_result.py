# app/models/analytics_result.py

from beanie import Document, Link
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from shared.models.user_data import UserData
from app.models.plot import Plot
from inspect import signature, Parameter


class AnalyticsResult(Document):
    userId: str
    datasetId: Link[UserData]
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analysisType: str  # e.g., "EDA", "regression", "clustering"
    config: Optional[dict] = None
    result: Optional[dict] = None
    plotRefs: Optional[List[Link[Plot]]] = None
    summaryText: Optional[str] = None

    def __init__(self, **data):
        # Pass only keyword arguments to the parent initalizer.
        super().__init__(**data)

    class Settings:
        name = "analytics_results"

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


def get_clean_signature(model):
    # Get the signature of the model's __init__ method
    sig = signature(model.__init__)
    # Filter out the parameters named 'args' and 'kwargs'
    new_params = [
        param
        for name, param in sig.parameters.items()
        if name not in ("args", "kwargs")
    ]
    return sig.replace(parameters=new_params)


# Override the signature
AnalyticsResult.__signature__ = get_clean_signature(AnalyticsResult)
