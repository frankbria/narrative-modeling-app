"""Rule-based dataset analysis for ``POST /ai/analyze``.

Computed from the dataset's stored schema and quality report; it never calls a
model and never invents an insight (#539). It was the fallback behind an MCP server
that no environment ever ran, and became the only path when that was dropped (#508).
"""

from typing import Any

from pydantic import BaseModel

LOW_QUALITY_SCORE = 0.8
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


def _recommendations(quality_score: float | None, quality_report: dict[str, Any]) -> list[str]:
    recommendations = []
    if quality_score is not None and quality_score < LOW_QUALITY_SCORE:
        recommendations.append("Consider data cleaning to improve overall quality score")
    recommendations.extend((quality_report.get("recommendations") or [])[:QUALITY_REPORT_RECOMMENDATIONS])
    return list(dict.fromkeys(recommendations))


def _overview(row_count: int, column_count: int) -> dict[str, Any]:
    details = {"row_count": row_count, "column_count": column_count}
    description = f"Dataset has {row_count:,} rows and {column_count} columns."
    return {"type": "data_overview", "title": "Dataset Overview", "description": description, "details": details}


def _quality(quality_score: float) -> dict[str, Any]:
    description = f"Overall data quality score is {quality_score:.2f} (0-1 scale)."
    details = {"overall_quality_score": quality_score}
    return {"type": "data_quality", "title": "Data Quality", "description": description, "details": details}


def analyze_dataset(file_id: str, analysis_type: str, schema: dict[str, Any], quality_report: dict[str, Any]) -> DatasetAnalysisResponse:
    """Facts about the dataset, labelled as not AI via ``metadata.ai_used``.

    Processing stores explicit nulls (#981), so a null reads as missing.
    """
    # shortcut: one statement per line, because the CRAP gate cannot verify a multi-line Python statement from coverage.py's LCOV; fold back once the gate maps them.
    row_count, column_count = schema.get("row_count") or 0, schema.get("column_count") or 0
    insights = [_overview(row_count, column_count)]
    quality_score = quality_report.get("overall_quality_score")
    if quality_score is not None:
        insights.append(_quality(quality_score))
    summary = f"This is a rule-based summary computed directly from the dataset ({row_count:,} rows, {column_count} columns)."
    recommendations = _recommendations(quality_score, quality_report)
    response = {"summary": summary, "insights": insights, "recommendations": recommendations, "metadata": {"ai_used": False}}
    return DatasetAnalysisResponse(file_id=file_id, analysis_type=analysis_type, **response)
