"""
Pydantic schemas for Feature Builder API endpoints.

These schemas define request/response models for feature creation,
preview, validation, and management operations.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Import enums from models
from app.models.feature import (
    NodeType,
    OutputType,
)

# =============================================================================
# Expression Node Schemas
# =============================================================================


class ExpressionNodeRequest(BaseModel):
    """Request schema for expression node."""

    node_id: str = Field(..., description="Unique identifier for this node")
    node_type: str = Field(..., description="Type: column, operation, function, constant, conditional")
    value: str | float | int | bool | None = Field(None, description="Node value")
    children: list["ExpressionNodeRequest"] = Field(default_factory=list, description="Child nodes")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Additional parameters")
    position: dict[str, float] | None = Field(None, description="Visual position {x, y}")

    @field_validator('node_type')
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        """Validate node_type is one of allowed values."""
        allowed_types = {t.value for t in NodeType}
        if v not in allowed_types:
            raise ValueError(f"node_type must be one of {allowed_types}, got: {v}")
        return v


# Allow recursive reference
ExpressionNodeRequest.model_rebuild()


class ExpressionNodeResponse(BaseModel):
    """Response schema for expression node."""

    node_id: str
    node_type: str
    value: str | float | int | bool | None = None
    children: list["ExpressionNodeResponse"] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] | None = None


ExpressionNodeResponse.model_rebuild()


# =============================================================================
# Feature Definition Schemas
# =============================================================================


class FeatureDefinitionCreate(BaseModel):
    """Request schema for creating a new feature definition."""

    name: str = Field(..., min_length=1, max_length=255, description="Feature name")
    description: str | None = Field(None, max_length=1000, description="Feature description")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    expression_tree: ExpressionNodeRequest = Field(..., description="Expression tree root node")
    output_type: str | None = Field(default="numeric", description="Expected output type")
    canvas_state: dict[str, Any] | None = Field(None, description="Canvas state for UI")

    @field_validator('output_type')
    @classmethod
    def validate_output_type(cls, v: str | None) -> str | None:
        """Validate output_type is one of allowed values."""
        if v is None:
            return "numeric"
        allowed_types = {t.value for t in OutputType}
        if v not in allowed_types:
            raise ValueError(f"output_type must be one of {allowed_types}, got: {v}")
        return v


class FeatureDefinitionUpdate(BaseModel):
    """Request schema for updating a feature definition."""

    name: str | None = Field(None, min_length=1, max_length=255, description="Feature name")
    description: str | None = Field(None, max_length=1000, description="Feature description")
    tags: list[str] | None = Field(None, description="Tags for categorization")
    expression_tree: ExpressionNodeRequest | None = Field(None, description="Expression tree")
    output_type: str | None = Field(None, description="Expected output type")
    canvas_state: dict[str, Any] | None = Field(None, description="Canvas state for UI")

    @field_validator('output_type')
    @classmethod
    def validate_output_type(cls, v: str | None) -> str | None:
        """Validate output_type if provided."""
        if v is None:
            return v
        allowed_types = {t.value for t in OutputType}
        if v not in allowed_types:
            raise ValueError(f"output_type must be one of {allowed_types}, got: {v}")
        return v


class FeatureStatisticsResponse(BaseModel):
    """Response schema for feature statistics."""

    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    null_count: int = 0
    unique_count: int = 0
    total_count: int = 0


class FeatureValidationResponse(BaseModel):
    """Response schema for feature validation."""

    is_valid: bool = Field(..., description="Whether expression is valid")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    inferred_type: str | None = Field(None, description="Inferred output type")
    validated_at: datetime = Field(..., description="Validation timestamp")


class FeatureDefinitionResponse(BaseModel):
    """Response schema for feature definition."""

    id: str = Field(..., description="MongoDB document ID")
    feature_id: str = Field(..., description="Unique feature identifier")
    user_id: str = Field(..., description="Owner user ID")
    dataset_id: str = Field(..., description="Associated dataset ID")
    name: str = Field(..., description="Feature name")
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    expression_tree: ExpressionNodeResponse = Field(..., description="Expression tree")
    formula_string: str | None = Field(None, description="Human-readable formula")
    input_columns: list[str] = Field(default_factory=list)
    output_type: str = Field(default="numeric")
    is_valid: bool = Field(default=False)
    validation_result: FeatureValidationResponse | None = None
    statistics: FeatureStatisticsResponse | None = None
    canvas_state: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    version: str = "1.0.0"


class FeatureListResponse(BaseModel):
    """Response schema for listing features."""

    features: list[FeatureDefinitionResponse] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="Total number of features")
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class FeatureDeleteResponse(BaseModel):
    """Response schema for feature deletion."""

    status: str = Field(..., description="Delete status")
    feature_id: str = Field(..., description="Deleted feature ID")
    message: str = Field(..., description="Status message")


# =============================================================================
# Feature Template Schemas
# =============================================================================


class FeatureTemplateInfo(BaseModel):
    """Information about a feature template."""

    template_id: str = Field(..., description="Template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="What this template creates")
    category: str = Field(..., description="Template category")
    required_column_types: list[str] = Field(
        default_factory=list,
        description="Types of columns needed"
    )
    num_columns_required: int = Field(default=1, description="Number of columns needed")
    example_formula: str = Field(..., description="Example formula")
    parameters: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Template parameters"
    )


# =============================================================================
# Feature Application Schemas
# =============================================================================


class ApplyFeatureRequest(BaseModel):
    """Request schema for applying a feature to the dataset."""

    feature_id: str = Field(..., description="Feature to apply")
    output_column_name: str | None = Field(None, description="Name for output column")
    create_new_dataset: bool = Field(default=False, description="Create new dataset version")


class ApplyFeatureResponse(BaseModel):
    """Response schema for applying a feature."""

    success: bool = Field(default=True)
    dataset_id: str = Field(..., description="Dataset ID (new if created)")
    column_name: str = Field(..., description="Name of added column")
    rows_computed: int = Field(..., ge=0, description="Number of rows computed")
    null_values: int = Field(default=0, ge=0, description="Null values in result")
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ApplyMultipleFeaturesRequest(BaseModel):
    """Request schema for applying multiple features."""

    feature_ids: list[str] = Field(..., min_length=1, max_length=50)
    create_new_dataset: bool = Field(default=False)
