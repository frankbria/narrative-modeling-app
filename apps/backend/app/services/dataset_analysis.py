"""Rule-based dataset analysis for ``POST /ai/analyze``.

Computed from the dataset's stored schema and quality report; it never calls a
model and never invents an insight (#539). It was the fallback behind an MCP server
that no environment ever ran, and became the only path when that was dropped (#508).
"""

from typing import Any

from pydantic import BaseModel

LOW_QUALITY_SCORE = 0.8
MAX_RECOMMENDATIONS = 5
QUALITY_REPORT_RECOMMENDATIONS = 3


class DatasetAnalysisResponse(BaseModel):
    """The analysis of one dataset."""

    file_id: str
    analysis_type: str
    summary: str
    insights: list[dict[str, Any]]
    recommendations: list[str]
    visualizations: list[dict[str, Any]] | None = None
    metadata: dict[str, Any]


def _recommendations(quality_report: dict[str, Any]) -> list[str]:
    recommendations = []
    if quality_report.get("overall_quality_score", 1.0) < LOW_QUALITY_SCORE:
        recommendations.append("Consider data cleaning to improve overall quality score")
    recommendations.extend(quality_report.get("recommendations", [])[:QUALITY_REPORT_RECOMMENDATIONS])
    return list(dict.fromkeys(recommendations))[:MAX_RECOMMENDATIONS]


def analyze_dataset(
    file_id: str,
    analysis_type: str,
    schema: dict[str, Any],
    quality_report: dict[str, Any],
) -> DatasetAnalysisResponse:
    """Facts about the dataset, labelled as not AI via ``metadata.ai_used``."""
    row_count = schema.get("row_count", 0)
    column_count = schema.get("column_count", 0)
    insights: list[dict[str, Any]] = [
        {
            "type": "data_overview",
            "title": "Dataset Overview",
            "description": f"Dataset has {row_count:,} rows and {column_count} columns.",
            "details": {"row_count": row_count, "column_count": column_count},
        }
    ]
    quality_score = quality_report.get("overall_quality_score")
    if quality_score is not None:
        insights.append(
            {
                "type": "data_quality",
                "title": "Data Quality",
                "description": f"Overall data quality score is {quality_score:.2f} (0-1 scale).",
                "details": {"overall_quality_score": quality_score},
            }
        )
    return DatasetAnalysisResponse(
        file_id=file_id,
        analysis_type=analysis_type,
        summary=(
            "This is a rule-based summary computed directly from the dataset "
            f"({row_count:,} rows, {column_count} columns)."
        ),
        insights=insights,
        recommendations=_recommendations(quality_report),
        metadata={"ai_used": False},
    )
