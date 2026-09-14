from datetime import UTC, datetime
from typing import Annotated

import pymongo
from beanie import Document, Indexed, Link
from pydantic import BaseModel, Field
from pymongo import IndexModel

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
    # Owner of the dataset these stats describe. Optional so rows written
    # before #449 still validate; they simply miss the scoped cache read and
    # are recomputed, which then stamps this field.
    user_id: Annotated[str | None, Indexed()] = None
    column_name: str = Indexed(str)
    data_type: str  # 'numeric', 'categorical', 'date', 'text', 'boolean'

    # Basic statistics
    # `count` shadows Beanie's inherited `count()` query method; renaming would
    # change the persisted field name and the constructor kwarg used elsewhere.
    count: int  # type: ignore[assignment]
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
            # One stats row per (dataset, column) — before #543 the broken cache query
            # re-inserted a full set on every GET, growing the collection without bound.
            # A NEW index name (not the old non-unique compound) because Mongo refuses to
            # rebuild an existing name with different options (#565). Run
            # scripts/dedupe_column_stats.py BEFORE deploying: a unique index cannot build
            # while duplicates exist (startup would fail).
            IndexModel(
                [("dataset_id", pymongo.ASCENDING), ("column_name", pymongo.ASCENDING)],
                name="dataset_column_unique",
                unique=True,
            ),
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
