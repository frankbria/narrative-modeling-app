from datetime import datetime
from typing import Any

from beanie import Document, Indexed, Link
from pydantic import BaseModel, Field

from app.models.user_data import UserData
from app.utils.datetime import utcnow


class HistogramData(BaseModel):
    """Model for storing histogram data"""

    bins: list[float]
    counts: list[int]
    bin_edges: list[float]


class BoxplotData(BaseModel):
    """Model for storing boxplot data"""

    min: float
    q1: float
    median: float
    q3: float
    max: float
    outliers: list[float]


class CorrelationMatrixData(BaseModel):
    """Model for storing correlation matrix data"""

    matrix: list[list[float]]
    columns: list[str]


class VisualizationCache(Document):
    """Model for caching visualization data"""

    dataset_id: Link[UserData] = Indexed(Link[UserData])
    visualization_type: str  # 'histogram', 'boxplot', 'correlation'
    column_name: str | None = None  # For histograms and boxplots
    data: dict[
        str, Any
    ]  # Will contain HistogramData, BoxplotData, or CorrelationMatrixData
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "visualization_cache"
        indexes = [
            "dataset_id",
            "visualization_type",
            "column_name",
            ("dataset_id", "visualization_type"),
            ("dataset_id", "visualization_type", "column_name"),
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
