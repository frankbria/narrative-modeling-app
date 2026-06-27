"""Schemas for the data quality scoring system (issue #102).

Mirrored by the frontend in apps/frontend/lib/types/quality.ts — change both together.
"""

from pydantic import BaseModel, Field

from app.services.data_processing.quality_assessment import ActionableRecommendation


class QualityGateResult(BaseModel):
    """Result of evaluating one soft quality gate (issue #102, AC4)."""

    gate_name: str
    passed: bool
    actual_score: float = Field(..., description="0-100 overall score evaluated")
    required_score: float = Field(..., description="0-100 minimum overall score")
    failing_dimensions: list[str] = Field(
        default_factory=list, description="Dimensions below their threshold"
    )
    is_blocking: bool = Field(
        False, description="Soft gates never block workflow progression"
    )


class QualityReportResponse(BaseModel):
    """Consolidated quality report for a dataset (issue #102, AC5)."""

    file_id: str
    filename: str | None = None
    score_0_100: float
    component_scores: dict[str, float] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    actionable_recommendations: list[ActionableRecommendation] = Field(default_factory=list)
    gates: list[QualityGateResult] = Field(default_factory=list)
    critical_issue_count: int = 0
    warning_count: int = 0
    partial: bool = Field(
        False, description="True when computed from a pre-#102 cached report"
    )
