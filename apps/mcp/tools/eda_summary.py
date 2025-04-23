from fastmcp import BaseTool, ToolResult
from typing import Any, Dict
import asyncio
import logging
import pandas as pd

from utils.user_data import get_user_data_by_id
from utils.s3_service import download_file_from_s3
from utils.numpy_json import convert_numpy_types

logger = logging.getLogger(__name__)


class EdaSummaryTool(BaseTool):
    name = "eda_summary"
    description = "Generate an EDA summary for a given dataset_id"
    parameters = {
        "dataset_id": {
            "type": "string",
            "description": "The ID of the dataset to analyze",
            "required": True,
        }
    }

    def run(self, dataset_id: str, **kwargs: Any) -> ToolResult:
        try:
            user_data = asyncio.run(get_user_data_by_id(dataset_id))
            if not user_data:
                return ToolResult(
                    success=False, message=f"No dataset found for ID: {dataset_id}"
                )

            local_file_path = download_file_from_s3(user_data.s3_url)
            df = pd.read_csv(local_file_path)

            eda_summary = {
                "overview": {
                    "filename": user_data.filename,
                    "shape": list(df.shape),
                    "columns": df.columns.tolist(),
                    "dtypes": df.dtypes.astype(str).to_dict(),
                },
                "dataQuality": self.calculate_data_quality(df),
                "variableInsights": self.calculate_variable_insights(df),
                "transformations": self.suggest_transformations(df),
                "groupedInsights": self.generate_grouped_insights(df),
            }

            return ToolResult(success=True, data=convert_numpy_types(eda_summary))

        except Exception as e:
            logger.exception("Failed to run EDA summary tool")
            return ToolResult(success=False, message=str(e))

    def calculate_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
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

    def calculate_variable_insights(self, df: pd.DataFrame) -> Dict[str, Any]:
        high_card = (
            df.nunique()[df.nunique() > 50].sort_values(ascending=False).to_dict()
        )
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

    def suggest_transformations(self, df: pd.DataFrame) -> Dict[str, Any]:
        log_candidates = df.skew(numeric_only=True)
        log_transforms = log_candidates[log_candidates > 1].index.tolist()
        encode_candidates = df.select_dtypes(include="object").columns.tolist()
        id_like = [
            col for col in df.columns if df[col].is_unique and "id" in col.lower()
        ]

        return {
            "normalize": log_transforms,
            "encode": encode_candidates,
            "drop": id_like,
        }

    def generate_grouped_insights(self, df: pd.DataFrame) -> Dict[str, Any]:
        insights = {}
        for col in df.select_dtypes(include="object").columns:
            try:
                insights[col] = (
                    df.groupby(col).mean(numeric_only=True).describe().to_dict()
                )
            except Exception as e:
                logger.warning(f"Error generating grouped insights for {col}: {e}")

        return convert_numpy_types(insights)
