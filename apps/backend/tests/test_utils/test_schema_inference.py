import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from app.utils.schema_inference import infer_field_type, infer_data_type, infer_schema


def test_infer_field_type_numeric():
    """Test inferring field type for numeric data."""
    # Test with integer data
    int_series = pd.Series([1, 2, 3, 4, 5])
    assert infer_field_type(int_series) == "numeric"

    # Test with float data
    float_series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert infer_field_type(float_series) == "numeric"

    # Test with mixed numeric data
    mixed_series = pd.Series([1, 2.0, 3, 4.0, 5])
    assert infer_field_type(mixed_series) == "numeric"


def test_infer_field_type_boolean():
    """Test inferring field type for boolean data."""
    # Test with boolean data
    bool_series = pd.Series([True, False, True, False, True])
    assert infer_field_type(bool_series) == "boolean"

    # Test with object boolean data
    obj_bool_series = pd.Series([True, False, True, False, True], dtype=object)
    assert infer_field_type(obj_bool_series) == "boolean"


def test_infer_field_type_datetime():
    """Test inferring field type for datetime data."""
    # Test with datetime data
    datetime_series = pd.Series(
        [datetime(2023, 1, 1), datetime(2023, 1, 2), datetime(2023, 1, 3)]
    )
    assert infer_field_type(datetime_series) == "datetime"

    # Test with string datetime data
    str_datetime_series = pd.Series(["2023-01-01", "2023-01-02", "2023-01-03"])
    assert (
        infer_field_type(str_datetime_series) == "text"
    )  # Should be text as it's not parsed as datetime


def test_infer_field_type_categorical():
    """Test inferring field type for categorical data."""
    # Test with categorical data (less than 50% unique values)
    cat_series = pd.Series(["A", "B", "A", "B", "A", "B", "A", "B", "A", "B"])
    assert infer_field_type(cat_series) == "categorical"

    # Test with string data that's not categorical
    text_series = pd.Series(
        [
            "This is a long text",
            "Another long text",
            "Yet another long text",
            "More long text",
            "Even more long text",
        ]
    )
    assert infer_field_type(text_series) == "text"


def test_infer_data_type_numeric():
    """Test inferring data type for numeric data."""
    # Test with ratio scale (has true zero)
    ratio_series = pd.Series([0, 1, 2, 3, 4, 5])
    assert infer_data_type(ratio_series, "numeric") == "ratio"

    # Test with interval scale (no true zero)
    interval_series = pd.Series([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5])
    assert infer_data_type(interval_series, "numeric") == "interval"


def test_infer_data_type_categorical():
    """Test inferring data type for categorical data."""
    # Test with nominal categorical data
    nominal_series = pd.Series(["A", "B", "C", "A", "B", "C"])
    assert infer_data_type(nominal_series, "categorical") == "nominal"

    # Test with ordinal categorical data
    ordinal_series = pd.Series(["Low", "Medium", "High", "Low", "Medium", "High"])
    ordinal_series = ordinal_series.astype("category")
    ordinal_series = ordinal_series.cat.set_categories(
        ["Low", "Medium", "High"], ordered=True
    )
    assert infer_data_type(ordinal_series, "categorical") == "ordinal"


def test_infer_data_type_datetime():
    """Test inferring data type for datetime data."""
    datetime_series = pd.Series(
        [datetime(2023, 1, 1), datetime(2023, 1, 2), datetime(2023, 1, 3)]
    )
    assert infer_data_type(datetime_series, "datetime") == "interval"


def test_infer_data_type_boolean():
    """Test inferring data type for boolean data."""
    bool_series = pd.Series([True, False, True, False, True])
    assert infer_data_type(bool_series, "boolean") == "nominal"


