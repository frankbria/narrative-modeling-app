"""
Pydantic schemas for transformation API
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class TransformationType(str, Enum):
    """Types of transformations available"""
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
    
    # Custom
    FORMULA = "formula"
    CONDITIONAL = "conditional"
    REGEX_REPLACE = "regex_replace"


class TransformationRequest(BaseModel):
    """Request to preview or apply a transformation"""
    dataset_id: str
    transformation_type: TransformationType
    parameters: Dict[str, Any]
    preview_rows: Optional[int] = Field(default=100, ge=10, le=1000)


class TransformationStepRequest(BaseModel):
    """A single transformation step"""
    type: TransformationType
    parameters: Dict[str, Any]
    description: Optional[str] = None


class TransformationPipelineRequest(BaseModel):
    """Request to apply multiple transformations"""
    dataset_id: str
    transformations: List[TransformationStepRequest]
    save_as_recipe: Optional[bool] = False
    recipe_name: Optional[str] = None
    recipe_description: Optional[str] = None


class TransformationPreviewResponse(BaseModel):
    """Response from transformation preview"""
    success: bool
    preview_data: Optional[List[Dict[str, Any]]] = None
    affected_rows: int = 0
    affected_columns: List[str] = Field(default_factory=list)
    stats_before: Optional[Dict[str, Any]] = None
    stats_after: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)


class TransformationApplyResponse(BaseModel):
    """Response from applying transformation"""
    success: bool
    dataset_id: str
    transformation_id: str
    affected_rows: int = 0
    affected_columns: List[str] = Field(default_factory=list)
    execution_time_ms: int
    error: Optional[str] = None


class RecipeCreateRequest(BaseModel):
    """Request to create a transformation recipe"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    steps: List[TransformationStepRequest]
    dataset_id: Optional[str] = None
    is_public: bool = False
    tags: List[str] = Field(default_factory=list, max_items=10)


class RecipeResponse(BaseModel):
    """Response containing recipe details"""
    id: str
    name: str
    description: Optional[str]
    user_id: str
    steps: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    is_public: bool
    tags: List[str]
    usage_count: int
    rating: Optional[float]


class RecipeListResponse(BaseModel):
    """Response containing list of recipes"""
    recipes: List[RecipeResponse]
    total: int
    page: int
    per_page: int


class RecipeApplyRequest(BaseModel):
    """Request to apply a saved recipe"""
    recipe_id: str
    dataset_id: str


class RecipeExportRequest(BaseModel):
    """Request to export recipe as code"""
    recipe_id: str
    language: str = Field(default="python", pattern="^(python|sql|r)$")


class RecipeExportResponse(BaseModel):
    """Response containing exported code"""
    recipe_name: str
    language: str
    code: str


class TransformationHistoryResponse(BaseModel):
    """Response containing transformation history"""
    transformations: List[Dict[str, Any]]
    total: int


class AutoCleanRequest(BaseModel):
    """Request for one-click auto-clean"""
    dataset_id: str
    options: Dict[str, Any] = Field(
        default_factory=lambda: {
            "remove_duplicates": True,
            "trim_whitespace": True,
            "handle_missing": "drop",  # drop, impute, flag
            "fix_casing": True,
            "standardize_dates": True,
            "handle_outliers": "keep"  # keep, cap, remove
        }
    )


class TransformationSuggestionResponse(BaseModel):
    """Response containing suggested transformations"""
    suggestions: List[Dict[str, Any]]
    data_quality_score: float
    critical_issues: List[str]


class ValidationRequest(BaseModel):
    """Request to validate transformations before applying"""
    dataset_id: str
    transformations: List[TransformationStepRequest]


class ValidationResponse(BaseModel):
    """Response from transformation validation"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    info: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)