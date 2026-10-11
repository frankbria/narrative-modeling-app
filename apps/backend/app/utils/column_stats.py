
import numpy as np
import pandas as pd
from beanie import PydanticObjectId
from pymongo.errors import BulkWriteError

from app.models.column_stats import (
    CategoricalValueCounts,
    ColumnStats,
    NumericHistogram,
)
from app.models.user_data import UserData

_DUPLICATE_KEY = 11000  # MongoDB's E11000


async def calculate_and_store_column_stats(
    df: pd.DataFrame, dataset_id: str, user_id: str
) -> list[ColumnStats]:
    """
    Calculate descriptive statistics for each column in a DataFrame and store them in the database.

    Args:
        df: The pandas DataFrame containing the data
        dataset_id: The ID of the dataset
        user_id: The ID of the user who owns the dataset

    Returns:
        The computed ColumnStats, complete even when a concurrent recompute
        stored the rows first (see _store)
    """
    # Get the dataset document
    dataset = await UserData.get(dataset_id)
    if not dataset:
        raise ValueError(f"Dataset with ID {dataset_id} not found")

    # Verify the user owns the dataset
    if dataset.user_id != user_id:
        raise ValueError(f"User {user_id} does not own dataset {dataset_id}")

    column_stats_list = [
        _column_stats(df[column_name], column_name, dataset, user_id)
        for column_name in df.columns
        if not df[column_name].empty
    ]
    await _store(column_stats_list)
    return column_stats_list


def _column_stats(
    series: pd.Series, column_name: str, dataset: UserData, user_id: str
) -> ColumnStats:
    """One column's statistics, not yet stored."""
    data_type = _determine_data_type(series)

    column_stats = ColumnStats(
        dataset_id=dataset,
        user_id=user_id,
        column_name=column_name,
        data_type=data_type,
        count=len(series),
        missing=series.isna().sum(),
        unique=series.nunique(),
    )

    if data_type == "numeric":
        _add_numeric_stats(column_stats, series)
    elif data_type == "categorical":
        _add_categorical_stats(column_stats, series)
    elif data_type == "date":
        _add_date_stats(column_stats, series)
    elif data_type == "text":
        _add_text_stats(column_stats, series)

    # Assign the id up front so the single bulk write in _store does not
    # leave these objects id-less.
    column_stats.id = PydanticObjectId()
    return column_stats


async def _store(column_stats_list: list[ColumnStats]) -> None:
    """Write a dataset's stats in one bulk write; lose a concurrent race quietly.

    One insert_many rather than an insert per column: `recalculate` deletes the
    old rows first, so per-column inserts left a long window in which a failure
    destroyed a complete set and left a partial one.

    A duplicate key on dataset_column_unique (#543) means another request is
    storing this same dataset's stats. The caller keeps the list it computed
    and must not re-read instead (#715): insert_many is not atomic across
    documents, so the winner may have written only some of its rows. Any other
    bulk failure raises.
    """
    if not column_stats_list:
        return
    try:
        await ColumnStats.insert_many(column_stats_list)
    except BulkWriteError as e:
        codes = {err.get("code") for err in e.details.get("writeErrors", [])}
        if codes != {_DUPLICATE_KEY}:
            raise


def _determine_data_type(series: pd.Series) -> str:
    """Determine the data type of a pandas Series"""
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    elif pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    elif pd.api.types.is_bool_dtype(series):
        return "boolean"
    elif pd.api.types.is_string_dtype(series) or pd.api.types.is_categorical_dtype(
        series
    ):
        # Check if it's a categorical with few unique values
        if series.nunique() < min(len(series) * 0.5, 50):
            return "categorical"
        else:
            return "text"
    else:
        return "text"  # Default to text for unknown types


def _add_numeric_stats(column_stats: ColumnStats, series: pd.Series) -> None:
    """Add numeric statistics to a ColumnStats object"""
    # Drop NaN values for calculations
    clean_series = series.dropna()

    if len(clean_series) == 0:
        return

    # Basic statistics
    column_stats.min_value = float(clean_series.min())
    column_stats.max_value = float(clean_series.max())
    column_stats.mean = float(clean_series.mean())
    column_stats.median = float(clean_series.median())
    column_stats.std = float(clean_series.std())

    # Quartiles
    column_stats.q1 = float(clean_series.quantile(0.25))
    column_stats.q3 = float(clean_series.quantile(0.75))

    # Skewness and kurtosis
    column_stats.skewness = float(clean_series.skew())
    column_stats.kurtosis = float(clean_series.kurtosis())

    # Create histogram
    hist, bin_edges = np.histogram(
        clean_series, bins=min(30, len(clean_series.unique()))
    )

    column_stats.numeric_histogram = NumericHistogram(
        bin_edges=bin_edges.tolist(),
        bin_counts=hist.tolist(),
        bin_width=float(bin_edges[1] - bin_edges[0]),
        min_value=float(bin_edges[0]),
        max_value=float(bin_edges[-1]),
    )


def _add_categorical_stats(column_stats: ColumnStats, series: pd.Series) -> None:
    """Add categorical statistics to a ColumnStats object"""
    # Get value counts
    value_counts = series.value_counts()

    # Get top N values
    top_n = min(10, len(value_counts))
    top_values = value_counts.head(top_n)

    column_stats.categorical_value_counts = CategoricalValueCounts(
        values=top_values.index.tolist(), counts=top_values.values.tolist(), top_n=top_n
    )


def _add_date_stats(column_stats: ColumnStats, series: pd.Series) -> None:
    """Add date statistics to a ColumnStats object"""
    # Drop NaN values for calculations
    clean_series = series.dropna()

    if len(clean_series) == 0:
        return

    # Convert to datetime if not already
    if not pd.api.types.is_datetime64_any_dtype(clean_series):
        clean_series = pd.to_datetime(clean_series)

    # Min and max dates
    column_stats.min_date = clean_series.min()
    column_stats.max_date = clean_series.max()


def _add_text_stats(column_stats: ColumnStats, series: pd.Series) -> None:
    """Add text statistics to a ColumnStats object"""
    # Drop NaN values for calculations
    clean_series = series.dropna()

    if len(clean_series) == 0:
        return

    # Convert to string if not already
    if not pd.api.types.is_string_dtype(clean_series):
        clean_series = clean_series.astype(str)

    # Calculate string lengths
    lengths = clean_series.str.len()

    column_stats.min_length = int(lengths.min())
    column_stats.max_length = int(lengths.max())
    column_stats.avg_length = float(lengths.mean())
