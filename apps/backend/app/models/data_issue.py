"""
Data Issue model for MongoDB.

This model represents detected data quality issues and their suggested fixes.
It provides audit trail for issue detection and fix application.
"""

from beanie import Document, Indexed
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from beanie import PydanticObjectId
from enum import Enum


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(timezone.utc)


class IssueType(str, Enum):
    """Types of data quality issues that can be detected."""
    MISSING_VALUES = "missing_values"
    OUTLIERS = "outliers"
    INCONSISTENT_FORMAT = "inconsistent_format"
    DUPLICATES = "duplicates"
    INVALID_VALUES = "invalid_values"
    TYPE_MISMATCH = "type_mismatch"
    INCONSISTENT_CASING = "inconsistent_casing"
    WHITESPACE_ISSUES = "whitespace_issues"
    DATE_FORMAT_ISSUES = "date_format_issues"
    NUMERIC_STRING_MISMATCH = "numeric_string_mismatch"


class IssueSeverity(str, Enum):
    """Severity levels for data issues."""
    CRITICAL = "critical"  # Blocks analysis, data loss risk
    HIGH = "high"          # Significant impact on analysis
    MEDIUM = "medium"      # Moderate impact
    LOW = "low"            # Minor impact, cosmetic issues


class SuggestedFix(BaseModel):
    """A suggested fix for a data issue."""

    fix_id: str = Field(default_factory=lambda: str(PydanticObjectId()))
    transformation_type: str = Field(..., description="Type of transformation to apply")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Transformation parameters")
    explanation: str = Field(default="", description="Plain-language explanation of the fix")
    ai_generated: bool = Field(default=False, description="Whether this fix was suggested by AI")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in this fix")
    preview_impact: Optional[Dict[str, Any]] = Field(default=None, description="Preview of fix impact")
    estimated_rows_affected: int = Field(default=0, ge=0, description="Estimated rows affected")
    estimated_data_loss: float = Field(default=0.0, ge=0.0, le=100.0, description="Estimated data loss %")
    is_safe: bool = Field(default=True, description="Whether fix is safe to apply automatically")


class DataIssue(BaseModel):
    """Individual data quality issue detected in a dataset."""

    issue_id: str = Field(default_factory=lambda: str(PydanticObjectId()))
    issue_type: IssueType = Field(..., description="Type of data issue")
    severity: IssueSeverity = Field(..., description="Severity level")
    affected_column: Optional[str] = Field(None, description="Column affected by the issue")
    affected_columns: List[str] = Field(default_factory=list, description="Multiple columns affected")
    affected_rows: int = Field(default=0, ge=0, description="Number of rows affected")
    affected_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Percentage of rows affected")
    description: str = Field(..., description="Human-readable description of the issue")
    impact: str = Field(default="", description="Potential impact on analysis")
    suggested_fixes: List[SuggestedFix] = Field(default_factory=list, description="Suggested fixes for this issue")
    ai_generated: bool = Field(default=False, description="Whether detected by AI analysis")
    ai_explanation: Optional[str] = Field(None, description="AI-generated explanation")
    detected_at: datetime = Field(default_factory=get_current_time)

    # Additional metadata for context
    example_values: List[Any] = Field(default_factory=list, description="Example problematic values")
    column_stats: Optional[Dict[str, Any]] = Field(None, description="Relevant column statistics")


class AppliedFix(BaseModel):
    """Record of a fix that was applied."""

    fix_id: str = Field(..., description="ID of the applied fix")
    issue_id: str = Field(..., description="ID of the issue this fix addressed")
    transformation_type: str = Field(..., description="Type of transformation applied")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    applied_at: datetime = Field(default_factory=get_current_time)
    applied_by: str = Field(..., description="User ID who applied the fix")
    rows_affected: int = Field(default=0, ge=0)
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(None)
    rollback_available: bool = Field(default=False)


