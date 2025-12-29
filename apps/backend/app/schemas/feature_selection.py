"""
Pydantic schemas for Feature Selection API endpoints.

Defines request/response models for feature selection operations,
supporting multiple selection algorithms with importance scoring.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


# Enums for selection methods
SelectionMethod = Literal[
    "correlation",
    "mutual_info",
    "random_forest",
    "rfe",
    "lasso",
    "statistical"
]


class FeatureSelectionRequest(BaseModel):
    """Request schema for feature selection endpoint."""

    target_column: str = Field(
        ...,
        description="Name of the target column for supervised selection"
    )
    method: SelectionMethod = Field(
        ...,
        description="Feature selection algorithm to use"
    )
    top_k: Optional[int] = Field(
        None,
        ge=1,
        description="Number of top features to select (default: auto-determine)"
    )
    threshold: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Importance threshold for feature inclusion (0.0-1.0)"
    )
    correlation_threshold: Optional[float] = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Threshold for detecting redundant features (default: 0.7)"
    )
    problem_type: Optional[Literal["classification", "regression"]] = Field(
        None,
        description="Type of ML problem (auto-detected if not provided)"
    )
    algorithm_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Algorithm-specific parameters (e.g., n_estimators for Random Forest)"
    )
    sample_size: Optional[int] = Field(
        None,
        description="Sample size for large datasets (default: use full dataset)"
    )


class FeatureScore(BaseModel):
    """Feature with importance score."""

    feature_name: str = Field(..., description="Feature name")
    score: float = Field(..., description="Normalized importance score (0-1)")
    rank: int = Field(..., ge=1, description="Rank by importance (1=most important)")
    selected: bool = Field(..., description="Whether feature was selected")


class RedundantPair(BaseModel):
    """Pair of redundant features."""

    feature1: str = Field(..., description="First feature name")
    feature2: str = Field(..., description="Second feature name")
    correlation: float = Field(..., description="Correlation coefficient")
    recommendation: str = Field(
        ...,
        description="Recommendation for handling redundancy"
    )


class FeatureSelectionResult(BaseModel):
    """Response schema for feature selection endpoint."""

    dataset_id: str = Field(..., description="Dataset ID")
    method: SelectionMethod = Field(..., description="Selection method used")
    selected_features: List[str] = Field(
        ...,
        description="List of selected feature names"
    )
    feature_scores: List[FeatureScore] = Field(
        ...,
        description="All features with importance scores"
    )
    redundant_pairs: List[RedundantPair] = Field(
        default_factory=list,
        description="Pairs of highly correlated features"
    )
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = Field(
        None,
        description="Full correlation matrix for numeric features"
    )
    explanation: str = Field(
        ...,
        description="Human-readable explanation of selection results"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (problem_type, n_samples, etc.)"
    )
    execution_time_ms: float = Field(
        ...,
        description="Execution time in milliseconds"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of selection"
    )


class FeatureImportanceRequest(BaseModel):
    """Request schema for feature importance calculation."""

    target_column: str = Field(..., description="Target column name")
    method: SelectionMethod = Field(..., description="Importance calculation method")
    problem_type: Optional[Literal["classification", "regression"]] = None
    algorithm_params: Optional[Dict[str, Any]] = Field(default_factory=dict)


class FeatureImportanceResponse(BaseModel):
    """Response schema for feature importance calculation."""

    dataset_id: str = Field(..., description="Dataset ID")
    method: SelectionMethod = Field(..., description="Method used")
    feature_scores: List[FeatureScore] = Field(
        ...,
        description="Features ranked by importance"
    )
    execution_time_ms: float = Field(..., description="Execution time")


class RedundancyDetectionRequest(BaseModel):
    """Request schema for redundancy detection."""

    correlation_threshold: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Correlation threshold for redundancy"
    )
    method: Literal["pearson", "spearman", "kendall"] = Field(
        "pearson",
        description="Correlation method to use"
    )


class RedundancyDetectionResponse(BaseModel):
    """Response schema for redundancy detection."""

    dataset_id: str = Field(..., description="Dataset ID")
    redundant_pairs: List[RedundantPair] = Field(
        ...,
        description="Redundant feature pairs"
    )
    correlation_matrix: Dict[str, Dict[str, float]] = Field(
        ...,
        description="Full correlation matrix"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for handling redundancy"
    )


class MethodComparisonRequest(BaseModel):
    """Request schema for comparing selection methods."""

    target_column: str = Field(..., description="Target column name")
    methods: List[SelectionMethod] = Field(
        ...,
        min_length=2,
        max_length=6,
        description="Methods to compare (2-6)"
    )
    top_k: Optional[int] = Field(
        10,
        ge=1,
        description="Number of top features per method"
    )
    problem_type: Optional[Literal["classification", "regression"]] = None


class MethodComparisonResult(BaseModel):
    """Results for a single method in comparison."""

    method: SelectionMethod = Field(..., description="Selection method")
    selected_features: List[str] = Field(..., description="Selected features")
    top_features: List[FeatureScore] = Field(
        ...,
        description="Top features with scores"
    )
    execution_time_ms: float = Field(..., description="Execution time")


class MethodComparisonResponse(BaseModel):
    """Response schema for method comparison."""

    dataset_id: str = Field(..., description="Dataset ID")
    results: List[MethodComparisonResult] = Field(
        ...,
        description="Results for each method"
    )
    consensus_features: List[str] = Field(
        ...,
        description="Features selected by all methods"
    )
    overlap_matrix: Dict[str, Dict[str, int]] = Field(
        ...,
        description="Overlap count between methods"
    )
    recommendations: str = Field(
        ...,
        description="Recommendations based on comparison"
    )


class SelectedFeaturesResponse(BaseModel):
    """Response schema for retrieving previously selected features."""

    dataset_id: str = Field(..., description="Dataset ID")
    selected_features: List[str] = Field(
        default_factory=list,
        description="List of previously selected feature names"
    )
    has_selection: bool = Field(
        ...,
        description="Whether any features have been selected"
    )
