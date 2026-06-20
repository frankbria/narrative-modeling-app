from datetime import UTC, datetime

from beanie import Document, Indexed, Link
from pydantic import BaseModel, Field

from app.models.user_data import UserData


def get_current_time() -> datetime:
    return datetime.now(UTC)


class NumericHistogram(BaseModel):
    """Model for storing numeric histogram data"""

    bin_edges: list[float]
    bin_counts: list[int]
    bin_width: float
    min_value: float
    max_value: float


class CategoricalValueCounts(BaseModel):
    """Model for storing categorical value counts"""

    values: list[str]
    counts: list[int]
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
    min_value: float | None = None
    max_value: float | None = None
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    q1: float | None = None  # First quartile
    q3: float | None = None  # Third quartile
    skewness: float | None = None
    kurtosis: float | None = None

    # Text statistics
    min_length: int | None = None
    max_length: int | None = None
    avg_length: float | None = None

    # Date statistics
    min_date: datetime | None = None
    max_date: datetime | None = None

    # Histogram data
    numeric_histogram: NumericHistogram | None = None
    categorical_value_counts: CategoricalValueCounts | None = None

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
