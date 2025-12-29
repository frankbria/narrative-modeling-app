"""
Transformation configuration model for MongoDB.

This model focuses on data transformation configurations, history, and validation.
It replaces the transformation-specific fields from the legacy UserData model.
"""

from beanie import Document, Indexed
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from beanie import PydanticObjectId
from enum import Enum


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(timezone.utc)


# =============================================================================
# CANONICAL TransformationType Enum - Single Source of Truth
# =============================================================================
# This enum is the canonical definition for all transformation types.
# Import this enum in schemas and services - do NOT duplicate.
# =============================================================================

class TransformationType(str, Enum):
    """
    Supported transformation types.

    This is the SINGLE SOURCE OF TRUTH for transformation types.
    Import from app.models.transformation in all other modules.
    """
    # Data Cleaning
    REMOVE_DUPLICATES = "remove_duplicates"
    TRIM_WHITESPACE = "trim_whitespace"
    FIX_CASING = "fix_casing"
    REMOVE_SPECIAL_CHARS = "remove_special_chars"
    STANDARDIZE_FORMAT = "standardize_format"

    # Missing Values
    DROP_MISSING = "drop_missing"
    FILL_MISSING = "fill_missing"
    IMPUTE_MEAN = "impute_mean"
    IMPUTE_MEDIAN = "impute_median"
    IMPUTE_MODE = "impute_mode"
    IMPUTE_FORWARD = "impute_forward"
    IMPUTE_BACKWARD = "impute_backward"

    # Type Conversions
    TO_NUMERIC = "to_numeric"
    TO_STRING = "to_string"
    TO_DATETIME = "to_datetime"
    TO_BOOLEAN = "to_boolean"
    ONE_HOT_ENCODE = "one_hot_encode"
    LABEL_ENCODE = "label_encode"

    # Date/Time
    EXTRACT_DATE_PARTS = "extract_date_parts"
    CALCULATE_AGE = "calculate_age"
    CREATE_CYCLICAL = "create_cyclical"

    # Scaling/Normalization
    SCALE = "scale"
    NORMALIZE = "normalize"
    STANDARDIZE = "standardize"

    # Custom/Advanced
    FORMULA = "formula"
    CONDITIONAL = "conditional"
    REGEX_REPLACE = "regex_replace"
    ENCODE = "encode"
    IMPUTE = "impute"
    FILTER = "filter"
    AGGREGATE = "aggregate"
    DERIVE = "derive"
    OUTLIER_REMOVAL = "outlier_removal"


# Constant for data loss threshold (50%)
DATA_LOSS_THRESHOLD_PERCENT = 50.0


class TransformationStep(BaseModel):
    """A single transformation step with parameters and validation."""

    transformation_type: str = Field(..., description="Type of transformation: encode, scale, impute, drop_missing")
    column: Optional[str] = Field(None, description="Target column for transformation (if applicable)")
    columns: Optional[List[str]] = Field(None, description="Target columns for transformation (for multi-column ops)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Transformation parameters")
    applied_at: datetime = Field(default_factory=get_current_time, description="When transformation was applied")
    version_id: Optional[str] = Field(None, description="Dataset version ID after this transformation")

    # Validation results
    is_valid: bool = Field(default=True, description="Whether transformation parameters are valid")
    validation_errors: List[str] = Field(default_factory=list, description="Validation error messages")

    # Impact tracking
    rows_affected: Optional[int] = Field(None, ge=0, description="Number of rows affected by transformation")
    data_loss_percentage: Optional[float] = Field(None, ge=0.0, le=100.0, description="Percentage of data lost")

    @field_validator('transformation_type')
    @classmethod
    def validate_transformation_type(cls, v: str) -> str:
        """Validate transformation_type is one of supported types."""
        # Use the canonical TransformationType enum as source of truth
        allowed_types = {t.value for t in TransformationType}
        if v not in allowed_types:
            raise ValueError(f"transformation_type must be one of {sorted(allowed_types)}, got: {v}")
        return v

    @model_validator(mode='after')
    def validate_column_specification(self) -> 'TransformationStep':
        """Validate that either column or columns is specified when required."""
        column_required_types = {
            'encode', 'scale', 'impute', 'fill_missing',
            'label_encode', 'normalize', 'standardize'
        }

        if self.transformation_type in column_required_types:
            if not self.column and not self.columns:
                raise ValueError(f"Transformation type '{self.transformation_type}' requires column or columns to be specified")

        return self


