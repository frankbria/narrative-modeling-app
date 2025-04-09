import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime


def infer_field_type(series: pd.Series) -> str:
    """
    Infer the field type based on the data in the series.
    Returns one of: 'numeric', 'text', 'boolean', 'datetime', 'categorical'
    """
    # Check if it's a boolean
    if series.dtype == bool or (
        series.dtype == object
        and series.dropna().apply(lambda x: isinstance(x, bool)).all()
    ):
        return "boolean"

    # Check if it's a datetime
    if pd.api.types.is_datetime64_any_dtype(series) or (
        series.dtype == object
        and series.dropna()
        .apply(lambda x: isinstance(x, (datetime, pd.Timestamp)))
        .all()
    ):
        return "datetime"

    # Check if it's numeric
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    # Check if it's categorical (limited number of unique values)
    unique_count = series.nunique()
    if unique_count < len(series) * 0.5:  # Less than 50% unique values
        return "categorical"

    # Default to text
    return "text"


def infer_data_type(series: pd.Series, field_type: str) -> Optional[str]:
    """
    Infer the data type based on the field type and data.
    Returns one of: 'nominal', 'ordinal', 'interval', 'ratio' or None if can't be inferred
    """
    if field_type == "categorical":
        # Check if the categories have a natural order
        if series.dtype == "category" and series.cat.ordered:
            return "ordinal"
        return "nominal"

    if field_type == "numeric":
        # Check if it's a ratio scale (has a true zero)
        if series.min() >= 0 and series.dtype in [np.int64, np.float64]:
            return "ratio"
        return "interval"

    if field_type == "datetime":
        return "interval"

    if field_type == "boolean":
        return "nominal"

    return None


def infer_schema(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Infer the schema for a DataFrame.
    Returns a list of field descriptions.
    """
    schema = []

    for column in df.columns:
        series = df[column]

        # Skip empty columns
        if series.empty:
            continue

        # Get basic stats
        unique_count = series.nunique()
        missing_count = series.isna().sum()
        total_count = len(series)

        # Get example values (up to 3 non-null values)
        example_values = series.dropna().head(3).tolist()

        # Infer field type
        field_type = infer_field_type(series)

        # Infer data type
        data_type = infer_data_type(series, field_type)

        # Create field description
        field = {
            "field_name": column,
            "field_type": field_type,
            "data_type": data_type,
            "inferred_dtype": str(series.dtype),
            "unique_values": int(unique_count),
            "missing_values": int(missing_count),
            "example_values": example_values,
            "is_constant": unique_count == 1,
            "is_high_cardinality": unique_count > total_count * 0.5,
        }

        schema.append(field)

    return schema


def generate_s3_filename(original_filename: str) -> str:
    """
    Generate a unique S3 filename using UUID.
    Preserves the original file extension.
    """
    # Get the file extension
    ext = original_filename.split(".")[-1] if "." in original_filename else ""

    # Generate a UUID
    unique_id = str(uuid.uuid4())

    # Combine with extension
    return f"{unique_id}.{ext}" if ext else unique_id
