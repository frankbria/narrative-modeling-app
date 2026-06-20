# app/schemas/analytics_result_in.py
from typing import Any

from pydantic import BaseModel


class AnalyticsResultIn(BaseModel):
    datasetId: str  # or change to an ObjectId-like string if necessary
    analysisType: str
    config: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    plotRefs: list[str] | None = None
    summaryText: str | None = None

    class Config:
        schema_extra = {
            "example": {
                "datasetId": "67fdb854cef0d907308298aa",
                "analysisType": "EDA",
                "config": {"columns": ["column1", "column2"]},
                "result": {"summary": "Test analysis"},
                "plotRefs": ["67fdb854cef0d907308298ab"],
                "summaryText": "Test summary",
            }
        }
