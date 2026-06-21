"""
Data Issue Detection Service.

This service orchestrates the detection of data quality issues using both
rule-based analysis (via QualityAssessmentService) and AI-powered analysis.
"""

import logging
import time
from typing import Any

import numpy as np
import pandas as pd

from app.models.data_issue import (
    DataIssue,
    DataIssueRecord,
    DetectionSummary,
    IssueSeverity,
    IssueType,
    SuggestedFix,
)
from app.schemas.data_issue import DetectionOptions
from app.services.data_processing.quality_assessment import (
    QualityAssessmentService,
    QualityDimension,
    QualityIssue,
)

logger = logging.getLogger(__name__)


class DataIssueDetectionService:
    """
    Service for detecting data quality issues.

    Combines rule-based detection from QualityAssessmentService with
    AI-powered semantic analysis for comprehensive issue detection.
    """

    def __init__(self):
        """Initialize the detection service."""
        self.quality_service = QualityAssessmentService()
        self._severity_thresholds = {
            "critical": 0.5,   # >50% affected
            "high": 0.3,       # 30-50% affected
            "medium": 0.1,     # 10-30% affected
            "low": 0.0         # <10% affected
        }

    async def detect_issues(
        self,
        df: pd.DataFrame,
        column_types: dict[str, str],
        options: DetectionOptions | None = None,
        include_ai_analysis: bool = True,
    ) -> tuple[list[DataIssue], DetectionSummary]:
        """
        Detect data quality issues in a DataFrame.

        Args:
            df: Input DataFrame to analyze
            column_types: Dictionary mapping column names to types
            options: Detection options for customization
            include_ai_analysis: Whether to include AI-powered analysis

        Returns:
            Tuple of (list of detected issues, detection summary)
        """
        start_time = time.time()
        options = options or DetectionOptions()
        all_issues: list[DataIssue] = []

        # Sample large datasets for performance
        sample_df = self._create_sample(df, options.sample_size)

        try:
            # 1. Rule-based detection using QualityAssessmentService
            if any([
                options.check_missing_values,
                options.check_duplicates,
                options.check_inconsistencies,
                options.check_type_mismatches,
            ]):
                rule_issues = await self._detect_rule_based_issues(
                    sample_df, column_types, options
                )
                all_issues.extend(rule_issues)

            # 2. Outlier detection (separate from quality assessment)
            if options.check_outliers:
                outlier_issues = self._detect_outliers(
                    sample_df, column_types, options
                )
                all_issues.extend(outlier_issues)

            # 3. Additional format-specific checks
            format_issues = self._detect_format_issues(sample_df, column_types)
            all_issues.extend(format_issues)

            # 4. AI-powered analysis (optional)
            if include_ai_analysis and options.include_ai_analysis:
                try:
                    from app.utils.ai_issue_analyzer import AIIssueAnalyzer
                    ai_analyzer = AIIssueAnalyzer()
                    ai_issues = await ai_analyzer.analyze_data_patterns(
                        sample_df, column_types, all_issues
                    )
                    all_issues.extend(ai_issues)
                except ImportError:
                    logger.warning("AI Issue Analyzer not available, skipping AI analysis")
                except Exception as e:
                    logger.error(f"AI analysis failed: {str(e)}")

            # 5. Generate fix suggestions for each issue
            for issue in all_issues:
                if not issue.suggested_fixes:
                    fixes = self._generate_fix_suggestions(issue, sample_df, column_types)
                    issue.suggested_fixes = fixes

            # Calculate summary
            detection_time_ms = int((time.time() - start_time) * 1000)
            summary = self._create_summary(
                all_issues,
                detection_time_ms,
                len(df.columns),
                len(sample_df)
            )

            return all_issues, summary

        except Exception as e:
            logger.error(f"Issue detection failed: {str(e)}")
            raise

    async def _detect_rule_based_issues(
        self,
        df: pd.DataFrame,
        column_types: dict[str, str],
        options: DetectionOptions,
    ) -> list[DataIssue]:
        """Use QualityAssessmentService for rule-based detection."""
        issues: list[DataIssue] = []

        # Run quality assessment
        quality_report = await self.quality_service.assess_quality(df, column_types)

        # Convert QualityIssue to DataIssue
        all_quality_issues = quality_report.critical_issues + quality_report.warnings

        for qi in all_quality_issues:
            # Filter based on options
            if not self._should_include_issue(qi, options):
                continue

            issue = self._convert_quality_issue(qi, df)
            issues.append(issue)

        return issues

    def _should_include_issue(
        self,
        qi: QualityIssue,
        options: DetectionOptions
    ) -> bool:
        """Check if issue should be included based on options."""
        if qi.dimension == QualityDimension.COMPLETENESS:
            return options.check_missing_values
        elif qi.dimension == QualityDimension.UNIQUENESS:
            return options.check_duplicates
        elif qi.dimension == QualityDimension.CONSISTENCY:
            return options.check_inconsistencies
        elif qi.dimension == QualityDimension.VALIDITY:
            return options.check_type_mismatches
        return True

    def _convert_quality_issue(
        self,
        qi: QualityIssue,
        df: pd.DataFrame
    ) -> DataIssue:
        """Convert a QualityIssue to a DataIssue."""
        # Map dimension to issue type
        type_mapping = {
            QualityDimension.COMPLETENESS: IssueType.MISSING_VALUES,
            QualityDimension.UNIQUENESS: IssueType.DUPLICATES,
            QualityDimension.CONSISTENCY: IssueType.INCONSISTENT_FORMAT,
            QualityDimension.VALIDITY: IssueType.INVALID_VALUES,
        }

        # Map severity
        severity_mapping = {
            "high": IssueSeverity.HIGH,
            "medium": IssueSeverity.MEDIUM,
            "low": IssueSeverity.LOW,
        }

        issue_type = type_mapping.get(qi.dimension, IssueType.INVALID_VALUES)
        severity = severity_mapping.get(qi.severity, IssueSeverity.MEDIUM)

        # Get example values if column exists
        example_values = []
        if qi.column and qi.column in df.columns:
            example_values = self._get_example_problematic_values(
                df[qi.column], issue_type
            )

        return DataIssue(
            issue_type=issue_type,
            severity=severity,
            affected_column=qi.column,
            affected_columns=[qi.column] if qi.column else [],
            affected_rows=qi.affected_rows,
            affected_percentage=qi.affected_percentage,
            description=qi.description,
            impact=self._get_impact_description(issue_type, qi.affected_percentage),
            example_values=example_values,
            ai_generated=False,
        )

    def _detect_outliers(
        self,
        df: pd.DataFrame,
        column_types: dict[str, str],
        options: DetectionOptions,
    ) -> list[DataIssue]:
        """Detect outliers in numeric columns."""
        issues: list[DataIssue] = []
        numeric_cols = [
            col for col, dtype in column_types.items()
            if dtype in ["integer", "float"] and col in df.columns
        ]

        for col in numeric_cols:
            series = pd.to_numeric(df[col], errors='coerce').dropna()
            if len(series) < 10:  # Skip small samples
                continue

            outliers = self._find_outliers(
                series,
                method=options.outlier_method,
                threshold=options.outlier_threshold
            )

            if len(outliers) > 0:
                outlier_pct = (len(outliers) / len(series)) * 100
                severity = self._get_severity_from_percentage(outlier_pct)

                issues.append(DataIssue(
                    issue_type=IssueType.OUTLIERS,
                    severity=severity,
                    affected_column=col,
                    affected_columns=[col],
                    affected_rows=len(outliers),
                    affected_percentage=outlier_pct,
                    description=f"Found {len(outliers)} outliers in column '{col}' ({outlier_pct:.1f}% of values)",
                    impact=f"Outliers may skew statistical analysis and model training for '{col}'",
                    example_values=list(outliers[:5]),
                    column_stats={
                        "mean": float(series.mean()),
                        "std": float(series.std()),
                        "min": float(series.min()),
                        "max": float(series.max()),
                        "median": float(series.median()),
                    },
                    ai_generated=False,
                ))

        return issues

    def _find_outliers(
        self,
        series: pd.Series,
        method: str = "iqr",
        threshold: float = 1.5
    ) -> pd.Series:
        """Find outliers using specified method."""
        if method == "iqr":
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr
            return series[(series < lower_bound) | (series > upper_bound)]
        elif method == "zscore":
            from scipy import stats
            z_scores = np.abs(stats.zscore(series))
            return series[z_scores > threshold]
        else:
            return pd.Series([])

    def _detect_format_issues(
        self,
        df: pd.DataFrame,
        column_types: dict[str, str],
    ) -> list[DataIssue]:
        """Detect format-specific issues like inconsistent casing, whitespace."""
        issues: list[DataIssue] = []

        for col, dtype in column_types.items():
            if col not in df.columns:
                continue

            if dtype in ["string", "categorical"]:
                # Check for whitespace issues
                whitespace_issues = self._check_whitespace_issues(df[col], col)
                if whitespace_issues:
                    issues.append(whitespace_issues)

                # Check for casing inconsistencies
                casing_issues = self._check_casing_issues(df[col], col)
                if casing_issues:
                    issues.append(casing_issues)

            elif dtype in ["date", "datetime"]:
                # Check for date format issues
                date_issues = self._check_date_format_issues(df[col], col)
                if date_issues:
                    issues.append(date_issues)

        return issues

    def _check_whitespace_issues(
        self,
        series: pd.Series,
        col_name: str
    ) -> DataIssue | None:
        """Check for leading/trailing whitespace."""
        non_null = series.dropna().astype(str)
        if len(non_null) == 0:
            return None

        has_leading = non_null.str.startswith(' ')
        has_trailing = non_null.str.endswith(' ')
        has_whitespace = has_leading | has_trailing
        count = has_whitespace.sum()

        if count > 0:
            pct = (count / len(non_null)) * 100
            return DataIssue(
                issue_type=IssueType.WHITESPACE_ISSUES,
                severity=self._get_severity_from_percentage(pct),
                affected_column=col_name,
                affected_columns=[col_name],
                affected_rows=int(count),
                affected_percentage=pct,
                description=f"Column '{col_name}' has {count} values with leading/trailing whitespace",
                impact="Whitespace can cause string matching and grouping issues",
                example_values=list(non_null[has_whitespace].head(5)),
                ai_generated=False,
            )
        return None

    def _check_casing_issues(
        self,
        series: pd.Series,
        col_name: str
    ) -> DataIssue | None:
        """Check for inconsistent casing in categorical-like columns."""
        non_null = series.dropna().astype(str)
        if len(non_null) == 0:
            return None

        unique_values = non_null.unique()
        unique_lower = pd.Series(unique_values).str.lower().unique()

        if len(unique_values) > len(unique_lower):
            duplicates = len(unique_values) - len(unique_lower)
            return DataIssue(
                issue_type=IssueType.INCONSISTENT_CASING,
                severity=IssueSeverity.LOW,
                affected_column=col_name,
                affected_columns=[col_name],
                affected_rows=duplicates,
                affected_percentage=(duplicates / len(unique_values)) * 100,
                description=f"Column '{col_name}' has {duplicates} values that differ only by casing",
                impact="Inconsistent casing may cause incorrect grouping and aggregation",
                example_values=self._find_casing_duplicates(unique_values),
                ai_generated=False,
            )
        return None

    def _find_casing_duplicates(self, values: np.ndarray) -> list[str]:
        """Find values that are duplicates when compared case-insensitively."""
        lower_map: dict[str, str] = {}
        duplicates: list[str] = []
        for v in values:
            lower = str(v).lower()
            if lower in lower_map:
                if lower_map[lower] not in duplicates:
                    duplicates.append(lower_map[lower])
                duplicates.append(str(v))
            else:
                lower_map[lower] = str(v)
        return duplicates[:5]

    def _check_date_format_issues(
        self,
        series: pd.Series,
        col_name: str
    ) -> DataIssue | None:
        """Check for inconsistent date formats."""
        non_null = series.dropna()
        if len(non_null) == 0:
            return None

        # Try to parse dates
        parsed = pd.to_datetime(non_null, errors='coerce')
        failed = parsed.isna().sum()

        if failed > 0:
            pct = (failed / len(non_null)) * 100
            return DataIssue(
                issue_type=IssueType.DATE_FORMAT_ISSUES,
                severity=self._get_severity_from_percentage(pct),
                affected_column=col_name,
                affected_columns=[col_name],
                affected_rows=int(failed),
                affected_percentage=pct,
                description=f"Column '{col_name}' has {failed} values that cannot be parsed as dates",
                impact="Unparseable dates will be treated as missing in date-based analysis",
                example_values=list(non_null[parsed.isna()].head(5)),
                ai_generated=False,
            )
        return None

    def _generate_fix_suggestions(
        self,
        issue: DataIssue,
        df: pd.DataFrame,
        column_types: dict[str, str],
    ) -> list[SuggestedFix]:
        """Generate fix suggestions for an issue."""
        fixes: list[SuggestedFix] = []

        if issue.issue_type == IssueType.MISSING_VALUES:
            fixes.extend(self._suggest_missing_value_fixes(issue, df, column_types))

        elif issue.issue_type == IssueType.DUPLICATES:
            fixes.append(SuggestedFix(
                transformation_type="remove_duplicates",
                parameters={"keep": "first"},
                explanation="Remove duplicate rows, keeping the first occurrence",
                confidence_score=0.9,
                estimated_rows_affected=issue.affected_rows,
                is_safe=True,
            ))

        elif issue.issue_type == IssueType.WHITESPACE_ISSUES:
            fixes.append(SuggestedFix(
                transformation_type="trim_whitespace",
                parameters={"columns": [issue.affected_column]},
                explanation=f"Remove leading and trailing whitespace from '{issue.affected_column}'",
                confidence_score=0.95,
                estimated_rows_affected=issue.affected_rows,
                is_safe=True,
            ))

        elif issue.issue_type == IssueType.INCONSISTENT_CASING:
            fixes.append(SuggestedFix(
                transformation_type="fix_casing",
                parameters={
                    "columns": [issue.affected_column],
                    "casing": "lower"
                },
                explanation=f"Standardize casing in '{issue.affected_column}' to lowercase",
                confidence_score=0.8,
                estimated_rows_affected=issue.affected_rows,
                is_safe=True,
            ))

        elif issue.issue_type == IssueType.OUTLIERS:
            fixes.extend(self._suggest_outlier_fixes(issue))

        elif issue.issue_type == IssueType.DATE_FORMAT_ISSUES:
            fixes.append(SuggestedFix(
                transformation_type="to_datetime",
                parameters={
                    "columns": [issue.affected_column],
                    "errors": "coerce"
                },
                explanation=f"Convert '{issue.affected_column}' to datetime, setting invalid values to null",
                confidence_score=0.7,
                estimated_rows_affected=issue.affected_rows,
                estimated_data_loss=issue.affected_percentage,
                is_safe=False,  # May result in data loss
            ))

        elif issue.issue_type in [IssueType.INCONSISTENT_FORMAT, IssueType.INVALID_VALUES]:
            # These need more context to suggest appropriate fixes
            pass

        return fixes

    def _suggest_missing_value_fixes(
        self,
        issue: DataIssue,
        df: pd.DataFrame,
        column_types: dict[str, str],
    ) -> list[SuggestedFix]:
        """Suggest fixes for missing values based on column type."""
        fixes: list[SuggestedFix] = []
        col = issue.affected_column

        if not col or col not in df.columns:
            return fixes

        col_type = column_types.get(col, "unknown")

        if col_type in ["integer", "float"]:
            # Numeric: mean, median, or drop
            fixes.append(SuggestedFix(
                transformation_type="fill_missing",
                parameters={"columns": [col], "method": "mean"},
                explanation=f"Fill missing values in '{col}' with the column mean",
                confidence_score=0.85,
                estimated_rows_affected=issue.affected_rows,
                is_safe=True,
            ))
            fixes.append(SuggestedFix(
                transformation_type="fill_missing",
                parameters={"columns": [col], "method": "median"},
                explanation=f"Fill missing values in '{col}' with the column median (robust to outliers)",
                confidence_score=0.85,
                estimated_rows_affected=issue.affected_rows,
                is_safe=True,
            ))
        elif col_type in ["string", "categorical"]:
            # Categorical: mode or constant
            fixes.append(SuggestedFix(
                transformation_type="fill_missing",
                parameters={"columns": [col], "method": "mode"},
                explanation=f"Fill missing values in '{col}' with the most frequent value",
                confidence_score=0.75,
                estimated_rows_affected=issue.affected_rows,
                is_safe=True,
            ))

        # Always offer drop option for small percentages
        if issue.affected_percentage < 20:
            fixes.append(SuggestedFix(
                transformation_type="drop_missing",
                parameters={"columns": [col]},
                explanation=f"Remove rows with missing values in '{col}' ({issue.affected_percentage:.1f}% of data)",
                confidence_score=0.7,
                estimated_rows_affected=issue.affected_rows,
                estimated_data_loss=issue.affected_percentage,
                is_safe=issue.affected_percentage < 5,
            ))

        return fixes

    def _suggest_outlier_fixes(self, issue: DataIssue) -> list[SuggestedFix]:
        """Suggest fixes for outliers."""
        fixes: list[SuggestedFix] = []
        col = issue.affected_column

        if issue.affected_percentage < 10:
            fixes.append(SuggestedFix(
                transformation_type="outlier_removal",
                parameters={
                    "columns": [col],
                    "method": "iqr",
                    "threshold": 1.5
                },
                explanation=f"Remove outliers from '{col}' using IQR method",
                confidence_score=0.6,
                estimated_rows_affected=issue.affected_rows,
                estimated_data_loss=issue.affected_percentage,
                is_safe=issue.affected_percentage < 3,
            ))

        # Cap/floor option is often safer
        fixes.append(SuggestedFix(
            transformation_type="outlier_removal",
            parameters={
                "columns": [col],
                "method": "cap",
                "threshold": 1.5
            },
            explanation=f"Cap extreme values in '{col}' to upper/lower bounds (preserves all rows)",
            confidence_score=0.8,
            estimated_rows_affected=issue.affected_rows,
            estimated_data_loss=0.0,
            is_safe=True,
        ))

        return fixes

    def _create_sample(
        self,
        df: pd.DataFrame,
        sample_size: int | None
    ) -> pd.DataFrame:
        """Create a sample of the DataFrame for analysis."""
        if sample_size is None or len(df) <= sample_size:
            return df
        return df.sample(n=sample_size, random_state=42)

    def _get_example_problematic_values(
        self,
        series: pd.Series,
        issue_type: IssueType
    ) -> list[Any]:
        """Get example values that are problematic."""
        if issue_type == IssueType.MISSING_VALUES:
            # Return indices of missing values
            return []
        elif issue_type in [IssueType.DUPLICATES]:
            # Return duplicate values
            return list(series[series.duplicated()].head(5))
        else:
            # Return some non-null values as examples
            return list(series.dropna().head(5))

    def _get_impact_description(
        self,
        issue_type: IssueType,
        percentage: float
    ) -> str:
        """Generate impact description based on issue type and severity."""
        impact_templates = {
            IssueType.MISSING_VALUES: "Missing values may cause errors in analysis and reduce model accuracy",
            IssueType.DUPLICATES: "Duplicates may inflate statistics and bias model training",
            IssueType.OUTLIERS: "Outliers may skew statistical measures and impact model predictions",
            IssueType.INCONSISTENT_FORMAT: "Format inconsistencies may cause parsing errors and incorrect grouping",
            IssueType.INVALID_VALUES: "Invalid values may cause computation errors or incorrect results",
            IssueType.TYPE_MISMATCH: "Type mismatches may cause conversion errors and data loss",
            IssueType.INCONSISTENT_CASING: "Casing inconsistencies may cause incorrect grouping and matching",
            IssueType.WHITESPACE_ISSUES: "Whitespace issues may cause string matching failures",
            IssueType.DATE_FORMAT_ISSUES: "Date format issues may cause parsing errors or data loss",
        }

        base_impact = impact_templates.get(
            issue_type,
            "This issue may affect data analysis quality"
        )

        if percentage > 50:
            severity_note = " This is a critical issue affecting over half of your data."
        elif percentage > 25:
            severity_note = " This significantly impacts your data quality."
        elif percentage > 10:
            severity_note = " This affects a moderate portion of your data."
        else:
            severity_note = ""

        return base_impact + severity_note

    def _get_severity_from_percentage(self, percentage: float) -> IssueSeverity:
        """Determine severity based on affected percentage."""
        if percentage >= self._severity_thresholds["critical"] * 100:
            return IssueSeverity.CRITICAL
        elif percentage >= self._severity_thresholds["high"] * 100:
            return IssueSeverity.HIGH
        elif percentage >= self._severity_thresholds["medium"] * 100:
            return IssueSeverity.MEDIUM
        return IssueSeverity.LOW

    def _create_summary(
        self,
        issues: list[DataIssue],
        detection_time_ms: int,
        columns_analyzed: int,
        rows_analyzed: int,
    ) -> DetectionSummary:
        """Create detection summary from issues list."""
        summary = DetectionSummary(
            total_issues=len(issues),
            critical_count=len([i for i in issues if i.severity == IssueSeverity.CRITICAL]),
            high_count=len([i for i in issues if i.severity == IssueSeverity.HIGH]),
            medium_count=len([i for i in issues if i.severity == IssueSeverity.MEDIUM]),
            low_count=len([i for i in issues if i.severity == IssueSeverity.LOW]),
            ai_detected_count=len([i for i in issues if i.ai_generated]),
            auto_fixable_count=len([
                i for i in issues
                if any(f.is_safe for f in i.suggested_fixes)
            ]),
            detection_time_ms=detection_time_ms,
            columns_analyzed=columns_analyzed,
            rows_analyzed=rows_analyzed,
        )
        return summary

    async def store_detection_results(
        self,
        dataset_id: str,
        user_id: str,
        issues: list[DataIssue],
        summary: DetectionSummary,
        options: DetectionOptions,
    ) -> DataIssueRecord:
        """Store detection results in MongoDB."""
        record = DataIssueRecord(
            dataset_id=dataset_id,
            user_id=user_id,
            issues=issues,
            summary=summary,
            detection_options=options.model_dump(),
            include_ai_analysis=options.include_ai_analysis,
        )
        await record.insert()
        return record

    async def get_latest_detection(
        self,
        dataset_id: str,
        user_id: str,
    ) -> DataIssueRecord | None:
        """Get the most recent detection record for a dataset."""
        record = await DataIssueRecord.find_one(
            DataIssueRecord.dataset_id == dataset_id,
            DataIssueRecord.user_id == user_id,
            sort=[("detected_at", -1)]
        )
        return record
