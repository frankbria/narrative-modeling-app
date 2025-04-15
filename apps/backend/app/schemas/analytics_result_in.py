# app/schemas/analytics_result_in.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class AnalyticsResultIn(BaseModel):
    datasetId: str  # or change to an ObjectId-like string if necessary
    analysisType: str
    config: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    plotRefs: Optional[List[str]] = None
    summaryText: Optional[str] = None

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
