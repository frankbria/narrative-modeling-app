import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from mcp.tools.eda_summary import EdaSummaryTool


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "id": range(1, 101),
            "numeric_normal": np.random.normal(0, 1, 100),
            "numeric_skewed": np.exp(np.random.normal(0, 1, 100)),
            "category": np.random.choice(["A", "B", "C"], 100),
            "high_cardinality": [f"val_{i}" for i in range(100)],
            "missing_values": np.where(
                np.random.random(100) > 0.8, np.nan, np.random.random(100)
            ),
        }
    )


@pytest.fixture
def eda_tool():
    """Create an instance of EdaSummaryTool."""
    return EdaSummaryTool()


def test_run_success(eda_tool, sample_df):
    """Test successful execution of the EDA tool."""
    with patch("mcp.tools.eda_summary.download_file_from_s3") as mock_download:
        # Mock the S3 download to return a temporary CSV
        mock_download.return_value = "temp.csv"
        with patch("pandas.read_csv", return_value=sample_df):
            result = eda_tool.run("s3://bucket/file.csv")

            assert result.success is True
            assert isinstance(result.data, dict)
            assert all(
                k in result.data
                for k in [
                    "overview",
                    "dataQuality",
                    "variableInsights",
                    "transformations",
                    "groupedInsights",
                ]
            )


def test_calculate_data_quality(eda_tool, sample_df):
    """Test data quality calculations."""
    quality_metrics = eda_tool.calculate_data_quality(sample_df)

    assert isinstance(quality_metrics, dict)
    assert "missingData" in quality_metrics
    assert "missingPercentage" in quality_metrics
    assert "outliers" in quality_metrics
    assert "skewness" in quality_metrics
    assert "lowVarianceFeatures" in quality_metrics

    # Check missing values detection
    assert quality_metrics["missingData"]["missing_values"] > 0
    assert quality_metrics["missingPercentage"]["missing_values"] > 0


def test_calculate_variable_insights(eda_tool, sample_df):
    """Test variable insights calculations."""
    insights = eda_tool.calculate_variable_insights(sample_df)

    assert isinstance(insights, dict)
    assert "highCardinality" in insights
    assert "correlatedFeatures" in insights

    # Check high cardinality detection
    assert "high_cardinality" in insights["highCardinality"]


def test_suggest_transformations(eda_tool, sample_df):
    """Test transformation suggestions."""
    suggestions = eda_tool.suggest_transformations(sample_df)

    assert isinstance(suggestions, dict)
    assert all(k in suggestions for k in ["normalize", "encode", "drop"])

    # Check if skewed column is suggested for normalization
    assert "numeric_skewed" in suggestions["normalize"]
    # Check if categorical columns are suggested for encoding
    assert "category" in suggestions["encode"]
    # Check if ID column is suggested for dropping
    assert "id" in suggestions["drop"]


def test_generate_grouped_insights(eda_tool, sample_df):
    """Test grouped insights generation."""
    grouped = eda_tool.generate_grouped_insights(sample_df)

    assert isinstance(grouped, dict)
    assert "category" in grouped  # Should have insights for categorical column
    assert isinstance(grouped["category"], dict)


def test_run_failure(eda_tool):
    """Test error handling in run method."""
    with patch(
        "mcp.tools.eda_summary.download_file_from_s3",
        side_effect=Exception("Download failed"),
    ):
        result = eda_tool.run("s3://bucket/nonexistent.csv")

        assert result.success is False
        assert "Download failed" in result.message
