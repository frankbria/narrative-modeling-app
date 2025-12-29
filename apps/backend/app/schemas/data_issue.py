"""
Pydantic schemas for Data Issue API endpoints.

These schemas define request/response models for data issue detection
and fix suggestion operations.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Import types from models - SINGLE SOURCE OF TRUTH


# Request Schemas

class DetectionOptions(BaseModel):
    """Options for issue detection."""

    include_ai_analysis: bool = Field(default=True, description="Include AI-powered analysis")
    check_missing_values: bool = Field(default=True, description="Check for missing values")
    check_duplicates: bool = Field(default=True, description="Check for duplicate rows")
    check_outliers: bool = Field(default=True, description="Check for outliers")
    check_inconsistencies: bool = Field(default=True, description="Check for format inconsistencies")
    check_type_mismatches: bool = Field(default=True, description="Check for type mismatches")
    outlier_method: str = Field(default="iqr", description="Outlier detection method: iqr, zscore")
    outlier_threshold: float = Field(default=1.5, ge=1.0, le=5.0, description="Outlier detection threshold")
    columns: Optional[List[str]] = Field(None, description="Specific columns to analyze (None = all)")
    sample_size: Optional[int] = Field(None, ge=100, le=100000, description="Sample size for large datasets")


class IssueDetectionRequest(BaseModel):
    """Request schema for issue detection."""

    dataset_id: str = Field(..., description="ID of the dataset to analyze")
    options: DetectionOptions = Field(default_factory=DetectionOptions, description="Detection options")


class FixPreviewRequest(BaseModel):
    """Request schema for previewing a fix."""

    dataset_id: str = Field(..., description="Dataset ID")
    issue_id: str = Field(..., description="ID of the issue to fix")
    fix_id: Optional[str] = Field(None, description="Specific fix ID (uses first suggested if not provided)")
    preview_rows: int = Field(default=100, ge=10, le=1000, description="Number of rows to preview")


class FixApplicationRequest(BaseModel):
    """Request schema for applying a fix."""

    dataset_id: str = Field(..., description="Dataset ID")
    issue_id: str = Field(..., description="ID of the issue to fix")
    fix_id: Optional[str] = Field(None, description="Specific fix ID to apply")
    preview_mode: bool = Field(default=False, description="Preview only, don't apply")
    save_as_new_version: bool = Field(default=True, description="Save as new dataset version")


class BatchFixRequest(BaseModel):
    """Request schema for applying multiple fixes."""

    dataset_id: str = Field(..., description="Dataset ID")
    issue_ids: List[str] = Field(..., description="List of issue IDs to fix")
    auto_apply_safe: bool = Field(default=False, description="Only apply fixes marked as safe")
    stop_on_error: bool = Field(default=True, description="Stop batch on first error")
    preview_mode: bool = Field(default=False, description="Preview only, don't apply")


# Response Schemas

class SuggestedFixResponse(BaseModel):
    """Response schema for a suggested fix."""

    fix_id: str = Field(..., description="Unique fix identifier")
    transformation_type: str = Field(..., description="Type of transformation")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Transformation parameters")
    explanation: str = Field(..., description="Human-readable explanation")
    ai_generated: bool = Field(default=False, description="Whether AI suggested this fix")
    confidence_score: float = Field(default=1.0, description="Confidence in this fix")
    estimated_rows_affected: int = Field(default=0, description="Estimated rows affected")
    estimated_data_loss: float = Field(default=0.0, description="Estimated data loss percentage")
    is_safe: bool = Field(default=True, description="Safe for automatic application")


class DataIssueResponse(BaseModel):
    """Response schema for a detected data issue."""

    issue_id: str = Field(..., description="Unique issue identifier")
    issue_type: str = Field(..., description="Type of data issue")
    severity: str = Field(..., description="Severity level")
    affected_column: Optional[str] = Field(None, description="Affected column name")
    affected_columns: List[str] = Field(default_factory=list, description="Multiple affected columns")
    affected_rows: int = Field(default=0, description="Number of affected rows")
    affected_percentage: float = Field(default=0.0, description="Percentage of rows affected")
    description: str = Field(..., description="Issue description")
    impact: str = Field(default="", description="Potential impact on analysis")
    suggested_fixes: List[SuggestedFixResponse] = Field(default_factory=list)
    ai_generated: bool = Field(default=False, description="Detected by AI")
    ai_explanation: Optional[str] = Field(None, description="AI-generated explanation")
    detected_at: datetime = Field(..., description="When issue was detected")
    example_values: List[Any] = Field(default_factory=list, description="Example problematic values")


class DetectionSummaryResponse(BaseModel):
    """Response schema for detection summary."""

    total_issues: int = Field(default=0, description="Total issues detected")
    critical_count: int = Field(default=0, description="Critical severity count")
    high_count: int = Field(default=0, description="High severity count")
    medium_count: int = Field(default=0, description="Medium severity count")
    low_count: int = Field(default=0, description="Low severity count")
    ai_detected_count: int = Field(default=0, description="AI-detected issues count")
    auto_fixable_count: int = Field(default=0, description="Auto-fixable issues count")
    detection_time_ms: int = Field(default=0, description="Detection time in milliseconds")
    columns_analyzed: int = Field(default=0, description="Number of columns analyzed")
    rows_analyzed: int = Field(default=0, description="Number of rows analyzed")


class IssueDetectionResponse(BaseModel):
    """Response schema for issue detection."""

    success: bool = Field(default=True, description="Whether detection succeeded")
    dataset_id: str = Field(..., description="Dataset ID")
    issues: List[DataIssueResponse] = Field(default_factory=list, description="Detected issues")
    summary: DetectionSummaryResponse = Field(default_factory=DetectionSummaryResponse)
    record_id: Optional[str] = Field(None, description="ID of stored detection record")
    error: Optional[str] = Field(None, description="Error message if failed")


class FixPreviewResponse(BaseModel):
    """Response schema for fix preview."""

    success: bool = Field(default=True, description="Whether preview succeeded")
    issue_id: str = Field(..., description="Issue ID")
    fix_id: str = Field(..., description="Fix ID being previewed")
    preview_data_before: Optional[List[Dict[str, Any]]] = Field(None, description="Data before fix")
    preview_data_after: Optional[List[Dict[str, Any]]] = Field(None, description="Data after fix")
    affected_rows: int = Field(default=0, description="Rows that would be affected")
    affected_columns: List[str] = Field(default_factory=list, description="Columns that would be affected")
    estimated_data_loss: float = Field(default=0.0, description="Estimated data loss")
    warnings: List[str] = Field(default_factory=list, description="Warnings about the fix")
    error: Optional[str] = Field(None, description="Error message if failed")


class FixApplicationResponse(BaseModel):
    """Response schema for fix application."""

    success: bool = Field(default=True, description="Whether fix was applied")
    dataset_id: str = Field(..., description="Dataset ID")
    issue_id: str = Field(..., description="Issue ID that was fixed")
    fix_id: str = Field(..., description="Fix ID that was applied")
    transformation_id: Optional[str] = Field(None, description="Transformation record ID")
    affected_rows: int = Field(default=0, description="Rows affected")
    affected_columns: List[str] = Field(default_factory=list, description="Columns affected")
    execution_time_ms: int = Field(default=0, description="Execution time")
    new_version_id: Optional[str] = Field(None, description="New dataset version ID if created")
    error: Optional[str] = Field(None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Warnings")


class BatchFixResult(BaseModel):
    """Result of a single fix in a batch operation."""

    issue_id: str = Field(..., description="Issue ID")
    fix_id: str = Field(..., description="Fix ID")
    success: bool = Field(default=True, description="Whether this fix succeeded")
    affected_rows: int = Field(default=0, description="Rows affected")
    error: Optional[str] = Field(None, description="Error if failed")


class BatchFixResponse(BaseModel):
    """Response schema for batch fix application."""

    success: bool = Field(default=True, description="Whether overall batch succeeded")
    dataset_id: str = Field(..., description="Dataset ID")
    total_fixes: int = Field(default=0, description="Total fixes attempted")
    successful_fixes: int = Field(default=0, description="Fixes that succeeded")
    failed_fixes: int = Field(default=0, description="Fixes that failed")
    results: List[BatchFixResult] = Field(default_factory=list, description="Per-fix results")
    total_rows_affected: int = Field(default=0, description="Total rows affected")
    execution_time_ms: int = Field(default=0, description="Total execution time")
    new_version_id: Optional[str] = Field(None, description="New dataset version ID")
    error: Optional[str] = Field(None, description="Overall error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Warnings")


class AppliedFixResponse(BaseModel):
    """Response schema for an applied fix record."""

    fix_id: str = Field(..., description="Fix ID")
    issue_id: str = Field(..., description="Issue ID")
    transformation_type: str = Field(..., description="Type of transformation")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    applied_at: datetime = Field(..., description="When fix was applied")
    applied_by: str = Field(..., description="User who applied")
    rows_affected: int = Field(default=0)
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(None)


class IssueHistoryResponse(BaseModel):
    """Response schema for issue detection history."""

    record_id: str = Field(..., description="Detection record ID")
    dataset_id: str = Field(..., description="Dataset ID")
    detected_at: datetime = Field(..., description="Detection timestamp")
    summary: DetectionSummaryResponse = Field(...)
    issues_count: int = Field(default=0, description="Number of issues detected")
    applied_fixes_count: int = Field(default=0, description="Number of fixes applied")


class IssueHistoryListResponse(BaseModel):
    """Response schema for list of issue detection history."""

    records: List[IssueHistoryResponse] = Field(default_factory=list)
    total: int = Field(default=0, description="Total records")
    page: int = Field(default=1)
    per_page: int = Field(default=20)
