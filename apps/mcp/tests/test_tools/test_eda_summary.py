import types
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from mcp.tools.eda_summary import (
    EdaInput,
    authorize_dataset,
    calculate_data_quality,
    calculate_variable_insights,
    generate_grouped_insights,
    run_eda_summary,
    suggest_transformations,
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


def _owned(user_id="user-1", s3_url="s3://app-bucket/data/file.csv"):
    """A stand-in UserData record (authorize_dataset only reads attributes)."""
    return types.SimpleNamespace(user_id=user_id, s3_url=s3_url)


# --- Ownership authorization (pure) -----------------------------------------

def test_authorize_dataset_returns_s3_url_for_owner():
    url = authorize_dataset(_owned(user_id="user-1"), "user-1")
    assert url == "s3://app-bucket/data/file.csv"


def test_authorize_dataset_denies_missing_dataset():
    with pytest.raises(PermissionError):
        authorize_dataset(None, "user-1")


def test_authorize_dataset_denies_foreign_owner():
    with pytest.raises(PermissionError):
        authorize_dataset(_owned(user_id="owner"), "attacker")


def test_authorize_dataset_error_is_generic_for_missing_and_foreign():
    """Missing and not-yours must produce the SAME message (no enumeration)."""
    missing = foreign = None
    try:
        authorize_dataset(None, "user-1")
    except PermissionError as e:
        missing = str(e)
    try:
        authorize_dataset(_owned(user_id="owner"), "attacker")
    except PermissionError as e:
        foreign = str(e)
    assert missing == foreign


# --- Tool end-to-end (async) ------------------------------------------------

async def test_run_eda_summary_success_for_owner(sample_df):
    """Owner gets a success envelope; the S3 key is derived from the record."""
    with patch(
        "mcp.tools.eda_summary.get_user_data_by_id",
        new=AsyncMock(return_value=_owned(user_id="user-1")),
    ), patch(
        "mcp.tools.eda_summary.download_dataset_file", return_value="temp.csv"
    ) as mock_dl, patch("pandas.read_csv", return_value=sample_df):
        result = await run_eda_summary(
            EdaInput(dataset_id="abc", user_id="user-1")
        )

    assert result["success"] is True
    assert set(result["data"]) >= {
        "overview",
        "dataQuality",
        "variableInsights",
        "transformations",
        "groupedInsights",
    }
    # Downloaded the DB-sourced URL, never a caller-supplied one.
    mock_dl.assert_called_once_with("s3://app-bucket/data/file.csv")


async def test_run_eda_summary_denied_for_foreign_dataset(sample_df):
    """A dataset owned by someone else is refused and never downloaded."""
    with patch(
        "mcp.tools.eda_summary.get_user_data_by_id",
        new=AsyncMock(return_value=_owned(user_id="owner")),
    ), patch("mcp.tools.eda_summary.download_dataset_file") as mock_dl:
        result = await run_eda_summary(
            EdaInput(dataset_id="abc", user_id="attacker")
        )

    assert result["success"] is False
    assert result["message"] == "Dataset not found or access denied"
    mock_dl.assert_not_called()


async def test_run_eda_summary_denied_for_missing_dataset():
    with patch(
        "mcp.tools.eda_summary.get_user_data_by_id",
        new=AsyncMock(return_value=None),
    ), patch("mcp.tools.eda_summary.download_dataset_file") as mock_dl:
        result = await run_eda_summary(
            EdaInput(dataset_id="missing", user_id="user-1")
        )

    assert result["success"] is False
    assert result["message"] == "Dataset not found or access denied"
    mock_dl.assert_not_called()


async def test_run_eda_summary_download_failure_is_generic():
    """S3 internals must not leak in the caller-facing message."""
    with patch(
        "mcp.tools.eda_summary.get_user_data_by_id",
        new=AsyncMock(return_value=_owned(user_id="user-1")),
    ), patch(
        "mcp.tools.eda_summary.download_dataset_file",
        side_effect=RuntimeError("AccessDenied: arn:aws:s3:::secret/creds"),
    ):
        result = await run_eda_summary(
            EdaInput(dataset_id="abc", user_id="user-1")
        )

    assert result["success"] is False
    assert result["message"] == "Failed to generate EDA summary"
    assert "AccessDenied" not in result["message"]


# --- Pure analysis helpers (unchanged behavior) -----------------------------

def test_calculate_data_quality(sample_df):
    quality_metrics = calculate_data_quality(sample_df)
    for key in [
        "missingData",
        "missingPercentage",
        "outliers",
        "skewness",
        "lowVarianceFeatures",
    ]:
        assert key in quality_metrics
    assert quality_metrics["missingData"]["missing_values"] > 0


def test_calculate_variable_insights(sample_df):
    insights = calculate_variable_insights(sample_df)
    assert "highCardinality" in insights
    assert "correlatedFeatures" in insights
    assert "high_cardinality" in insights["highCardinality"]


def test_suggest_transformations(sample_df):
    suggestions = suggest_transformations(sample_df)
    assert all(k in suggestions for k in ["normalize", "encode", "drop"])
    assert "numeric_skewed" in suggestions["normalize"]
    assert "category" in suggestions["encode"]
    assert "id" in suggestions["drop"]


def test_generate_grouped_insights(sample_df):
    grouped = generate_grouped_insights(sample_df)
    assert "category" in grouped
    assert isinstance(grouped["category"], dict)