class DetectionSummary(BaseModel):
    """Summary of an issue detection run."""

    total_issues: int = Field(default=0, ge=0)
    critical_count: int = Field(default=0, ge=0)
    high_count: int = Field(default=0, ge=0)
    medium_count: int = Field(default=0, ge=0)
    low_count: int = Field(default=0, ge=0)
    ai_detected_count: int = Field(default=0, ge=0)
    auto_fixable_count: int = Field(default=0, ge=0)
    detection_time_ms: int = Field(default=0, ge=0)
    columns_analyzed: int = Field(default=0, ge=0)
    rows_analyzed: int = Field(default=0, ge=0)


class DataIssueRecord(Document):
    """
    MongoDB document for storing detected issues and fix history.

    This document provides an audit trail of:
    - Detected data quality issues
    - Suggested fixes
    - Applied fixes and their results
    """

    # Ownership and identification
    dataset_id: Indexed(str) = Field(..., description="Dataset these issues belong to")
    user_id: Indexed(str) = Field(..., description="User who owns this dataset")

    # Detection results
    issues: List[DataIssue] = Field(default_factory=list, description="Detected issues")
    summary: DetectionSummary = Field(default_factory=DetectionSummary)

    # Fix history
    applied_fixes: List[AppliedFix] = Field(default_factory=list, description="History of applied fixes")

    # Detection options used
    detection_options: Dict[str, Any] = Field(default_factory=dict)
    include_ai_analysis: bool = Field(default=True)

    # Timestamps
    detected_at: datetime = Field(default_factory=get_current_time)
    last_updated: datetime = Field(default_factory=get_current_time)

    # Versioning
    version: int = Field(default=1, ge=1, description="Record version for optimistic locking")

    class Settings:
        name = "data_issues"
        indexes = [
            "dataset_id",
            "user_id",
            "detected_at",
            [("dataset_id", 1), ("detected_at", -1)],
            [("user_id", 1), ("detected_at", -1)],
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    def add_issue(self, issue: DataIssue) -> None:
        """Add a detected issue."""
        self.issues.append(issue)
        self._update_summary()
        self.last_updated = get_current_time()

    def add_applied_fix(self, fix: AppliedFix) -> None:
        """Record an applied fix."""
        self.applied_fixes.append(fix)
        self.last_updated = get_current_time()
        self.version += 1

    def get_issues_by_severity(self, severity: IssueSeverity) -> List[DataIssue]:
        """Get issues filtered by severity."""
        return [issue for issue in self.issues if issue.severity == severity]

    def get_issues_by_type(self, issue_type: IssueType) -> List[DataIssue]:
        """Get issues filtered by type."""
        return [issue for issue in self.issues if issue.issue_type == issue_type]

    def get_auto_fixable_issues(self) -> List[DataIssue]:
        """Get issues that have safe automatic fixes."""
        return [
            issue for issue in self.issues
            if any(fix.is_safe for fix in issue.suggested_fixes)
        ]

    def _update_summary(self) -> None:
        """Update the detection summary based on current issues."""
        self.summary.total_issues = len(self.issues)
        self.summary.critical_count = len(self.get_issues_by_severity(IssueSeverity.CRITICAL))
        self.summary.high_count = len(self.get_issues_by_severity(IssueSeverity.HIGH))
        self.summary.medium_count = len(self.get_issues_by_severity(IssueSeverity.MEDIUM))
        self.summary.low_count = len(self.get_issues_by_severity(IssueSeverity.LOW))
        self.summary.ai_detected_count = len([i for i in self.issues if i.ai_generated])
        self.summary.auto_fixable_count = len(self.get_auto_fixable_issues())

    def mark_issue_fixed(self, issue_id: str) -> bool:
        """Mark an issue as fixed (removes from active issues list)."""
        original_count = len(self.issues)
        self.issues = [i for i in self.issues if i.issue_id != issue_id]
        if len(self.issues) < original_count:
            self._update_summary()
            self.last_updated = get_current_time()
            return True
        return False
