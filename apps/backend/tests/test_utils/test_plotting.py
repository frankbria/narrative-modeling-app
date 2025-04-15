import pytest
import numpy as np
import pandas as pd
from app.utils.plotting import (
    generate_histogram,
    generate_boxplot,
    generate_correlation_matrix,
)
from app.models.visualization_cache import (
    HistogramData,
    BoxplotData,
    CorrelationMatrixData,
)


@pytest.fixture
def sample_numeric_data():
    """Create sample numeric data for testing."""
    return pd.Series([1, 2, 2, 3, 3, 3, 4, 4, 5, 5, 6, 7, 8, 9, 10])


@pytest.fixture
def sample_numeric_dataframe():
    """Create sample numeric dataframe for testing."""
    return pd.DataFrame(
        {
            "col1": [1, 2, 3, 4, 5],
            "col2": [2, 4, 6, 8, 10],
            "col3": [1, 3, 5, 7, 9],
        }
    )


def test_generate_histogram(sample_numeric_data):
    """Test histogram generation with valid numeric data."""
    num_bins = 5
    result = generate_histogram(sample_numeric_data, num_bins)

    assert isinstance(result, HistogramData)
    assert len(result.bins) == num_bins
    assert len(result.counts) == num_bins
    assert len(result.bin_edges) == num_bins + 1
    assert sum(result.counts) == len(sample_numeric_data)
    assert all(count >= 0 for count in result.counts)


def test_generate_histogram_empty_data():
    """Test histogram generation with empty data."""
    empty_data = pd.Series([])
    result = generate_histogram(empty_data)

    assert isinstance(result, HistogramData)
    assert len(result.bins) == 0
    assert len(result.counts) == 0
    assert len(result.bin_edges) == 1


def test_generate_histogram_with_nulls():
    """Test histogram generation with data containing null values."""
    data_with_nulls = pd.Series([1, 2, np.nan, 3, 4, np.nan, 5])
    result = generate_histogram(data_with_nulls)

    assert isinstance(result, HistogramData)
    assert sum(result.counts) == len(data_with_nulls.dropna())
    assert all(count >= 0 for count in result.counts)


def test_generate_boxplot(sample_numeric_data):
    """Test boxplot generation with valid numeric data."""
    result = generate_boxplot(sample_numeric_data)

    assert isinstance(result, BoxplotData)
    assert result.min == sample_numeric_data.min()
    assert result.max == sample_numeric_data.max()
    assert result.q1 == sample_numeric_data.quantile(0.25)
    assert result.median == sample_numeric_data.median()
    assert result.q3 == sample_numeric_data.quantile(0.75)
    assert isinstance(result.outliers, list)
    assert all(isinstance(x, float) for x in result.outliers)


def test_generate_boxplot_empty_data():
    """Test boxplot generation with empty data."""
    empty_data = pd.Series([])
    result = generate_boxplot(empty_data)

    assert isinstance(result, BoxplotData)
    assert np.isnan(result.min)
    assert np.isnan(result.max)
    assert np.isnan(result.q1)
    assert np.isnan(result.median)
    assert np.isnan(result.q3)
    assert len(result.outliers) == 0


def test_generate_boxplot_with_nulls():
    """Test boxplot generation with data containing null values."""
    data_with_nulls = pd.Series([1, 2, np.nan, 3, 4, np.nan, 5])
    result = generate_boxplot(data_with_nulls)

    assert isinstance(result, BoxplotData)
    assert result.min == data_with_nulls.min()
    assert result.max == data_with_nulls.max()
    assert result.q1 == data_with_nulls.quantile(0.25)
    assert result.median == data_with_nulls.median()
    assert result.q3 == data_with_nulls.quantile(0.75)
    assert isinstance(result.outliers, list)


def test_generate_correlation_matrix(sample_numeric_dataframe):
    """Test correlation matrix generation with valid numeric dataframe."""
    result = generate_correlation_matrix(sample_numeric_dataframe)

    assert isinstance(result, CorrelationMatrixData)
    assert len(result.matrix) == len(sample_numeric_dataframe.columns)
    assert len(result.matrix[0]) == len(sample_numeric_dataframe.columns)
    assert len(result.columns) == len(sample_numeric_dataframe.columns)
    assert all(abs(val) <= 1 for row in result.matrix for val in row)
    assert all(col in sample_numeric_dataframe.columns for col in result.columns)


def test_generate_correlation_matrix_empty_dataframe():
    """Test correlation matrix generation with empty dataframe."""
    empty_df = pd.DataFrame()
    result = generate_correlation_matrix(empty_df)

    assert isinstance(result, CorrelationMatrixData)
    assert len(result.matrix) == 0
    assert len(result.columns) == 0


def test_generate_correlation_matrix_with_nulls():
    """Test correlation matrix generation with dataframe containing null values."""
    df_with_nulls = pd.DataFrame(
        {
            "col1": [1, 2, np.nan, 4, 5],
            "col2": [2, 4, 6, np.nan, 10],
            "col3": [1, np.nan, 5, 7, 9],
        }
    )
    result = generate_correlation_matrix(df_with_nulls)

    assert isinstance(result, CorrelationMatrixData)
    assert len(result.matrix) == len(df_with_nulls.columns)
    assert len(result.matrix[0]) == len(df_with_nulls.columns)
    assert len(result.columns) == len(df_with_nulls.columns)
    assert all(abs(val) <= 1 for row in result.matrix for val in row)


def test_generate_correlation_matrix_with_non_numeric():
    """Test correlation matrix generation with dataframe containing non-numeric columns."""
    mixed_df = pd.DataFrame(
        {
            "numeric": [1, 2, 3, 4, 5],
            "string": ["a", "b", "c", "d", "e"],
            "boolean": [True, False, True, False, True],
        }
    )
    result = generate_correlation_matrix(mixed_df)

    assert isinstance(result, CorrelationMatrixData)
    assert len(result.matrix) == 1  # Only numeric column
    assert len(result.matrix[0]) == 1
    assert len(result.columns) == 1
    assert result.columns[0] == "numeric"
