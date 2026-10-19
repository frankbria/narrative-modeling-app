"""
Pydantic schemas for Transformation API endpoints.

These schemas define request/response models for transformation operations,
using TransformationConfig model.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Import canonical TransformationType from models - SINGLE SOURCE OF TRUTH
from app.models.transformation import TransformationType

# Request Schemas

class TransformationStepRequest(BaseModel):
    """Request schema for adding a transformation step."""

    transformation_type: str = Field(..., description="Type of transformation")
    column: str | None = Field(None, description="Target column")
    columns: list[str] | None = Field(None, description="Target columns")
    parameters: dict[str, Any] | None = Field(default_factory=dict, description="Transformation parameters")

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
    transformation_steps: list[TransformationStepRequest] = Field(..., description="Transformation steps to preview")
    preview_rows: int | None = Field(default=100, description="Number of rows to preview")


class TransformationApplyRequest(BaseModel):
    """Request schema for applying a single transformation."""

    dataset_id: str = Field(..., description="Dataset to apply transformation to")
    transformation_type: str = Field(..., description="Type of transformation")
    column: str | None = Field(None, description="Target column")
    columns: list[str] | None = Field(None, description="Target columns")
    parameters: dict[str, Any] | None = Field(default_factory=dict, description="Transformation parameters")
    save_as_new: bool = Field(default=False, description="Whether to save as new dataset version")

    @field_validator('transformation_type')
    @classmethod
    def validate_transformation_type(cls, v: str) -> str:
        """Validate transformation_type is one of supported types."""
        allowed_types = {t.value for t in TransformationType}
        if v not in allowed_types:
            raise ValueError(f"transformation_type must be one of {allowed_types}, got: {v}")
        return v


# Response Schemas

class TransformationStepResponse(BaseModel):
    """Response schema for transformation step."""

    transformation_type: str
    column: str | None = None
    columns: list[str] | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    applied_at: datetime
    is_valid: bool = True
    validation_errors: list[str] = Field(default_factory=list)
    rows_affected: int | None = None
    data_loss_percentage: float | None = None


class TransformationConfigResponse(BaseModel):
    """Response schema for transformation configuration."""

    config_id: str = Field(..., description="Configuration identifier")
    user_id: str = Field(..., description="User who owns the configuration")
    dataset_id: str = Field(..., description="Dataset this config applies to")
    transformation_steps: list[TransformationStepResponse] = Field(default_factory=list)
    current_file_path: str | None = None
    is_applied: bool = False
    applied_at: datetime | None = None
    total_transformations: int = 0
    total_data_loss: float = 0.0
    created_at: datetime
    updated_at: datetime
    version: str


class TransformationPreviewResponse(BaseModel):
    """Response schema for transformation preview."""

    success: bool = Field(default=True, description="Whether preview succeeded")
    preview_data: list[dict[str, Any]] | None = Field(default=None, description="Preview of transformed data")
    affected_rows: int = Field(default=0, ge=0, description="Number of rows affected")
    affected_columns: list[str] = Field(default_factory=list, description="Columns affected")
    stats_before: dict[str, Any] | None = Field(default=None, description="Statistics before transformation")
    stats_after: dict[str, Any] | None = Field(default=None, description="Statistics after transformation")
    error: str | None = Field(default=None, description="Error message if failed")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")


class TransformationApplyResponse(BaseModel):
    """Response schema for transformation apply operation."""

    success: bool = Field(default=True, description="Whether apply succeeded")
    dataset_id: str = Field(..., description="Dataset ID")
    transformation_id: str = Field(default="", description="Transformation ID")
    affected_rows: int = Field(default=0, ge=0, description="Number of rows affected")
    affected_columns: list[str] = Field(default_factory=list, description="Columns affected")
    execution_time_ms: int = Field(default=0, ge=0, description="Execution time in milliseconds")
    error: str | None = Field(default=None, description="Error message if failed")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")


class TransformationHistoryResponse(BaseModel):
    """Response schema for transformation history."""

    config_id: str = Field(..., description="Configuration ID")
    dataset_id: str = Field(..., description="Dataset ID")
    user_id: str = Field(..., description="User ID")
    transformation_steps: list[dict[str, Any]] = Field(default_factory=list, description="Transformation steps")
    is_applied: bool = Field(default=False, description="Whether transformations are applied")
    applied_at: datetime | None = Field(default=None, description="When transformations were applied")
    current_file_path: str | None = Field(default=None, description="Current file path after transformations")
    total_transformations: int = Field(default=0, ge=0, description="Total number of transformations")
    total_data_loss: float = Field(default=0.0, ge=0.0, description="Total data loss percentage")
    parent_config_id: str | None = Field(default=None, description="Parent config ID for lineage")
    version: str = Field(default="1.0.0", description="Version (major.minor.patch)")
    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: datetime = Field(..., description="Updated timestamp")


# Additional schemas for transformation pipeline

class RecipeStepRequest(BaseModel):
    """Request schema for recipe step."""

    type: str = Field(..., description="Transformation type")
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate type against the canonical TransformationType enum.

        Without this, unsupported types would be silently skipped by the
        validate endpoint's dispatch and reported as valid.
        """
        allowed_types = {t.value for t in TransformationType}
        if v not in allowed_types:
            raise ValueError(
                f"Unknown transformation type: '{v}'. "
                f"See TransformationType for supported values."
            )
        return v


