from typing import Dict, Any
from app.models.user_data import UserData
from app.services.s3_service import download_file_from_s3
import logging
import pandas as pd
import numpy as np


logger = logging.getLogger(__name__)


def convert_numpy_types(obj):
    """
    Convert NumPy types to Python native types for JSON serialization.
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj


def calculate_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
    # Calculate missing data
    missing_data = df.isnull().sum().sort_values(ascending=False).to_dict()

    # Calculate missing percentage
    missing_percentage = (df.isnull().mean() * 100).round(2).to_dict()

    # Calculate outliers using IQR method
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

    # Calculate skewness
    skewness = df.skew(numeric_only=True).round(2).to_dict()

    # Find low variance features
    low_variance = df.std(numeric_only=True)[
        df.std(numeric_only=True) < 1e-5
    ].index.tolist()

    result = {
        "missingData": missing_data,
        "missingPercentage": missing_percentage,
        "outliers": outliers,
        "skewness": skewness,
        "lowVarianceFeatures": low_variance,
    }

    # Convert NumPy types to Python native types
    return convert_numpy_types(result)


def calculate_variable_insights(df: pd.DataFrame) -> Dict[str, Any]:
    result = {
        "highCardinality": df.nunique()[df.nunique() > 50]
        .sort_values(ascending=False)
        .to_dict(),
        "correlatedFeatures": df.corr(numeric_only=True)
        .abs()
        .unstack()
        .sort_values(ascending=False)
        .drop_duplicates()
        .loc[lambda x: (x < 1) & (x > 0.8)]
        .head(10)
        .to_dict(),
    }

    # Convert NumPy types to Python native types
    return convert_numpy_types(result)


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
        insights[col] = df.groupby(col).mean(numeric_only=True).describe().to_dict()

    # Convert NumPy types to Python native types
    return convert_numpy_types(insights)


async def generate_eda_summary(user_data: UserData) -> Dict[str, Any]:
    local_file_path = download_file_from_s3(user_data.s3_url)
    df = pd.read_csv(local_file_path)

    eda_summary = {
        "overview": {
            "filename": user_data.filename,
            "shape": list(df.shape),  # Convert tuple to list
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
        },
        "dataQuality": calculate_data_quality(df),
        "variableInsights": calculate_variable_insights(df),
        "transformations": suggest_transformations(df),
        "groupedInsights": generate_grouped_insights(df),
    }

    return eda_summary
