"""Schemas for the error-analysis dashboard (issue #81).

Contract shared with the frontend: apps/frontend/lib/types/evaluation.ts mirrors
these models field-for-field. Change both together.

Error analysis reuses the held-out arrays persisted at training time (issue #79)
plus the held-out transformed feature matrix (``X_test`` + ``feature_names``,
added to the same ``evaluation_data.json`` for #81). Models trained before #81
lack ``X_test`` and degrade to ``partial=true`` (distribution / confusion pairs /
cases only — segments, clusters, and patterns need the feature matrix).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ErrorDistribution(BaseModel):
    """Overall and per-class error rates on the held-out set."""

    total_samples: int
    total_errors: int
    overall_error_rate: float
    # Classification: error rate among the actual members of each class.
    # Empty for regression.
    per_class_error_rate: dict[str, float] = Field(default_factory=dict)


class ConfusionPair(BaseModel):
    """A commonly-confused (actual, predicted) class pair. Classification only."""

    actual: str
    predicted: str
    count: int
    rate: float = Field(..., description="count / number of actual-class samples")


class ErrorSegment(BaseModel):
    """A feature value-range with a higher-than-overall error rate."""

    feature: str
    range_label: str
    lower: float | None
    upper: float | None
    error_rate: float
    error_count: int
    sample_count: int


class ErrorCluster(BaseModel):
    """A KMeans cluster of similar error cases (in engineered-feature space)."""

    cluster_id: int
    size: int
    characteristics: list[str] = Field(
        default_factory=list,
        description="Plain-language distinguishing traits, e.g. 'high age'",
    )
    dominant_confusion: str | None = Field(
        None, description="Most common 'actual→predicted' pair in the cluster"
    )


class ErrorPattern(BaseModel):
    """A decision-tree rule that isolates a high-error region of feature space."""

    rule: str = Field(..., description="e.g. 'age <= 25.00 AND income <= 30000.00'")
    error_rate: float
    error_count: int
    sample_count: int


class ErrorCase(BaseModel):
    """One misclassified / high-error held-out sample, for the case browser."""

    index: int
    actual: str
    predicted: str
    confidence: float | None = Field(
        None, description="Max predicted class probability; None without proba"
    )
    top_features: dict[str, float] = Field(
        default_factory=dict, description="A subset of engineered feature values"
    )


class ErrorAnalysisResponse(BaseModel):
    """Full error-analysis payload for one model (issue #81)."""

    model_id: str
    model_name: str | None = None
    algorithm: str | None = None
    problem_type: str
    partial: bool = Field(
        ...,
        description="True when artifacts are missing/incomplete (e.g. pre-#81 "
        "models without the feature matrix); analysis degrades, never 500s",
    )
    distribution: ErrorDistribution | None = None
    confusion_pairs: list[ConfusionPair] = Field(default_factory=list)
    segments: list[ErrorSegment] = Field(default_factory=list)
    clusters: list[ErrorCluster] = Field(default_factory=list)
    patterns: list[ErrorPattern] = Field(default_factory=list)
    cases: list[ErrorCase] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    suggestions_generated_by: Literal["openai", "fallback"] = "fallback"
    message: str | None = None
    evaluated_at: datetime