class TransformationPipelineRequest(BaseModel):
    """Request schema for transformation pipeline."""

    dataset_id: str = Field(..., description="Dataset ID")
    transformations: list[RecipeStepRequest] = Field(..., description="Transformation steps")
    save_as_recipe: bool = Field(default=False, description="Save as recipe")
    recipe_name: str | None = Field(None, description="Recipe name")
    recipe_description: str | None = Field(None, description="Recipe description")


class RecipeCreateRequest(BaseModel):
    """Request schema for creating recipe."""

    name: str = Field(..., description="Recipe name")
    description: str | None = None
    steps: list[RecipeStepRequest] = Field(..., description="Recipe steps")
    dataset_id: str | None = None
    is_public: bool = Field(default=False)
    tags: list[str] = Field(default_factory=list)


class RecipeResponse(BaseModel):
    """Response schema for recipe."""

    id: str
    name: str
    description: str | None = None
    # The owner's id, returned to the owner only. A public recipe read by another
    # account carries None (#914).
    user_id: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    tags: list[str] = Field(default_factory=list)
    usage_count: int = 0
    rating: float | None = None


class RecipeListResponse(BaseModel):
    """Response schema for recipe list."""

    recipes: list[RecipeResponse] = Field(default_factory=list)
    total: int
    page: int
    per_page: int


class RecipeApplyRequest(BaseModel):
    """Request schema for applying recipe."""

    dataset_id: str = Field(..., description="Dataset ID")


class PipelineExportRequest(BaseModel):
    """Request schema for exporting a pipeline as code: its steps, in order."""

    steps: list[RecipeStepRequest] = Field(..., max_length=200, description="Pipeline steps")


class PipelineExportResponse(BaseModel):
    """Response schema for a pipeline exported as code."""

    language: str
    filename: str
    code: str


class RecipeExportRequest(BaseModel):
    """Request schema for exporting recipe."""

    language: str = Field(default="python", description="Export language")


class RecipeExportResponse(BaseModel):
    """Response schema for recipe export."""

    recipe_name: str
    language: str
    code: str


class RecipeCompatibilityRequest(BaseModel):
    """Request schema for recipe compatibility check."""

    dataset_schema: dict[str, str] = Field(..., description="Dataset column schema {column: type}")


class RecipeCompatibilityResponse(BaseModel):
    """Response schema for compatibility check."""

    is_compatible: bool
    missing_columns: list[str] = Field(default_factory=list)
    type_mismatches: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    compatibility_score: float


