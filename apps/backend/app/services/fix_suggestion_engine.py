"""
Fix Suggestion Engine.

This service generates, validates, and applies fix suggestions for data issues.
It integrates with the TransformationEngine to execute fixes.
"""

import logging
from typing import Any

import pandas as pd

from app.models.data_issue import (
    AppliedFix,
    DataIssue,
    IssueType,
    SuggestedFix,
)
from app.models.transformation import TransformationType
from app.services.exceptions import OperationError, ValidationError
from app.services.transformation_engine.transformation_engine import (
    TransformationEngine,
)

logger = logging.getLogger(__name__)


# Maximum data loss threshold for automatic/safe fixes
MAX_SAFE_DATA_LOSS_PERCENT = 5.0


class FixSuggestionEngine:
    """
    Engine for generating, validating, and applying data fix suggestions.

    This engine maps data issues to appropriate transformations and handles
    the execution of fixes through the TransformationEngine.
    """

    def __init__(self) -> None:
        """Initialize the fix suggestion engine."""
        self.transformation_engine = TransformationEngine()

        # Mapping of issue types to supported transformation types
        self._issue_to_transformation_map: dict[IssueType, list[str]] = {
            IssueType.MISSING_VALUES: [
                "fill_missing", "drop_missing",
                "impute_mean", "impute_median", "impute_mode"
            ],
            IssueType.DUPLICATES: ["remove_duplicates"],
            IssueType.OUTLIERS: ["outlier_removal", "filter"],
            IssueType.INCONSISTENT_FORMAT: [
                "standardize_format", "regex_replace"
            ],
            IssueType.INCONSISTENT_CASING: ["fix_casing"],
            IssueType.WHITESPACE_ISSUES: ["trim_whitespace"],
            IssueType.DATE_FORMAT_ISSUES: ["to_datetime"],
            IssueType.TYPE_MISMATCH: [
                "to_numeric", "to_string", "to_datetime", "to_boolean"
            ],
            IssueType.INVALID_VALUES: ["filter", "fill_missing"],
        }

    def get_supported_transformations(
        self,
        issue_type: IssueType
    ) -> list[str]:
        """Get supported transformation types for an issue type."""
        return self._issue_to_transformation_map.get(issue_type, [])

    def suggest_fixes_for_issue(
        self,
        issue: DataIssue,
        df: pd.DataFrame,
        column_types: dict[str, str],
    ) -> list[SuggestedFix]:
        """
        Generate fix suggestions for a specific issue.

        Args:
            issue: The data issue to suggest fixes for
            df: The DataFrame containing the data
            column_types: Column type mappings

        Returns:
            List of suggested fixes
        """
        fixes: list[SuggestedFix] = []

        if issue.issue_type == IssueType.MISSING_VALUES:
            fixes = self._suggest_missing_value_fixes(issue, df, column_types)

        elif issue.issue_type == IssueType.DUPLICATES:
            fixes = self._suggest_duplicate_fixes(issue)

        elif issue.issue_type == IssueType.OUTLIERS:
            fixes = self._suggest_outlier_fixes(issue, df)

        elif issue.issue_type == IssueType.WHITESPACE_ISSUES:
            fixes = self._suggest_whitespace_fixes(issue)

        elif issue.issue_type == IssueType.INCONSISTENT_CASING:
            fixes = self._suggest_casing_fixes(issue, df)

        elif issue.issue_type == IssueType.DATE_FORMAT_ISSUES:
            fixes = self._suggest_date_fixes(issue)

        elif issue.issue_type == IssueType.TYPE_MISMATCH:
            fixes = self._suggest_type_conversion_fixes(issue, column_types)

        elif issue.issue_type == IssueType.INCONSISTENT_FORMAT:
            fixes = self._suggest_format_fixes(issue, df)

        # Calculate estimated impact for each fix
        for fix in fixes:
            if fix.estimated_rows_affected == 0:
                fix.estimated_rows_affected = issue.affected_rows
            fix.is_safe = self._is_fix_safe(fix, issue)

        return fixes

    def _suggest_missing_value_fixes(
        self,
        issue: DataIssue,
        df: pd.DataFrame,
        column_types: dict[str, str],
    ) -> list[SuggestedFix]:
        """Suggest fixes for missing values."""
        fixes: list[SuggestedFix] = []
        col = issue.affected_column

        if not col or col not in df.columns:
            return fixes

        col_type = column_types.get(col, "unknown")

        if col_type in ["integer", "float"]:
            # Calculate actual values for better suggestions
            series = pd.to_numeric(df[col], errors='coerce')
            mean_val = series.mean()
            median_val = series.median()

            # Format mean explanation, handling NaN case
            if pd.isna(mean_val):
                mean_explanation = "Fill missing values with mean (no numeric values available)"
                mean_preview_impact: dict[str, Any] = {"fill_value": None}
            else:
                mean_explanation = f"Fill missing values with mean ({mean_val:.2f})"
                mean_preview_impact = {"fill_value": float(mean_val)}

            fixes.append(SuggestedFix(
                transformation_type="fill_missing",
                parameters={"columns": [col], "method": "mean"},
                explanation=mean_explanation,
                confidence_score=0.85,
                estimated_rows_affected=issue.affected_rows,
                preview_impact=mean_preview_impact,
            ))

            # Format median explanation, handling NaN case
            if pd.isna(median_val):
                median_explanation = "Fill missing values with median (no numeric values available)"
                median_preview_impact: dict[str, Any] = {"fill_value": None}
            else:
                median_explanation = f"Fill missing values with median ({median_val:.2f}) - more robust to outliers"
                median_preview_impact = {"fill_value": float(median_val)}

            fixes.append(SuggestedFix(
                transformation_type="fill_missing",
                parameters={"columns": [col], "method": "median"},
                explanation=median_explanation,
                confidence_score=0.85,
                estimated_rows_affected=issue.affected_rows,
                preview_impact=median_preview_impact,
            ))

        elif col_type in ["string", "categorical"]:
            mode = df[col].mode()
            mode_val = mode.iloc[0] if len(mode) > 0 else "Unknown"

            fixes.append(SuggestedFix(
                transformation_type="fill_missing",
                parameters={"columns": [col], "method": "mode"},
                explanation=f"Fill missing values with most frequent value ('{mode_val}')",
                confidence_score=0.75,
                estimated_rows_affected=issue.affected_rows,
                preview_impact={"fill_value": str(mode_val)},
            ))

            fixes.append(SuggestedFix(
                transformation_type="fill_missing",
                parameters={"columns": [col], "value": "Unknown"},
                explanation="Fill missing values with 'Unknown'",
                confidence_score=0.7,
                estimated_rows_affected=issue.affected_rows,
            ))

        # Drop rows option - always available
        if issue.affected_percentage <= 20:
            fixes.append(SuggestedFix(
                transformation_type="drop_missing",
                parameters={"columns": [col], "how": "any"},
                explanation=f"Remove rows with missing values ({issue.affected_percentage:.1f}% of data)",
                confidence_score=0.6,
                estimated_rows_affected=issue.affected_rows,
                estimated_data_loss=issue.affected_percentage,
            ))

        return fixes

    def _suggest_duplicate_fixes(self, issue: DataIssue) -> list[SuggestedFix]:
        """Suggest fixes for duplicate rows."""
        return [
            SuggestedFix(
                transformation_type="remove_duplicates",
                parameters={"keep": "first"},
                explanation="Remove duplicates, keeping the first occurrence of each",
                confidence_score=0.9,
                estimated_rows_affected=issue.affected_rows,
            ),
            SuggestedFix(
                transformation_type="remove_duplicates",
                parameters={"keep": "last"},
                explanation="Remove duplicates, keeping the last occurrence of each",
                confidence_score=0.85,
                estimated_rows_affected=issue.affected_rows,
            ),
        ]

    def _suggest_outlier_fixes(
        self,
        issue: DataIssue,
        df: pd.DataFrame
    ) -> list[SuggestedFix]:
        """Suggest fixes for outliers."""
        fixes: list[SuggestedFix] = []
        col = issue.affected_column

        # Cap/floor method (preserves all rows)
        fixes.append(SuggestedFix(
            transformation_type="outlier_removal",
            parameters={
                "columns": [col],
                "method": "cap",
                "threshold": 1.5
            },
            explanation=f"Cap extreme values in '{col}' to 1.5 IQR bounds (preserves all rows)",
            confidence_score=0.85,
            estimated_rows_affected=issue.affected_rows,
            estimated_data_loss=0.0,
        ))

        # Remove outliers (only if small percentage)
        if issue.affected_percentage < 10:
            fixes.append(SuggestedFix(
                transformation_type="outlier_removal",
                parameters={
                    "columns": [col],
                    "method": "remove",
                    "threshold": 1.5
                },
                explanation=f"Remove outlier rows from '{col}' using IQR method",
                confidence_score=0.7,
                estimated_rows_affected=issue.affected_rows,
                estimated_data_loss=issue.affected_percentage,
            ))

        return fixes

    def _suggest_whitespace_fixes(self, issue: DataIssue) -> list[SuggestedFix]:
        """Suggest fixes for whitespace issues."""
        # Guard against None affected_column
        if issue.affected_column is None:
            return []

        return [
            SuggestedFix(
                transformation_type="trim_whitespace",
                parameters={"columns": [issue.affected_column]},
                explanation=f"Remove leading and trailing whitespace from '{issue.affected_column}'",
                confidence_score=0.95,
                estimated_rows_affected=issue.affected_rows,
            ),
        ]

    def _suggest_casing_fixes(
        self,
        issue: DataIssue,
        df: pd.DataFrame
    ) -> list[SuggestedFix]:
        """Suggest fixes for inconsistent casing."""
        col = issue.affected_column
        fixes = []

        # Analyze current casing distribution
        if col and col in df.columns:
            series = df[col].dropna().astype(str)
            lower_count = series.str.islower().sum()
            upper_count = series.str.isupper().sum()
            title_count = series.str.istitle().sum()

            # Suggest based on majority casing
            if lower_count >= upper_count and lower_count >= title_count:
                suggested_casing = "lower"
                explanation = f"Convert to lowercase (matches {lower_count} existing values)"
            elif upper_count >= title_count:
                suggested_casing = "upper"
                explanation = f"Convert to uppercase (matches {upper_count} existing values)"
            else:
                suggested_casing = "title"
                explanation = f"Convert to title case (matches {title_count} existing values)"

            fixes.append(SuggestedFix(
                transformation_type="fix_casing",
                parameters={"columns": [col], "casing": suggested_casing},
                explanation=explanation,
                confidence_score=0.85,
                estimated_rows_affected=issue.affected_rows,
            ))

        # Always include standard options
        for casing in ["lower", "upper", "title"]:
            if not any(f.parameters.get("casing") == casing for f in fixes):
                fixes.append(SuggestedFix(
                    transformation_type="fix_casing",
                    parameters={"columns": [issue.affected_column], "casing": casing},
                    explanation=f"Standardize to {casing}case",
                    confidence_score=0.7,
                    estimated_rows_affected=issue.affected_rows,
                ))

        return fixes[:3]  # Return top 3 suggestions

    def _suggest_date_fixes(self, issue: DataIssue) -> list[SuggestedFix]:
        """Suggest fixes for date format issues."""
        return [
            SuggestedFix(
                transformation_type="to_datetime",
                parameters={
                    "columns": [issue.affected_column],
                    "errors": "coerce"
                },
                explanation=f"Parse '{issue.affected_column}' as datetime (invalid values become null)",
                confidence_score=0.75,
                estimated_rows_affected=issue.affected_rows,
                estimated_data_loss=issue.affected_percentage,
            ),
            SuggestedFix(
                transformation_type="standardize_format",
                parameters={
                    "columns": [issue.affected_column],
                    "format": "ISO8601"
                },
                explanation=f"Standardize date format in '{issue.affected_column}' to ISO 8601",
                confidence_score=0.7,
                estimated_rows_affected=issue.affected_rows,
            ),
        ]

    def _suggest_type_conversion_fixes(
        self,
        issue: DataIssue,
        column_types: dict[str, str]
    ) -> list[SuggestedFix]:
        """Suggest fixes for type mismatches."""
        fixes: list[SuggestedFix] = []
        col = issue.affected_column
        if not col:
            return fixes
        expected_type = column_types.get(col, "unknown")

        if expected_type in ["integer", "float"]:
            fixes.append(SuggestedFix(
                transformation_type="to_numeric",
                parameters={
                    "columns": [col],
                    "errors": "coerce"
                },
                explanation=f"Convert '{col}' to numeric (invalid values become null)",
                confidence_score=0.8,
                estimated_rows_affected=issue.affected_rows,
            ))
        elif expected_type == "boolean":
            fixes.append(SuggestedFix(
                transformation_type="to_boolean",
                parameters={"columns": [col]},
                explanation=f"Convert '{col}' to boolean",
                confidence_score=0.75,
                estimated_rows_affected=issue.affected_rows,
            ))

        return fixes

    def _suggest_format_fixes(
        self,
        issue: DataIssue,
        df: pd.DataFrame
    ) -> list[SuggestedFix]:
        """Suggest fixes for format inconsistencies."""
        return [
            SuggestedFix(
                transformation_type="standardize_format",
                parameters={"columns": issue.affected_columns or [issue.affected_column]},
                explanation="Standardize format based on detected patterns",
                confidence_score=0.6,
                estimated_rows_affected=issue.affected_rows,
            ),
        ]

    def _is_fix_safe(self, fix: SuggestedFix, issue: DataIssue) -> bool:
        """Determine if a fix is safe for automatic application."""
        # Check data loss threshold
        if fix.estimated_data_loss > MAX_SAFE_DATA_LOSS_PERCENT:
            return False

        # Safe transformations that don't lose data
        safe_types = {
            "trim_whitespace",
            "fix_casing",
            "fill_missing",  # Fills, doesn't remove
        }

        if fix.transformation_type in safe_types:
            return True

        # Duplicates removal is safe if it's removing true duplicates
        if fix.transformation_type == "remove_duplicates":
            return True

        # Outlier capping is safe (doesn't remove rows)
        if (fix.transformation_type == "outlier_removal" and
                fix.parameters.get("method") == "cap"):
            return True

        return False

    def preview_fix(
        self,
        df: pd.DataFrame,
        issue: DataIssue,
        fix: SuggestedFix,
        n_rows: int = 100,
    ) -> dict[str, Any]:
        """
        Preview a fix before applying it.

        This is a synchronous method performing CPU-bound DataFrame operations.

        Args:
            df: The DataFrame
            issue: The issue being fixed
            fix: The fix to preview
            n_rows: Number of rows to show in preview

        Returns:
            Dictionary with preview data and statistics
        """
        try:
            # Get transformation type enum
            try:
                trans_type = TransformationType(fix.transformation_type)
            except ValueError:
                # Use a compatible transformation or return error
                return {
                    "success": False,
                    "error": f"Transformation type '{fix.transformation_type}' not implemented in engine"
                }

            # Preview the transformation
            result = self.transformation_engine.preview_transformation(
                df=df,
                transformation_type=trans_type,
                parameters=fix.parameters,
                n_rows=n_rows,
            )

            if not result.success:
                return {
                    "success": False,
                    "error": result.error
                }

            # Get before data for comparison
            sample_before = df.head(n_rows).to_dict('records')

            return {
                "success": True,
                "preview_data_before": sample_before,
                "preview_data_after": result.preview_data,
                "affected_rows": result.affected_rows,
                "affected_columns": result.affected_columns,
                "stats_before": result.stats_before,
                "stats_after": result.stats_after,
                "warnings": result.warnings,
            }

        except Exception as e:
            logger.error(f"Fix preview failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def apply_fix(
        self,
        df: pd.DataFrame,
        issue: DataIssue,
        fix: SuggestedFix,
        user_id: str,
    ) -> tuple[pd.DataFrame, AppliedFix]:
        """
        Apply a fix to the DataFrame.

        This is a synchronous method performing CPU-bound DataFrame transformations.

        Args:
            df: The DataFrame to transform
            issue: The issue being fixed
            fix: The fix to apply
            user_id: ID of user applying the fix

        Returns:
            Tuple of (transformed DataFrame, applied fix record)
        """
        try:
            # Get transformation type enum
            try:
                trans_type = TransformationType(fix.transformation_type)
            except ValueError:
                raise ValidationError(
                    f"Transformation type '{fix.transformation_type}' not supported"
                )

            # Apply the transformation
            result = self.transformation_engine.apply_transformation(
                df=df,
                transformation_type=trans_type,
                parameters=fix.parameters,
            )

            if not result.success:
                applied_fix = AppliedFix(
                    fix_id=fix.fix_id,
                    issue_id=issue.issue_id,
                    transformation_type=fix.transformation_type,
                    parameters=fix.parameters,
                    applied_by=user_id,
                    rows_affected=0,
                    success=False,
                    error_message=result.error,
                )
                raise OperationError(
                    message=f"Failed to apply fix: {result.error}",
                    operation="apply_fix"
                )

            # Create transformed DataFrame
            transformed_df = pd.DataFrame(result.transformed_data)

            # Create applied fix record
            applied_fix = AppliedFix(
                fix_id=fix.fix_id,
                issue_id=issue.issue_id,
                transformation_type=fix.transformation_type,
                parameters=fix.parameters,
                applied_by=user_id,
                rows_affected=result.affected_rows,
                success=True,
                rollback_available=True,
            )

            return transformed_df, applied_fix

        except ValidationError:
            raise
        except OperationError:
            raise
        except Exception as e:
            logger.error(f"Apply fix failed: {str(e)}")
            raise OperationError(
                message=f"Failed to apply fix: {str(e)}",
                operation="apply_fix",
                original_error=e
            )

    def validate_fix_safety(
        self,
        fix: SuggestedFix,
        df: pd.DataFrame,
    ) -> tuple[bool, list[str]]:
        """
        Validate if a fix is safe to apply.

        Args:
            fix: The fix to validate
            df: The DataFrame

        Returns:
            Tuple of (is_safe, list of warnings)
        """
        warnings: list[str] = []
        is_safe = True

        # Check data loss
        if fix.estimated_data_loss > MAX_SAFE_DATA_LOSS_PERCENT:
            warnings.append(
                f"This fix may result in {fix.estimated_data_loss:.1f}% data loss"
            )
            is_safe = False

        # Check if operation would remove all rows
        if fix.transformation_type == "drop_missing":
            columns_list = fix.parameters.get("columns", [])
            col = columns_list[0] if columns_list else None
            if col and col in df.columns:
                rows_to_drop = df[col].isna().sum()
                if rows_to_drop >= len(df):
                    warnings.append("This operation would remove all rows from the dataset")
                    is_safe = False
                elif rows_to_drop > len(df) * 0.5:
                    warnings.append(f"This operation would remove over 50% of rows ({rows_to_drop}/{len(df)})")

        # Check for potentially destructive operations
        destructive_ops = ["filter", "outlier_removal"]
        if fix.transformation_type in destructive_ops and fix.parameters.get("method") != "cap":
            warnings.append("This operation may remove rows from your dataset")

        return is_safe, warnings

    async def apply_batch_fixes(
        self,
        df: pd.DataFrame,
        issues: list[DataIssue],
        user_id: str,
        auto_apply_safe_only: bool = False,
        stop_on_error: bool = True,
    ) -> tuple[pd.DataFrame, list[AppliedFix], list[str]]:
        """
        Apply multiple fixes in batch.

        Args:
            df: The DataFrame
            issues: List of issues with fixes to apply
            user_id: User applying fixes
            auto_apply_safe_only: Only apply safe fixes
            stop_on_error: Stop on first error

        Returns:
            Tuple of (transformed DataFrame, list of applied fixes, list of errors)
        """
        applied_fixes: list[AppliedFix] = []
        errors: list[str] = []
        current_df = df.copy()

        for issue in issues:
            if not issue.suggested_fixes:
                continue

            # Get the first suggested fix (or first safe fix)
            fix_to_apply = None
            for fix in issue.suggested_fixes:
                if auto_apply_safe_only and not fix.is_safe:
                    continue
                fix_to_apply = fix
                break

            if not fix_to_apply:
                if auto_apply_safe_only:
                    errors.append(f"No safe fix available for issue {issue.issue_id}")
                continue

            try:
                current_df, applied_fix = self.apply_fix(
                    current_df, issue, fix_to_apply, user_id
                )
                applied_fixes.append(applied_fix)

            except (ValidationError, OperationError) as e:
                error_msg = f"Fix for issue {issue.issue_id} failed: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

                if stop_on_error:
                    break

        return current_df, applied_fixes, errors
