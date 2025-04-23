from beanie import Document, Link, Indexed
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.models.user_data import UserData


class HistogramData(BaseModel):
    """Model for storing histogram data"""

    bins: List[float]
    counts: List[int]
    bin_edges: List[float]


class BoxplotData(BaseModel):
    """Model for storing boxplot data"""

    min: float
    q1: float
    median: float
    q3: float
    max: float
    outliers: List[float]


class CorrelationMatrixData(BaseModel):
    """Model for storing correlation matrix data"""

    matrix: List[List[float]]
    columns: List[str]


class VisualizationCache(Document):
    """Model for caching visualization data"""

    dataset_id: Link[UserData] = Indexed(Link[UserData])
    visualization_type: str  # 'histogram', 'boxplot', 'correlation'
    column_name: Optional[str] = None  # For histograms and boxplots
    data: Dict[
        str, Any
    ]  # Will contain HistogramData, BoxplotData, or CorrelationMatrixData
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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