class RecipeVersionRequest(BaseModel):
    """Request schema for creating recipe version."""

    changes: dict[str, Any] = Field(..., description="Changes to apply to new version")
    version_notes: str | None = Field(None, description="Notes about this version")


class RecipeShareRequest(BaseModel):
    """Request schema for sharing recipe."""

    target_user_id: str = Field(..., description="User ID to share with")


class RecipeShareResponse(BaseModel):
    """Response schema for sharing recipe."""

    shared_recipe_id: str
    target_user_id: str
    shared_at: str
    message: str


class SharedRecipeListResponse(BaseModel):
    """Response schema for shared recipes list."""

    shared_recipes: list[dict[str, Any]]
    total: int


class RecipeImportRequest(BaseModel):
    """Request schema for recipe import."""

    json_data: dict[str, Any] = Field(..., description="Recipe JSON data")
    name_override: str | None = Field(None, description="Override recipe name")


class RecipeExportJSONResponse(BaseModel):
    """Response schema for JSON recipe export."""

    format_version: str
    recipe: dict[str, Any]


class RecipeDuplicateRequest(BaseModel):
    """Request schema for duplicating recipe."""

    new_name: str = Field(..., description="Name for duplicate recipe")


class RecipeVersionHistoryResponse(BaseModel):
    """Response schema for version history."""

    versions: list[dict[str, Any]]
    total_versions: int


class AutoCleanRequest(BaseModel):
    """Request schema for auto-clean operation."""

    dataset_id: str = Field(..., description="Dataset ID")
    options: dict[str, Any] = Field(default_factory=dict)


class TransformationSuggestionResponse(BaseModel):
    """Response schema for transformation suggestions."""

    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_score: float
    critical_issues: list[str] = Field(default_factory=list)


class ValidationRequest(BaseModel):
    """Request schema for validation."""

    dataset_id: str = Field(..., description="Dataset ID")
    transformations: list[RecipeStepRequest] = Field(..., description="Transformations to validate")


class ValidationResponse(BaseModel):
    """Response schema for validation."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    info: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class TransformationTypeInfo(BaseModel):
    """Response schema for available transformation types with metadata."""

    type: str = Field(..., description="Transformation type identifier")
    category: str = Field(..., description="Category (Data Cleaning, Missing Values, etc.)")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(..., description="What this transformation does")
    parameters_schema: dict[str, Any] = Field(default_factory=dict, description="JSON schema for parameters")
    requires_columns: bool = Field(default=False, description="Whether transformation requires column selection")


# History Response Schemas

class HistoryOperationResponse(BaseModel):
    """Response schema for history operations (undo/redo/jump)."""

    success: bool = Field(..., description="Whether operation succeeded")
    version_id: str | None = Field(None, description="Version ID after operation")
    current_position: int = Field(..., description="Current position in history")
    message: str = Field(..., description="Human-readable message")


class HistoryEntrySchema(BaseModel):
    """Schema for a single history entry."""

    position: int = Field(..., description="Position in history (0-indexed)")
    transformation_type: str = Field(..., description="Type of transformation")
    description: str = Field(..., description="Human-readable description")
    timestamp: str = Field(..., description="ISO timestamp")
    affected_columns: list[str] = Field(default_factory=list, description="Columns affected")
    rows_affected: int | None = Field(None, description="Number of rows affected")
    version_id: str | None = Field(None, description="Associated version ID")


class HistoryDataResponse(BaseModel):
    """Response schema for get history endpoint."""

    history: list[HistoryEntrySchema] = Field(..., description="List of history entries")
    current_position: int = Field(..., description="Current position in history")
    can_undo: bool = Field(..., description="Whether undo is available")
    can_redo: bool = Field(..., description="Whether redo is available")


class ClearHistoryResponse(BaseModel):
    """Response schema for clear history endpoint."""

    success: bool = Field(..., description="Whether operation succeeded")
