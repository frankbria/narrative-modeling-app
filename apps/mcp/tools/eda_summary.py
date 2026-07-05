# apps/mcp/tools/eda_summary.py

from pydantic import BaseModel, Field
import asyncio
import logging
import os
import pandas as pd
from typing import Any, Dict

from models.user_data import UserData
from utils.s3_service import download_dataset_file
from utils.user_data import get_user_data_by_id
from utils.numpy_json import convert_numpy_types

logger = logging.getLogger(__name__)

# Single generic message for missing datasets AND ownership failures, so a caller
# can't distinguish "not found" from "not yours" (avoids tenant enumeration).
_ACCESS_DENIED = "Dataset not found or access denied"


class EdaInput(BaseModel):
    dataset_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)


def authorize_dataset(user_data: UserData | None, requested_user_id: str) -> str:
    """Return the dataset's server-stored S3 URL iff the caller owns it.

    Raises PermissionError (with a generic message) when the dataset is missing
    or owned by someone else. Pure/sync so it is fully unit-testable.
    """
    if user_data is None or user_data.user_id != requested_user_id:
        raise PermissionError(_ACCESS_DENIED)
    return user_data.s3_url


async def run_eda_summary(params: EdaInput) -> dict:
    """Generate an EDA summary for a dataset the caller owns.

    The S3 key is derived server-side from the dataset record — never from the
    caller — so an untrusted caller cannot read arbitrary S3 objects.
    """
    try:
        user_data = await get_user_data_by_id(params.dataset_id)
        s3_url = authorize_dataset(user_data, params.user_id)
    except PermissionError as e:
        return {"success": False, "message": str(e)}

    try:
        # Offload the whole blocking pipeline (download → read → analyze →
        # delete) to a single worker thread. Cleanup lives *inside* the thread:
        # asyncio.to_thread can't cancel the thread, so a cancelled/timed-out
        # request would run the coroutine's finally with no path to clean up
        # while the thread finished the download — leaking the dataset on disk.
        data = await asyncio.to_thread(_download_and_summarize, s3_url)
        return {"success": True, "data": data}

    except Exception:
        # Generic message: never leak S3/parse internals to the caller.
        logger.exception("Failed to run EDA summary tool")
        return {"success": False, "message": "Failed to generate EDA summary"}


def _download_and_summarize(s3_url: str) -> dict:
    """Download, summarize, and always delete the temp file (blocking).

    Runs in a worker thread; the `finally` guarantees the downloaded dataset is
    removed regardless of the awaiting request's fate (success or cancellation).
    """
    local_file_path = download_dataset_file(s3_url)
    try:
        return _build_summary(local_file_path)
    finally:
        try:
            os.remove(local_file_path)
        except OSError:
            pass


def _build_summary(local_file_path: str) -> dict:
    """Read the CSV and compute the EDA summary (blocking)."""
    df = pd.read_csv(local_file_path)
    result = {
        "overview": {
            "shape": list(df.shape),
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
        },
        "dataQuality": calculate_data_quality(df),
        "variableInsights": calculate_variable_insights(df),
        "transformations": suggest_transformations(df),
        "groupedInsights": generate_grouped_insights(df),
    }
    return convert_numpy_types(result)


def calculate_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
    missing_data = df.isnull().sum().sort_values(ascending=False).to_dict()
    missing_percentage = (df.isnull().mean() * 100).round(2).to_dict()

    numeric_cols = df.select_dtypes(include=["number"])
    outliers = {}
    for col in numeric_cols.columns:
        Q1 = numeric_cols[col].quantile(0.25)
        Q3 = numeric_cols[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        outliers[col] = (
            (numeric_cols[col] < lower_bound) | (numeric_cols[col] > upper_bound)
        ).sum()

    skewness = df.skew(numeric_only=True).round(2).to_dict()
    low_variance = df.std(numeric_only=True)[
        df.std(numeric_only=True) < 1e-5
    ].index.tolist()

    return convert_numpy_types(
        {
            "missingData": missing_data,
            "missingPercentage": missing_percentage,
            "outliers": outliers,
            "skewness": skewness,
            "lowVarianceFeatures": low_variance,
        }
    )


def calculate_variable_insights(df: pd.DataFrame) -> Dict[str, Any]:
    high_card = df.nunique()[df.nunique() > 50].sort_values(ascending=False).to_dict()
    correlated = (
        df.corr(numeric_only=True)
        .abs()
        .unstack()
        .sort_values(ascending=False)
        .drop_duplicates()
    )
    correlated = (
        correlated.loc[(correlated < 1) & (correlated > 0.8)].head(10).to_dict()
    )

    return convert_numpy_types(
        {
            "highCardinality": high_card,
            "correlatedFeatures": correlated,
        }
    )


def suggest_transformations(df: pd.DataFrame) -> Dict[str, Any]:
    log_candidates = df.skew(numeric_only=True)
    log_transforms = log_candidates[log_candidates > 1].index.tolist()
    encode_candidates = df.select_dtypes(include="object").columns.tolist()
    id_like = [col for col in df.columns if df[col].is_unique and "id" in col.lower()]

    return {
        "normalize": log_transforms,
        "encode": encode_candidates,
        "drop": id_like,
    }


def generate_grouped_insights(df: pd.DataFrame) -> Dict[str, Any]:
    insights = {}
    for col in df.select_dtypes(include="object").columns:
        try:
            insights[col] = df.groupby(col).mean(numeric_only=True).describe().to_dict()
        except Exception as e:
            logger.warning(f"Error generating grouped insights for {col}: {e}")

    return convert_numpy_types(insights)
