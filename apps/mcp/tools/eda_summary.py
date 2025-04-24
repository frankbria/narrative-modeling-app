# apps/mcp/tools/eda_summary.py

from pydantic import BaseModel
import logging
import pandas as pd
from typing import Any, Dict

from utils.s3_service import download_file_from_s3
from utils.numpy_json import convert_numpy_types

logger = logging.getLogger(__name__)


class EdaInput(BaseModel):
    file_uri: str


def eda_summary(params: EdaInput) -> dict:
    """Generate an EDA summary for a given CSV file stored at an S3 URI."""
    try:
        local_file_path = download_file_from_s3(params.file_uri)
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

        return {"success": True, "data": convert_numpy_types(result)}

    except Exception as e:
        logger.exception("Failed to run EDA summary tool")
        return {"success": False, "message": str(e)}


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
