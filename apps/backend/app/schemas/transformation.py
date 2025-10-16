"""
Pydantic schemas for Transformation API endpoints.

These schemas define request/response models for transformation operations,
using TransformationConfig model.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# Transformation types enum
class TransformationType(str, Enum):
    """Supported transformation types."""
    ENCODE = "encode"
    SCALE = "scale"
    IMPUTE = "impute"
    DROP_MISSING = "drop_missing"
    FILTER = "filter"
    AGGREGATE = "aggregate"
    DERIVE = "derive"
    NORMALIZE = "normalize"
    STANDARDIZE = "standardize"
    ONE_HOT_ENCODE = "one_hot_encode"
    LABEL_ENCODE = "label_encode"
    FILL_MISSING = "fill_missing"
    DROP_DUPLICATES = "drop_duplicates"
    OUTLIER_REMOVAL = "outlier_removal"


# Request Schemas

class TransformationStepRequest(BaseModel):
    """Request schema for adding a transformation step."""

    transformation_type: str = Field(..., description="Type of transformation")
    column: Optional[str] = Field(None, description="Target column")
    columns: Optional[List[str]] = Field(None, description="Target columns")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Transformation parameters")

    @field_validator('transformation_type')
    @classmethod
    def validate_transformation_type(cls, v: str) -> str:
        """Validate transformation_type is one of supported types."""
        allowed_types = {t.value for t in TransformationType}
        if v not in allowed_types:
            raise ValueError(f"transformation_type must be one of {allowed_types}, got: {v}")
        return v


class TransformationPreviewRequest(BaseModel):
    """Request schema for transformation preview."""

    dataset_id: str = Field(..., description="Dataset to preview transformation on")
    transformation_steps: List[TransformationStepRequest] = Field(..., description="Transformation steps to preview")


class TransformationApplyRequest(BaseModel):
    """Request schema for applying transformations."""

    dataset_id: str = Field(..., description="Dataset to apply transformations to")
    transformation_steps: List[TransformationStepRequest] = Field(..., description="Transformation steps to apply")
    save_as_new: bool = Field(default=False, description="Whether to save as new dataset version")


# Response Schemas

class TransformationStepResponse(BaseModel):
    """Response schema for transformation step."""

    transformation_type: str
    column: Optional[str] = None
    columns: Optional[List[str]] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    applied_at: datetime
    is_valid: bool = True
    validation_errors: List[str] = Field(default_factory=list)
    rows_affected: Optional[int] = None
    data_loss_percentage: Optional[float] = None


class TransformationConfigResponse(BaseModel):
    """Response schema for transformation configuration."""

    config_id: str = Field(..., description="Configuration identifier")
    user_id: str = Field(..., description="User who owns the configuration")
    dataset_id: str = Field(..., description="Dataset this config applies to")
    transformation_steps: List[TransformationStepResponse] = Field(default_factory=list)
    current_file_path: Optional[str] = None
    is_applied: bool = False
    applied_at: Optional[datetime] = None
    total_transformations: int = 0
    total_data_loss: float = 0.0
    created_at: datetime
    updated_at: datetime
    version: str


class TransformationPreviewResponse(BaseModel):
    """Response schema for transformation preview."""

    sample_before: List[Dict[str, Any]] = Field(default_factory=list)
    sample_after: List[Dict[str, Any]] = Field(default_factory=list)
    affected_columns: List[str] = Field(default_factory=list)
    estimated_rows_affected: int = Field(..., ge=0)
    estimated_data_loss: float = Field(default=0.0, ge=0.0, le=100.0)
    warnings: List[str] = Field(default_factory=list)
    generated_at: datetime


class TransformationValidationResponse(BaseModel):
    """Response schema for transformation validation."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validated_at: datetime
    parameter_validation: Dict[str, bool] = Field(default_factory=dict)
    data_type_compatibility: Dict[str, bool] = Field(default_factory=dict)
    dependency_validation: bool = True


class TransformationApplyResponse(BaseModel):
    """Response schema for transformation apply operation."""

    config_id: str = Field(..., description="Configuration ID")
    dataset_id: str = Field(..., description="Dataset ID")
    is_applied: bool = True
    applied_at: datetime
    new_file_path: str = Field(..., description="Path to transformed file")
    transformations_count: int = Field(..., ge=0)
    total_data_loss: float = Field(..., ge=0.0, le=100.0)


class TransformationHistoryResponse(BaseModel):
    """Response schema for transformation history."""

    config_id: str = Field(..., description="Configuration ID")
    dataset_id: str = Field(..., description="Dataset ID")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Transformation history")
    total_steps: int = Field(..., ge=0)
    created_at: datetime
    updated_at: datetime


class TransformationListResponse(BaseModel):
    """Response schema for list transformations endpoint."""

    configurations: List[TransformationConfigResponse] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="Total number of configurations")


class TransformationDeleteResponse(BaseModel):
    """Response schema for transformation delete endpoint."""

    status: str = Field(..., description="Delete status")
    config_id: str = Field(..., description="Deleted configuration ID")
    message: str = Field(..., description="Success message")


# Additional schemas for transformation pipeline

class TransformationPipelineRequest(BaseModel):
    """Request schema for transformation pipeline."""

    dataset_id: str = Field(..., description="Dataset ID")
    transformations: List[TransformationStepRequest] = Field(..., description="Transformation steps")
    save_as_recipe: bool = Field(default=False, description="Save as recipe")
    recipe_name: Optional[str] = Field(None, description="Recipe name")
    recipe_description: Optional[str] = Field(None, description="Recipe description")


class RecipeStepRequest(BaseModel):
    """Request schema for recipe step."""

    type: str = Field(..., description="Transformation type")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None


class RecipeCreateRequest(BaseModel):
    """Request schema for creating recipe."""

    name: str = Field(..., description="Recipe name")
    description: Optional[str] = None
    steps: List[RecipeStepRequest] = Field(..., description="Recipe steps")
    dataset_id: Optional[str] = None
    is_public: bool = Field(default=False)
    tags: List[str] = Field(default_factory=list)


class RecipeResponse(BaseModel):
    """Response schema for recipe."""

    id: str
    name: str
    description: Optional[str] = None
    user_id: str
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    tags: List[str] = Field(default_factory=list)
    usage_count: int = 0
    rating: float = 0.0


class RecipeListResponse(BaseModel):
    """Response schema for recipe list."""

    recipes: List[RecipeResponse] = Field(default_factory=list)
    total: int
    page: int
    per_page: int


class RecipeApplyRequest(BaseModel):
    """Request schema for applying recipe."""

    dataset_id: str = Field(..., description="Dataset ID")


class RecipeExportRequest(BaseModel):
    """Request schema for exporting recipe."""

    language: str = Field(default="python", description="Export language")


class RecipeExportResponse(BaseModel):
    """Response schema for recipe export."""

    recipe_name: str
    language: str
    code: str


class AutoCleanRequest(BaseModel):
    """Request schema for auto-clean operation."""

    dataset_id: str = Field(..., description="Dataset ID")
    options: Dict[str, Any] = Field(default_factory=dict)


class TransformationSuggestionResponse(BaseModel):
    """Response schema for transformation suggestions."""

    suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    data_quality_score: float
    critical_issues: List[str] = Field(default_factory=list)


class ValidationRequest(BaseModel):
    """Request schema for validation."""

    dataset_id: str = Field(..., description="Dataset ID")
    transformations: List[TransformationStepRequest] = Field(..., description="Transformations to validate")


class ValidationResponse(BaseModel):
    """Response schema for validation."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    info: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
