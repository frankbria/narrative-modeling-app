from beanie import Document, Link, Indexed
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from shared.models.user_data import UserData


def get_current_time() -> datetime:
    return datetime.now(timezone.utc)


class NumericHistogram(BaseModel):
    """Model for storing numeric histogram data"""

    bin_edges: List[float]
    bin_counts: List[int]
    bin_width: float
    min_value: float
    max_value: float


class CategoricalValueCounts(BaseModel):
    """Model for storing categorical value counts"""

    values: List[str]
    counts: List[int]
    top_n: int = 10  # Number of top values to store


class ColumnStats(Document):
    """Model for storing per-column descriptive statistics and histograms"""

    dataset_id: Link[UserData] = Indexed(Link[UserData])
    column_name: str = Indexed(str)
    data_type: str  # 'numeric', 'categorical', 'date', 'text', 'boolean'

    # Basic statistics
    count: int
    missing: int
    unique: int

    # Numeric statistics
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    q1: Optional[float] = None  # First quartile
    q3: Optional[float] = None  # Third quartile
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None

    # Text statistics
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    avg_length: Optional[float] = None

    # Date statistics
    min_date: Optional[datetime] = None
    max_date: Optional[datetime] = None

    # Histogram data
    numeric_histogram: Optional[NumericHistogram] = None
    categorical_value_counts: Optional[CategoricalValueCounts] = None

    # Metadata
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)

    class Settings:
        name = "column_stats"
        indexes = [
            "dataset_id",
            "column_name",
            ("dataset_id", "column_name"),  # Compound index for faster lookups
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
