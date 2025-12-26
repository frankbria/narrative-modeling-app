"""
Pydantic schemas for Transformation API endpoints.

These schemas define request/response models for transformation operations,
using TransformationConfig model.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

# Import canonical TransformationType from models - SINGLE SOURCE OF TRUTH
from app.models.transformation import TransformationType


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
    preview_rows: Optional[int] = Field(default=100, description="Number of rows to preview")


class TransformationApplyRequest(BaseModel):
    """Request schema for applying a single transformation."""

    dataset_id: str = Field(..., description="Dataset to apply transformation to")
    transformation_type: str = Field(..., description="Type of transformation")
    column: Optional[str] = Field(None, description="Target column")
    columns: Optional[List[str]] = Field(None, description="Target columns")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Transformation parameters")
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

    success: bool = Field(default=True, description="Whether preview succeeded")
    preview_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Preview of transformed data")
    affected_rows: int = Field(default=0, ge=0, description="Number of rows affected")
    affected_columns: List[str] = Field(default_factory=list, description="Columns affected")
    stats_before: Optional[Dict[str, Any]] = Field(default=None, description="Statistics before transformation")
    stats_after: Optional[Dict[str, Any]] = Field(default=None, description="Statistics after transformation")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")


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

    success: bool = Field(default=True, description="Whether apply succeeded")
    dataset_id: str = Field(..., description="Dataset ID")
    transformation_id: str = Field(default="", description="Transformation ID")
    affected_rows: int = Field(default=0, ge=0, description="Number of rows affected")
    affected_columns: List[str] = Field(default_factory=list, description="Columns affected")
    execution_time_ms: int = Field(default=0, ge=0, description="Execution time in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")


class TransformationHistoryResponse(BaseModel):
    """Response schema for transformation history."""

    config_id: str = Field(..., description="Configuration ID")
    dataset_id: str = Field(..., description="Dataset ID")
    user_id: str = Field(..., description="User ID")
    transformation_steps: List[Dict[str, Any]] = Field(default_factory=list, description="Transformation steps")
    is_applied: bool = Field(default=False, description="Whether transformations are applied")
    applied_at: Optional[datetime] = Field(default=None, description="When transformations were applied")
    current_file_path: Optional[str] = Field(default=None, description="Current file path after transformations")
    total_transformations: int = Field(default=0, ge=0, description="Total number of transformations")
    total_data_loss: float = Field(default=0.0, ge=0.0, description="Total data loss percentage")
    parent_config_id: Optional[str] = Field(default=None, description="Parent config ID for lineage")
    version: str = Field(default="1.0.0", description="Version (major.minor.patch)")
    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: datetime = Field(..., description="Updated timestamp")


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
    rating: Optional[float] = None


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


class RecipeCompatibilityRequest(BaseModel):
    """Request schema for recipe compatibility check."""

    dataset_schema: Dict[str, str] = Field(..., description="Dataset column schema {column: type}")


class RecipeCompatibilityResponse(BaseModel):
    """Response schema for compatibility check."""

    is_compatible: bool
    missing_columns: List[str] = Field(default_factory=list)
    type_mismatches: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    compatibility_score: float


class RecipeVersionRequest(BaseModel):
    """Request schema for creating recipe version."""

    changes: Dict[str, Any] = Field(..., description="Changes to apply to new version")
    version_notes: Optional[str] = Field(None, description="Notes about this version")


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

    shared_recipes: List[Dict[str, Any]]
    total: int


class RecipeImportRequest(BaseModel):
    """Request schema for recipe import."""

    json_data: Dict[str, Any] = Field(..., description="Recipe JSON data")
    name_override: Optional[str] = Field(None, description="Override recipe name")


class RecipeExportJSONResponse(BaseModel):
    """Response schema for JSON recipe export."""

    format_version: str
    recipe: Dict[str, Any]


class RecipeDuplicateRequest(BaseModel):
    """Request schema for duplicating recipe."""

    new_name: str = Field(..., description="Name for duplicate recipe")


class RecipeVersionHistoryResponse(BaseModel):
    """Response schema for version history."""

    versions: List[Dict[str, Any]]
    total_versions: int


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


class TransformationTypeInfo(BaseModel):
    """Response schema for available transformation types with metadata."""

    type: str = Field(..., description="Transformation type identifier")
    category: str = Field(..., description="Category (Data Cleaning, Missing Values, etc.)")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(..., description="What this transformation does")
    parameters_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON schema for parameters")
    requires_columns: bool = Field(default=False, description="Whether transformation requires column selection")


# History Response Schemas

class HistoryOperationResponse(BaseModel):
    """Response schema for history operations (undo/redo/jump)."""

    success: bool = Field(..., description="Whether operation succeeded")
    version_id: Optional[str] = Field(None, description="Version ID after operation")
    current_position: int = Field(..., description="Current position in history")
    message: str = Field(..., description="Human-readable message")


class HistoryEntrySchema(BaseModel):
    """Schema for a single history entry."""

    position: int = Field(..., description="Position in history (0-indexed)")
    transformation_type: str = Field(..., description="Type of transformation")
    description: str = Field(..., description="Human-readable description")
    timestamp: str = Field(..., description="ISO timestamp")
    affected_columns: List[str] = Field(default_factory=list, description="Columns affected")
    rows_affected: Optional[int] = Field(None, description="Number of rows affected")
    version_id: Optional[str] = Field(None, description="Associated version ID")


class HistoryDataResponse(BaseModel):
    """Response schema for get history endpoint."""

    history: List[HistoryEntrySchema] = Field(..., description="List of history entries")
    current_position: int = Field(..., description="Current position in history")
    can_undo: bool = Field(..., description="Whether undo is available")
    can_redo: bool = Field(..., description="Whether redo is available")


class ClearHistoryResponse(BaseModel):
    """Response schema for clear history endpoint."""

    success: bool = Field(..., description="Whether operation succeeded")


# =============================================================================
# Bulk Transformation Schemas
# =============================================================================


class ColumnSelectionPatternRequest(BaseModel):
    """Request schema for column selection by pattern."""

    pattern_type: str = Field(
        ...,
        description="Type of pattern: data_type, name_pattern, quality_metric, custom"
    )
    criteria: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pattern-specific criteria"
    )

    @field_validator('pattern_type')
    @classmethod
    def validate_pattern_type(cls, v: str) -> str:
        """Validate pattern type."""
        allowed = {'data_type', 'name_pattern', 'quality_metric', 'custom'}
        if v not in allowed:
            raise ValueError(f"pattern_type must be one of {allowed}, got: {v}")
        return v


class ColumnMetadataResponse(BaseModel):
    """Response schema for column metadata in selection results."""

    column_name: str = Field(..., description="Column name")
    field_type: str = Field(..., description="Field type (numeric, text, etc.)")
    missing_values: int = Field(default=0, ge=0, description="Number of missing values")
    unique_values: int = Field(default=0, ge=0, description="Number of unique values")
    is_constant: bool = Field(default=False, description="Whether column is constant")
    is_high_cardinality: bool = Field(default=False, description="Whether column has high cardinality")


class ColumnSelectionResponse(BaseModel):
    """Response schema for column selection endpoint."""

    columns: List[ColumnMetadataResponse] = Field(
        default_factory=list,
        description="List of matching columns with metadata"
    )
    total_matched: int = Field(default=0, ge=0, description="Total number of matched columns")
    pattern_applied: str = Field(..., description="Pattern that was applied")


class BulkTransformationPreviewRequest(BaseModel):
    """Request schema for bulk transformation preview."""

    selected_columns: List[str] = Field(
        ...,
        min_length=1,
        description="List of columns to preview transformation on"
    )
    transformation_type: str = Field(..., description="Type of transformation")
    global_parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Global transformation parameters"
    )
    per_column_params: Optional[Dict[str, Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Per-column parameter overrides"
    )
    preview_rows: int = Field(default=10, ge=1, le=100, description="Number of rows to preview")

    @field_validator('transformation_type')
    @classmethod
    def validate_transformation_type(cls, v: str) -> str:
        """Validate transformation_type is one of supported types."""
        allowed_types = {t.value for t in TransformationType}
        if v not in allowed_types:
            raise ValueError(f"transformation_type must be one of {allowed_types}, got: {v}")
        return v


class ColumnPreviewResult(BaseModel):
    """Preview result for a single column."""

    column_name: str = Field(..., description="Column name")
    success: bool = Field(default=True, description="Whether preview succeeded")
    preview_data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Preview rows for this column"
    )
    stats_before: Optional[Dict[str, Any]] = Field(default=None, description="Stats before")
    stats_after: Optional[Dict[str, Any]] = Field(default=None, description="Stats after")
    affected_rows: int = Field(default=0, ge=0, description="Estimated rows affected")
    error: Optional[str] = Field(default=None, description="Error if preview failed")
    warnings: List[str] = Field(default_factory=list, description="Warnings")


class BulkTransformationPreviewResponse(BaseModel):
    """Response schema for bulk transformation preview."""

    success: bool = Field(default=True, description="Whether all previews succeeded")
    column_previews: List[ColumnPreviewResult] = Field(
        default_factory=list,
        description="Preview results per column"
    )
    total_estimated_rows_affected: int = Field(
        default=0,
        ge=0,
        description="Total estimated rows affected"
    )
    total_columns: int = Field(default=0, ge=0, description="Total columns previewed")
    successful_previews: int = Field(default=0, ge=0, description="Number of successful previews")
    failed_previews: int = Field(default=0, ge=0, description="Number of failed previews")
    error: Optional[str] = Field(default=None, description="Global error if any")
    warnings: List[str] = Field(default_factory=list, description="Global warnings")


class BulkTransformationRequest(BaseModel):
    """Request schema for applying bulk transformation."""

    selected_columns: List[str] = Field(
        ...,
        min_length=1,
        description="List of columns to transform"
    )
    transformation_type: str = Field(..., description="Type of transformation")
    global_parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Global transformation parameters"
    )
    per_column_params: Optional[Dict[str, Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Per-column parameter overrides"
    )
    stop_on_error: bool = Field(
        default=False,
        description="Whether to stop processing on first error"
    )

    @field_validator('transformation_type')
    @classmethod
    def validate_transformation_type(cls, v: str) -> str:
        """Validate transformation_type is one of supported types."""
        allowed_types = {t.value for t in TransformationType}
        if v not in allowed_types:
            raise ValueError(f"transformation_type must be one of {allowed_types}, got: {v}")
        return v


class BulkTransformationJobResponse(BaseModel):
    """Response schema for bulk transformation job creation."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    selected_columns: List[str] = Field(default_factory=list, description="Columns being transformed")
    total_columns: int = Field(default=0, ge=0, description="Total columns to process")
    message: str = Field(..., description="Status message")


class BulkTransformationProgressResponse(BaseModel):
    """Response schema for bulk transformation job progress."""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Current job status")
    progress: Dict[str, Any] = Field(
        default_factory=dict,
        description="Progress details"
    )
    percentage_complete: float = Field(default=0.0, ge=0, le=100, description="Percentage complete")
    total_columns: int = Field(default=0, ge=0, description="Total columns")
    processed_columns: int = Field(default=0, ge=0, description="Processed columns")
    successful_columns: int = Field(default=0, ge=0, description="Successful columns")
    failed_columns: int = Field(default=0, ge=0, description="Failed columns")
    current_column: Optional[str] = Field(default=None, description="Currently processing column")
    estimated_remaining_seconds: Optional[float] = Field(
        default=None,
        description="Estimated time remaining in seconds"
    )
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Results if completed")


class BulkJobListResponse(BaseModel):
    """Response schema for listing bulk transformation jobs."""

    jobs: List[BulkTransformationJobResponse] = Field(
        default_factory=list,
        description="List of jobs"
    )
    total: int = Field(default=0, ge=0, description="Total number of jobs")
