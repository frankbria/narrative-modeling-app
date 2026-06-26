"""Schemas for the AI orchestration / decision engine (issue #89).

Request/response contracts for AI-guided tool selection, parameter optimization,
and recommendation feedback. Mirrors the `source` ("rule_based" vs "ai") field
convention from `FeatureSuggestion` so the UI can show recommendation provenance.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Objective(str, Enum):
    """What the user is trying to accomplish at this workflow stage."""

    DATA_CLEANING = "data_cleaning"
    FEATURE_ENGINEERING = "feature_engineering"
    MODELING = "modeling"
    EXPLORATION = "exploration"


class ToolConstraints(BaseModel):
    """Optional preferences that bias the recommendations."""

    time_budget: str | None = Field(
        None, description="Rough time budget hint, e.g. 'fast' or 'thorough'"
    )
    interpretability_preference: str | None = Field(
        None, description="'high' to favour interpretable tools, 'low' to favour accuracy"
    )


class ToolRecommendation(BaseModel):
    """A single recommended tool/transformation with rationale."""

    recommendation_id: str = Field(..., description="Stable id for feedback linkage")
    tool_type: str = Field(
        ..., description="Tool identifier (aligned with TransformationType where applicable)"
    )
    priority: int = Field(..., ge=1, le=10, description="Higher is more strongly recommended")
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str = Field(..., description="Plain-language reason for the recommendation")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Suggested default params")
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    estimated_impact: str = Field(default="", description="Plain-language expected impact")
    source: str = Field(default="rule_based", description="'rule_based' or 'ai'")


class ToolRecommendationRequest(BaseModel):
    """Request for tool recommendations for a dataset + objective."""

    dataset_id: str
    objective: Objective
    constraints: ToolConstraints | None = None
    context: dict[str, Any] | None = Field(
        None, description="Optional context: previous_steps, user_preferences"
    )


class ToolRecommendationResponse(BaseModel):
    """Ranked recommendations plus an ordered multi-stage pipeline suggestion."""

    dataset_id: str
    objective: Objective
    recommendations: list[ToolRecommendation]
    pipeline_suggestion: list[str] = Field(
        default_factory=list, description="tool_types in suggested execution order"
    )
    data_profile_summary: str = ""
    reasoning_trace: list[str] = Field(default_factory=list)
    personalization_applied: bool = False
    generated_by: str = Field(default="rule_based", description="'rule_based' or 'hybrid'")
    partial: bool = Field(
        default=False, description="True when the dataset lacks full profiling metadata"
    )


class ParameterOptimizationRequest(BaseModel):
    """Request for optimized parameters for a specific tool on a dataset."""

    dataset_id: str
    tool_type: str
    current_parameters: dict[str, Any] = Field(default_factory=dict)
    optimization_goal: str | None = None


class ParameterAlternative(BaseModel):
    """An alternative parameter set the user could choose instead."""

    parameters: dict[str, Any]
    explanation: str
    expected_improvement: str = ""


class ParameterOptimizationResponse(BaseModel):
    """Optimized parameters with explanation and ranked alternatives."""

    dataset_id: str
    tool_type: str
    optimized_parameters: dict[str, Any]
    expected_improvement: str = ""
    explanation: str = ""
    alternatives: list[ParameterAlternative] = Field(default_factory=list)
    generated_by: str = Field(default="rule_based", description="'rule_based' or 'hybrid'")
    partial: bool = False


class FeedbackAction(str, Enum):
    """How the user reacted to a recommendation."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


class AIFeedbackRequest(BaseModel):
    """User feedback on a single recommendation (drives personalization)."""

    recommendation_id: str
    tool_type: str
    action: FeedbackAction
    dataset_id: str | None = None
    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = Field(None, max_length=2000)
    modification: dict[str, Any] | None = None


class AIFeedbackResponse(BaseModel):
    """Confirmation of stored feedback."""

    feedback_id: str
    recommendation_id: str
    tool_type: str
    action: FeedbackAction
    created_at: str
