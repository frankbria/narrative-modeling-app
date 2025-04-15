# app/schemas/analytics_result_out.py
from pydantic import BaseModel, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime


class AnalyticsResultOut(BaseModel):
    id: str
    userId: str
    datasetId: str  # Or adjust according to your ID format
    createdAt: datetime
    analysisType: str
    config: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    plotRefs: Optional[List[str]] = None
    summaryText: Optional[str] = None

    @model_validator(mode="before")
    def convert_fields(cls, data):
        """
        Convert types from the persistence model to the types expected by the API.
        This validator runs before standard validation.
        """
        # If data is not a dict (for instance, an AnalyticsResult instance), attempt to extract a dict.
        if not isinstance(data, dict):
            # You might use data.model_dump() if available, or data.__dict__
            data = data.model_dump() if hasattr(data, "model_dump") else data.__dict__

        # Convert the 'id' field to a string.
        if "id" in data and not isinstance(data["id"], str):
            data["id"] = str(data["id"])

        # For datasetId, if it's a Link, convert to string. Otherwise, convert directly.
        if "datasetId" in data:
            dataset = data["datasetId"]
            if hasattr(dataset, "ref"):
                data["datasetId"] = str(dataset.ref.id)
            elif not isinstance(dataset, str):
                data["datasetId"] = str(dataset)

        # For plotRefs, process each item similarly.
        if "plotRefs" in data and isinstance(data["plotRefs"], list):
            converted = []
            for ref in data["plotRefs"]:
                # If the ref has a "ref" attribute, use its id.
                if hasattr(ref, "ref"):
                    converted.append(str(ref.ref.id))
                else:
                    converted.append(str(ref))
            data["plotRefs"] = converted

        return data

    class Config:
        from_attributes = True
