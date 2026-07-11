"""
Pydantic schemas for Feature Engineering API endpoints.

These schemas define request/response models for AI-powered feature suggestion
and engineering operations.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FeatureType(str, Enum):
    """Types of features that can be suggested"""
    POLYNOMIAL = "polynomial"
    INTERACTION = "interaction"
    AGGREGATION = "aggregation"
    TIME_BASED = "time_based"
    TEXT = "text"
    BINNING = "binning"
    ENCODING = "encoding"
    SCALING = "scaling"
    MATHEMATICAL = "mathematical"
    DOMAIN_SPECIFIC = "domain_specific"


class ComputationCost(str, Enum):
    """Estimated computation cost for a feature"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FeatureSuggestion(BaseModel):
    """A single feature suggestion with metadata"""

    id: str = Field(..., description="Unique suggestion identifier")
    name: str = Field(..., description="Feature name")
    description: str = Field(..., description="Human-readable description of the feature")
    feature_type: FeatureType = Field(..., description="Type of feature transformation")
    formula: str | None = Field(None, description="Mathematical formula or logic for the feature")
    expected_importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Expected importance score (0-1)"
    )
    explanation: str = Field(..., description="Why this feature might be useful")
    computation_cost: ComputationCost = Field(
        default=ComputationCost.LOW,
        description="Estimated computation cost"
    )
    input_columns: list[str] = Field(
        default_factory=list,
        description="Source columns required for this feature"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Feature-specific parameters"
    )
    source: str = Field(
        default="rule_based",
        description="Source of suggestion: 'rule_based' or 'ai'"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "feat_poly_001",
                "name": "age_squared",
                "description": "Square of the age column for polynomial regression",
                "feature_type": "polynomial",
                "formula": "age ** 2",
                "expected_importance": 0.75,
                "explanation": "Polynomial features can capture non-linear relationships. Age often has diminishing or accelerating effects.",
                "computation_cost": "low",
                "input_columns": ["age"],
                "parameters": {"power": 2},
                "source": "rule_based"
            }
        }
    }


class FeatureSuggestionRequest(BaseModel):
    """Request model for generating feature suggestions"""

    target_column: str | None = Field(
        None,
        description="Target column for ML task (optional, auto-detected if not provided)"
    )
    problem_type: str | None = Field(
        None,
        description="ML problem type (auto-detected if not provided)"
    )
    max_suggestions: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of suggestions to return"
    )
    include_ai_suggestions: bool = Field(
        default=True,
        description="Whether to include AI-generated suggestions"
    )
    feature_types: list[FeatureType] | None = Field(
        None,
        description="Filter suggestions by feature types (all types if not specified)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "target_column": "price",
                "problem_type": "regression",
                "max_suggestions": 15,
                "include_ai_suggestions": True,
                "feature_types": ["polynomial", "interaction"]
            }
        }
    }


class FeatureSuggestionResponse(BaseModel):
    """Response model for feature suggestions"""

    dataset_id: str = Field(..., description="Dataset identifier")
    suggestions: list[FeatureSuggestion] = Field(
        default_factory=list,
        description="List of feature suggestions"
    )
    detected_problem_type: str | None = Field(
        None,
        description="Auto-detected problem type"
    )
    detected_target_column: str | None = Field(
        None,
        description="Auto-detected or specified target column"
    )
    detected_domain: str | None = Field(
        None,
        description="Auto-detected data domain (e.g., 'financial', 'healthcare')"
    )
    total_suggestions: int = Field(..., ge=0, description="Total number of suggestions")
    rule_based_count: int = Field(default=0, ge=0, description="Number of rule-based suggestions")
    ai_count: int = Field(default=0, ge=0, description="Number of AI-generated suggestions")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the suggestions"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of suggestion generation"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "dataset_id": "dataset_abc123",
                "suggestions": [],
                "detected_problem_type": "regression",
                "detected_target_column": "price",
                "detected_domain": "real_estate",
                "total_suggestions": 15,
                "rule_based_count": 10,
                "ai_count": 5,
                "metadata": {"processing_time_ms": 1250},
                "generated_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class FeatureFeedbackRequest(BaseModel):
    """Request model for recording user feedback on a suggestion"""

    accepted: bool = Field(..., description="Whether the suggestion was accepted")
    modified_parameters: dict[str, Any] | None = Field(
        None,
        description="Modified parameters if user customized the suggestion"
    )
    reason: str | None = Field(
        None,
        max_length=500,
        description="Optional reason for rejection"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "accepted": True,
                "modified_parameters": {"power": 3},
                "reason": None
            }
        }
    }