class TransformationPreview(BaseModel):
    """Preview of transformation results before application."""

    sample_before: List[Dict[str, Any]] = Field(default_factory=list, description="Sample data before transformation")
    sample_after: List[Dict[str, Any]] = Field(default_factory=list, description="Sample data after transformation")
    affected_columns: List[str] = Field(default_factory=list, description="Columns affected by transformation")
    estimated_rows_affected: int = Field(..., ge=0, description="Estimated number of rows affected")
    estimated_data_loss: float = Field(default=0.0, ge=0.0, le=100.0, description="Estimated data loss percentage")
    warnings: List[str] = Field(default_factory=list, description="Warnings about transformation impact")
    generated_at: datetime = Field(default_factory=get_current_time)


class TransformationValidation(BaseModel):
    """Validation results for transformation configuration."""

    is_valid: bool = Field(..., description="Whether overall transformation configuration is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    validated_at: datetime = Field(default_factory=get_current_time)

    # Detailed validation checks
    parameter_validation: Dict[str, bool] = Field(default_factory=dict, description="Per-parameter validation results")
    data_type_compatibility: Dict[str, bool] = Field(default_factory=dict, description="Data type compatibility checks")
    dependency_validation: bool = Field(default=True, description="Whether transformation order dependencies are valid")


class TransformationConfig(Document):
    """
    Transformation configuration document.

    Stores transformation history, configuration, and validation results for datasets.
    This model replaces the transformation-specific fields from the legacy UserData model,
    providing focused responsibility for transformation management.
    """

    # Ownership and identification
    user_id: Indexed(str) = Field(..., description="User who owns this transformation config")
    dataset_id: Indexed(str) = Field(..., description="Dataset this transformation config applies to")
    config_id: Indexed(str) = Field(..., description="Unique transformation config identifier")

    # Transformation history
    transformation_steps: List[TransformationStep] = Field(default_factory=list, description="Applied transformation steps")
    current_position: int = Field(default=-1, description="Current position in transformation history (-1 = no transformations)")

    # Current state
    current_file_path: Optional[str] = Field(None, description="Current file path after transformations")
    is_applied: bool = Field(default=False, description="Whether transformations have been applied")
    applied_at: Optional[datetime] = None

    # Validation
    validation_result: Optional[TransformationValidation] = None
    last_validated_at: Optional[datetime] = None

    # Preview
    last_preview: Optional[TransformationPreview] = None

    # Metadata
    total_transformations: int = Field(default=0, ge=0, description="Total number of transformations applied")
    total_data_loss: float = Field(default=0.0, ge=0.0, le=100.0, description="Cumulative data loss percentage")

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)

    # Version tracking
    version: str = Field(default="1.0.0", description="Config version (major.minor.patch)")
    parent_config_id: Optional[str] = Field(None, description="Parent config if this is derived")

    class Settings:
        name = "transformation_configs"
        indexes = [
            # Single field indexes for basic queries
            "user_id",
            "dataset_id",
            "config_id",
            "created_at",
            "is_applied",
            # Compound indexes for common query patterns
            [("user_id", 1), ("created_at", -1)],  # List user configs chronologically
            [("dataset_id", 1), ("is_applied", 1)],  # Filter applied/pending transformations
            [("dataset_id", 1), ("is_applied", 1), ("created_at", -1)],  # Applied configs chronologically
            [("dataset_id", 1), ("created_at", -1)],  # All dataset configs chronologically
            # History navigation indexes
            [("dataset_id", 1), ("current_position", 1)],  # Query by dataset and position
            [("user_id", 1), ("dataset_id", 1), ("updated_at", -1)],  # User's dataset configs by recency
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    def add_transformation_step(
        self,
        transformation_type: str,
        column: Optional[str] = None,
        columns: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        version_id: Optional[str] = None
    ) -> TransformationStep:
        """
        Add a new transformation step with branching support.

        If current_position is not at the end of history (i.e., user has done undo),
        this will truncate forward history and create a new branch.

        Args:
            transformation_type: Type of transformation
            column: Single column to transform (optional)
            columns: Multiple columns to transform (optional)
            parameters: Transformation parameters
            version_id: Dataset version ID after this transformation (optional)

        Returns:
            The created transformation step
        """
        step = TransformationStep(
            transformation_type=transformation_type,
            column=column,
            columns=columns,
            parameters=parameters or {},
            version_id=version_id
        )

        # Handle branching: if we're not at the end, truncate forward history
        if self.current_position < len(self.transformation_steps) - 1:
            # Truncate steps after current position
            self.transformation_steps = self.transformation_steps[:self.current_position + 1]

        # Add new step
        self.transformation_steps.append(step)
        self.total_transformations = len(self.transformation_steps)

        # Update position to point to new step
        self.current_position = len(self.transformation_steps) - 1

        self.update_timestamp()

        return step

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = get_current_time()

    def mark_applied(self, file_path: str) -> None:
        """Mark transformations as applied."""
        self.is_applied = True
        self.applied_at = get_current_time()
        self.current_file_path = file_path
        self.update_timestamp()

    def get_transformation_history(self) -> List[Dict[str, Any]]:
        """Get transformation history in legacy format for backward compatibility."""
        return [
            {
                "type": step.transformation_type,
                "column": step.column,
                "columns": step.columns,
                "parameters": step.parameters,
                "applied_at": step.applied_at.isoformat(),
                "rows_affected": step.rows_affected,
                "data_loss_percentage": step.data_loss_percentage
            }
            for step in self.transformation_steps
        ]

    def validate_transformations(self) -> TransformationValidation:
        """
        Validate all transformation steps.

        Returns:
            Validation results
        """
        errors: List[str] = []
        warnings: List[str] = []
        parameter_validation: Dict[str, bool] = {}
        data_type_compatibility: Dict[str, bool] = {}

        for i, step in enumerate(self.transformation_steps):
            step_key = f"step_{i}_{step.transformation_type}"

            # Basic parameter validation
            if step.transformation_type in {'encode', 'scale', 'impute'} and not step.column and not step.columns:
                errors.append(f"Step {i}: {step.transformation_type} requires column specification")
                parameter_validation[step_key] = False
            else:
                parameter_validation[step_key] = True

            # Data loss warnings
            if step.data_loss_percentage and step.data_loss_percentage > 50.0:
                warnings.append(f"Step {i}: High data loss ({step.data_loss_percentage:.1f}%)")

            # Check for validation errors in step
            if step.validation_errors:
                errors.extend([f"Step {i}: {err}" for err in step.validation_errors])

        # Cumulative data loss warning
        if self.total_data_loss > 50.0:
            warnings.append(f"Total data loss exceeds 50% ({self.total_data_loss:.1f}%)")

        validation_result = TransformationValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            parameter_validation=parameter_validation,
            data_type_compatibility=data_type_compatibility
        )

        self.validation_result = validation_result
        self.last_validated_at = get_current_time()
        self.update_timestamp()

        return validation_result

    def clear_transformations(self) -> None:
        """Clear all transformation steps."""
        self.transformation_steps = []
        self.total_transformations = 0
        self.total_data_loss = 0.0
        self.is_applied = False
        self.applied_at = None
        self.validation_result = None
        self.last_preview = None
        self.update_timestamp()

    def get_affected_columns(self) -> List[str]:
        """Get list of all columns affected by transformations."""
        affected = set()
        for step in self.transformation_steps:
            if step.column:
                affected.add(step.column)
            if step.columns:
                affected.update(step.columns)
        return list(affected)

    def can_undo(self) -> bool:
        """
        Check if undo operation is possible.

        Returns:
            True if current_position > 0, False otherwise
        """
        return self.current_position > 0

    def can_redo(self) -> bool:
        """
        Check if redo operation is possible.

        Returns:
            True if current_position < len(transformation_steps) - 1, False otherwise
        """
        return self.current_position < len(self.transformation_steps) - 1

    def get_current_state(self) -> Dict[str, Any]:
        """
        Get current history state metadata.

        Returns:
            Dictionary with current_position, total_steps, can_undo, can_redo
        """
        return {
            "current_position": self.current_position,
            "total_steps": len(self.transformation_steps),
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo()
        }