def test_infer_schema():
    """Test inferring schema for a DataFrame."""
    # Create a test DataFrame with various data types
    df = pd.DataFrame(
        {
            "numeric_int": [1, 2, 3, 4, 5],
            "numeric_float": [1.0, 2.0, 3.0, 4.0, 5.0],
            "boolean": [True, False, True, False, True],
            "datetime": [
                datetime(2023, 1, 1),
                datetime(2023, 1, 2),
                datetime(2023, 1, 3),
                datetime(2023, 1, 4),
                datetime(2023, 1, 5),
            ],
            "categorical": ["A", "B", "A", "B", "A"],
            "text": [
                "This is a long text",
                "Another long text",
                "Yet another long text",
                "More long text",
                "Even more long text",
            ],
        }
    )

    schema = infer_schema(df)

    # Check that all columns are included
    assert len(schema) == 6

    # Check numeric columns
    numeric_int_field = next(f for f in schema if f["field_name"] == "numeric_int")
    assert numeric_int_field["field_type"] == "numeric"
    assert numeric_int_field["data_type"] == "ratio"
    assert numeric_int_field["unique_values"] == 5
    assert numeric_int_field["missing_values"] == 0
    assert numeric_int_field["is_constant"] is False
    assert numeric_int_field["is_high_cardinality"] is True  # 5 unique values out of 5 = 100% unique

    # Check boolean column
    boolean_field = next(f for f in schema if f["field_name"] == "boolean")
    assert boolean_field["field_type"] == "boolean"
    assert boolean_field["data_type"] == "nominal"
    assert boolean_field["unique_values"] == 2
    assert boolean_field["missing_values"] == 0
    assert boolean_field["is_constant"] is False
    assert boolean_field["is_high_cardinality"] is False

    # Check datetime column
    datetime_field = next(f for f in schema if f["field_name"] == "datetime")
    assert datetime_field["field_type"] == "datetime"
    assert datetime_field["data_type"] == "interval"
    assert datetime_field["unique_values"] == 5
    assert datetime_field["missing_values"] == 0
    assert datetime_field["is_constant"] is False
    assert datetime_field["is_high_cardinality"] is True  # 5 unique values out of 5 = 100% unique

    # Check categorical column
    categorical_field = next(f for f in schema if f["field_name"] == "categorical")
    assert categorical_field["field_type"] == "categorical"
    assert categorical_field["data_type"] == "nominal"
    assert categorical_field["unique_values"] == 2
    assert categorical_field["missing_values"] == 0
    assert categorical_field["is_constant"] is False
    assert categorical_field["is_high_cardinality"] is False

    # Check text column
    text_field = next(f for f in schema if f["field_name"] == "text")
    assert text_field["field_type"] == "text"
    assert text_field["data_type"] is None
    assert text_field["unique_values"] == 5
    assert text_field["missing_values"] == 0
    assert text_field["is_constant"] is False
    assert text_field["is_high_cardinality"] is True


def test_infer_schema_with_missing_values():
    """Test inferring schema for a DataFrame with missing values."""
    df = pd.DataFrame(
        {
            "numeric": [1, 2, None, 4, 5],
            "categorical": ["A", "B", None, "A", "B"],
            "text": ["Text 1", None, "Text 3", "Text 4", "Text 5"],
        }
    )

    schema = infer_schema(df)

    # Check numeric column
    numeric_field = next(f for f in schema if f["field_name"] == "numeric")
    assert numeric_field["missing_values"] == 1
    assert numeric_field["unique_values"] == 4

    # Check categorical column
    categorical_field = next(f for f in schema if f["field_name"] == "categorical")
    assert categorical_field["missing_values"] == 1
    assert categorical_field["unique_values"] == 2

    # Check text column
    text_field = next(f for f in schema if f["field_name"] == "text")
    assert text_field["missing_values"] == 1
    assert text_field["unique_values"] == 4  # 4 unique non-null values


def test_infer_schema_with_constant_column():
    """Test inferring schema for a DataFrame with a constant column."""
    df = pd.DataFrame({"constant": [1, 1, 1, 1, 1], "varying": [1, 2, 3, 4, 5]})

    schema = infer_schema(df)

    # Check constant column
    constant_field = next(f for f in schema if f["field_name"] == "constant")
    assert constant_field["is_constant"] is True
    assert constant_field["unique_values"] == 1

    # Check varying column
    varying_field = next(f for f in schema if f["field_name"] == "varying")
    assert varying_field["is_constant"] is False
    assert varying_field["unique_values"] == 5


def test_infer_schema_with_high_cardinality():
    """Test inferring schema for a DataFrame with high cardinality columns."""
    df = pd.DataFrame(
        {
            "high_cardinality": [
                f"value_{i}" for i in range(100)
            ],  # 100% unique values
            "low_cardinality": ["A", "B"] * 50,  # 2 unique values
        }
    )

    schema = infer_schema(df)

    # Check high cardinality column
    high_card_field = next(f for f in schema if f["field_name"] == "high_cardinality")
    assert high_card_field["is_high_cardinality"] is True
    assert high_card_field["unique_values"] == 100

    # Check low cardinality column
    low_card_field = next(f for f in schema if f["field_name"] == "low_cardinality")
    assert low_card_field["is_high_cardinality"] is False
    assert low_card_field["unique_values"] == 2