class FeatureFeedbackResponse(BaseModel):
    """Response model for feedback submission"""

    suggestion_id: str = Field(..., description="Suggestion identifier")
    accepted: bool = Field(..., description="Whether accepted")
    recorded_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Feedback timestamp"
    )
    message: str = Field(..., description="Status message")


class GenerateMoreRequest(BaseModel):
    """Request model for generating additional suggestions"""

    excluded_suggestion_ids: list[str] = Field(
        default_factory=list,
        description="IDs of suggestions to exclude"
    )
    target_column: str | None = Field(
        None,
        description="Target column"
    )
    problem_type: str | None = Field(
        None,
        description="Problem type"
    )
    count: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Number of additional suggestions"
    )
    prefer_feature_types: list[FeatureType] | None = Field(
        None,
        description="Preferred feature types for new suggestions"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "excluded_suggestion_ids": ["feat_001", "feat_002"],
                "target_column": "price",
                "problem_type": "regression",
                "count": 10,
                "prefer_feature_types": ["interaction", "aggregation"]
            }
        }
    }


class ApplyFeatureRequest(BaseModel):
    """Request model for applying a feature suggestion"""

    suggestion_id: str = Field(..., description="Suggestion to apply")
    parameters: dict[str, Any] | None = Field(
        None,
        description="Override parameters"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "suggestion_id": "feat_poly_001",
                "parameters": {"power": 2}
            }
        }
    }


class ApplyMultipleFeaturesRequest(BaseModel):
    """Request model for applying multiple feature suggestions"""

    suggestion_ids: list[str] = Field(
        ...,
        min_length=1,
        description="List of suggestion IDs to apply"
    )
    parameter_overrides: dict[str, dict[str, Any]] | None = Field(
        None,
        description="Parameter overrides per suggestion ID"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "suggestion_ids": ["feat_001", "feat_002", "feat_003"],
                "parameter_overrides": {
                    "feat_001": {"power": 3}
                }
            }
        }
    }


class ApplyFeatureResponse(BaseModel):
    """Response model for feature application.

    Note (#274): these endpoints compute a *preview* of the engineered
    column(s) and never persist them to the stored dataset — ``persisted`` is
    always ``False``. To make the change stick, run the transformation pipeline
    (``/transformations``) which versions and saves the result.
    """

    dataset_id: str = Field(..., description="Dataset identifier")
    persisted: bool = Field(
        default=False,
        description="Whether the new columns were saved to the dataset. "
                    "Always False — this endpoint is preview-only (#274)."
    )
    applied_features: list[str] = Field(
        default_factory=list,
        description="Names of features successfully computed in the preview"
    )
    failed_features: list[dict[str, str]] = Field(
        default_factory=list,
        description="Features that failed with error messages"
    )
    new_column_count: int = Field(..., ge=0, description="Number of new columns previewed")
    preview_data: list[dict[str, Any]] | None = Field(
        None,
        description="Preview of data with new features (not persisted)"
    )
    message: str = Field(..., description="Status message")


class FeatureExplanationResponse(BaseModel):
    """Detailed explanation of a feature suggestion"""

    suggestion_id: str = Field(..., description="Suggestion identifier")
    name: str = Field(..., description="Feature name")
    detailed_explanation: str = Field(..., description="Detailed explanation in markdown")
    example_calculations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Example calculations showing input/output"
    )
    similar_features: list[str] = Field(
        default_factory=list,
        description="Names of similar features"
    )
    use_cases: list[str] = Field(
        default_factory=list,
        description="Common use cases for this feature type"
    )
    considerations: list[str] = Field(
        default_factory=list,
        description="Important considerations when using this feature"
    )


class FeatureFeedbackRecord(BaseModel):
    """MongoDB document schema for feature feedback storage"""

    feedback_id: str = Field(..., description="Unique feedback identifier")
    suggestion_id: str = Field(..., description="Suggestion identifier")
    user_id: str = Field(..., description="User who provided feedback")
    dataset_id: str = Field(..., description="Dataset identifier")
    feature_type: FeatureType = Field(..., description="Type of feature")
    accepted: bool = Field(..., description="Whether accepted")
    modified_parameters: dict[str, Any] | None = None
    reason: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "json_schema_extra": {
            "example": {
                "feedback_id": "fb_001",
                "suggestion_id": "feat_001",
                "user_id": "user_123",
                "dataset_id": "dataset_abc",
                "feature_type": "polynomial",
                "accepted": True,
                "modified_parameters": None,
                "reason": None,
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    }
