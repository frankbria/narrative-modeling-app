import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch

from mcp.tools.eda_summary import (
    eda_summary,
    EdaInput,
    calculate_data_quality,
    calculate_variable_insights,
    suggest_transformations,
    generate_grouped_insights,
)


@pytest.fixture
def sample_df():
    """Create a deterministic sample DataFrame for testing."""
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "id": range(1, 101),
            "numeric_normal": rng.normal(0, 1, 100),
            "numeric_skewed": np.exp(rng.normal(0, 1, 100)),
            "category": rng.choice(["A", "B", "C"], 100),
            "high_cardinality": [f"val_{i}" for i in range(100)],
            "missing_values": np.where(
                rng.random(100) > 0.8, np.nan, rng.random(100)
            ),
        }
    )


def test_eda_summary_success(sample_df):
    """eda_summary returns a success envelope with all expected sections."""
    with patch(
        "mcp.tools.eda_summary.download_file_from_s3", return_value="temp.csv"
    ), patch("pandas.read_csv", return_value=sample_df):
        result = eda_summary(EdaInput(file_uri="s3://bucket/file.csv"))

    assert result["success"] is True
    assert isinstance(result["data"], dict)
    assert all(
        k in result["data"]
        for k in [
            "overview",
            "dataQuality",
            "variableInsights",
            "transformations",
            "groupedInsights",
        ]
    )


def test_calculate_data_quality(sample_df):
    """Data quality calculation reports missing data, outliers, and skew."""
    quality_metrics = calculate_data_quality(sample_df)

    assert isinstance(quality_metrics, dict)
    for key in [
        "missingData",
        "missingPercentage",
        "outliers",
        "skewness",
        "lowVarianceFeatures",
    ]:
        assert key in quality_metrics

    assert quality_metrics["missingData"]["missing_values"] > 0
    assert quality_metrics["missingPercentage"]["missing_values"] > 0


def test_calculate_variable_insights(sample_df):
    """Variable insights flag high-cardinality columns and correlations."""
    insights = calculate_variable_insights(sample_df)

    assert isinstance(insights, dict)
    assert "highCardinality" in insights
    assert "correlatedFeatures" in insights
    assert "high_cardinality" in insights["highCardinality"]


def test_suggest_transformations(sample_df):
    """Transformation suggestions cover normalize/encode/drop buckets."""
    suggestions = suggest_transformations(sample_df)

    assert isinstance(suggestions, dict)
    assert all(k in suggestions for k in ["normalize", "encode", "drop"])

    # Skewed numeric -> normalize; categorical -> encode; unique id-like -> drop
    assert "numeric_skewed" in suggestions["normalize"]
    assert "category" in suggestions["encode"]
    assert "id" in suggestions["drop"]


def test_generate_grouped_insights(sample_df):
    """Grouped insights are produced for categorical columns."""
    grouped = generate_grouped_insights(sample_df)

    assert isinstance(grouped, dict)
    assert "category" in grouped
    assert isinstance(grouped["category"], dict)


def test_eda_summary_failure():
    """A download failure is returned as a failure envelope, not raised."""
    with patch(
        "mcp.tools.eda_summary.download_file_from_s3",
        side_effect=Exception("Download failed"),
    ):
        result = eda_summary(EdaInput(file_uri="s3://bucket/nonexistent.csv"))

    assert result["success"] is False
    assert "Download failed" in result["message"]
