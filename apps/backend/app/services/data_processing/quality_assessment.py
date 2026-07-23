"""
Data quality assessment service for comprehensive quality scoring
"""

from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from app.models.transformation import TransformationType
from app.utils.datetime import utcnow


class QualityDimension(str, Enum):
    """Data quality dimensions"""
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    ACCURACY = "accuracy"
    VALIDITY = "validity"
    UNIQUENESS = "uniqueness"
    TIMELINESS = "timeliness"


# The five ML-readiness dimensions combined into the headline 0-100 score (issue #102).
# Timeliness is excluded — it is a hardcoded placeholder, not a measured signal.
SCORE_DIMENSIONS = (
    QualityDimension.COMPLETENESS,
    QualityDimension.VALIDITY,
    QualityDimension.CONSISTENCY,
    QualityDimension.UNIQUENESS,
    QualityDimension.ACCURACY,
)


def _recommended_transformation(issue: "QualityIssue") -> TransformationType | None:
    """Map a quality issue to the transformation that fixes it (issue #102, AC2).

    Returns the canonical TransformationType so recommendations stay tied to the
    real transformation tooling. None when no automated fix applies.
    """
    desc = issue.description.lower()
    if issue.dimension == QualityDimension.COMPLETENESS:
        return TransformationType.FILL_MISSING
    if issue.dimension == QualityDimension.UNIQUENESS:
        return TransformationType.REMOVE_DUPLICATES
    if issue.dimension == QualityDimension.VALIDITY:
        if "outlier" in desc:
            return TransformationType.OUTLIER_REMOVAL
        return TransformationType.STANDARDIZE_FORMAT
    if issue.dimension == QualityDimension.CONSISTENCY:
        if "casing" in desc:
            return TransformationType.FIX_CASING
        if "non-numeric" in desc:
            return TransformationType.TO_NUMERIC
        if "date" in desc:
            return TransformationType.TO_DATETIME
        return TransformationType.STANDARDIZE_FORMAT
    return None


class ActionableRecommendation(BaseModel):
    """A quality recommendation tied to a concrete transformation (issue #102, AC2)."""
    dimension: QualityDimension
    description: str
    transformation_type: str  # canonical TransformationType value
    affected_columns: list[str] = Field(default_factory=list)
    severity: str  # "low", "medium", "high"


class QualityIssue(BaseModel):
    """Individual quality issue identified"""
    dimension: QualityDimension
    column: str | None = None
    severity: str  # "low", "medium", "high"
    description: str
    affected_rows: int
    affected_percentage: float
    recommendation: str


class ColumnQualityScore(BaseModel):
    """Quality scores for a single column"""
    column_name: str
    completeness_score: float
    consistency_score: float
    validity_score: float
    uniqueness_score: float
    overall_score: float
    issues: list[QualityIssue] = Field(default_factory=list)


class QualityReport(BaseModel):
    """Comprehensive data quality report"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={
            np.integer: lambda v: int(v),
            np.floating: lambda v: float(v),
            np.ndarray: lambda v: v.tolist(),
            np.bool_: lambda v: bool(v)
        }
    )
    
    overall_quality_score: float
    score_0_100: float = 0.0  # 0-100 ML-readiness score over SCORE_DIMENSIONS (issue #102)
    dimension_scores: dict[QualityDimension, float]
    component_scores: dict[QualityDimension, float] = Field(default_factory=dict)  # 0-100 per dim
    column_scores: list[ColumnQualityScore]
    critical_issues: list[QualityIssue]
    warnings: list[QualityIssue]
    recommendations: list[str]
    actionable_recommendations: list[ActionableRecommendation] = Field(default_factory=list)
    row_count: int
    column_count: int
    assessed_at: datetime = Field(default_factory=utcnow)


class QualityAssessmentService:
    """Service for assessing data quality across multiple dimensions"""
    
    def __init__(self):
        """Initialize quality assessment service"""
        self.severity_thresholds = {
            "high": 0.3,    # More than 30% affected
            "medium": 0.1,  # 10-30% affected
            "low": 0.0      # Less than 10% affected
        }

    async def assess_quality(
        self, 
        df: pd.DataFrame, 
        column_types: dict[str, str],
        column_stats: dict[str, Any] | list[Any] | None = None
    ) -> QualityReport:
        """
        Assess data quality across multiple dimensions
        
        Args:
            df: Input DataFrame
            column_types: Dictionary mapping column names to data types
            column_stats: Pre-calculated column statistics (optional)
            
        Returns:
            QualityReport with scores and issues
        """
        all_issues = []
        column_scores = []
        
        # Assess each column
        for col_name in df.columns:
            col_type = column_types.get(col_name, "unknown")
            col_score, col_issues = await self._assess_column_quality(
                df[col_name], col_name, col_type
            )
            column_scores.append(col_score)
            all_issues.extend(col_issues)
        
        # Calculate dimension scores
        dimension_scores = self._calculate_dimension_scores(column_scores)
        
        # Overall quality score
        if dimension_scores:
            overall_score = float(np.mean(list(dimension_scores.values())))
        else:
            overall_score = 0.0  # Empty dataframe has no quality
        
        # Categorize issues
        critical_issues = [issue for issue in all_issues if issue.severity == "high"]
        warnings = [issue for issue in all_issues if issue.severity in ["medium", "low"]]
        
        # Generate recommendations
        recommendations = self._generate_recommendations(all_issues, column_types)
        actionable_recommendations = self._generate_actionable_recommendations(all_issues)

        # 0-100 ML-readiness score + per-dimension component scores (issue #102, AC1)
        component_scores = {
            dim: round(dimension_scores.get(dim, 0.0) * 100, 1) for dim in SCORE_DIMENSIONS
        }
        if component_scores:
            score_0_100 = round(float(np.mean(list(component_scores.values()))), 1)
        else:
            score_0_100 = 0.0

        return QualityReport(
            overall_quality_score=float(overall_score),
            score_0_100=score_0_100,
            dimension_scores=dimension_scores,
            component_scores=component_scores,
            column_scores=column_scores,
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=recommendations,
            actionable_recommendations=actionable_recommendations,
            row_count=len(df),
            column_count=len(df.columns)
        )

    async def _assess_column_quality(
        self, 
        series: pd.Series, 
        col_name: str, 
        col_type: str
    ) -> tuple[ColumnQualityScore, list[QualityIssue]]:
        """Assess quality for a single column"""
        issues = []
        
        # Completeness assessment
        completeness_score, completeness_issues = self._assess_completeness(series, col_name)
        issues.extend(completeness_issues)
        
        # Consistency assessment
        consistency_score, consistency_issues = self._assess_consistency(series, col_name, col_type)
        issues.extend(consistency_issues)
        
        # Validity assessment
        validity_score, validity_issues = self._assess_validity(series, col_name, col_type)
        issues.extend(validity_issues)
        
        # Uniqueness assessment
        uniqueness_score, uniqueness_issues = self._assess_uniqueness(series, col_name, col_type)
        issues.extend(uniqueness_issues)
        
        # Calculate overall column score
        overall_score = np.mean([
            completeness_score,
            consistency_score,
            validity_score,
            uniqueness_score
        ])
        
        column_score = ColumnQualityScore(
            column_name=col_name,
            completeness_score=float(completeness_score),
            consistency_score=float(consistency_score),
            validity_score=float(validity_score),
            uniqueness_score=float(uniqueness_score),
            overall_score=float(overall_score),
            issues=issues
        )
        
        return column_score, issues

    def _assess_completeness(self, series: pd.Series, col_name: str) -> tuple[float, list[QualityIssue]]:
        """Assess data completeness"""
        issues = []
        null_count = series.isna().sum()
        null_percentage = null_count / len(series)
        
        # Score based on completeness
        completeness_score = 1.0 - null_percentage
        
        # Create issues if there are missing values
        if null_count > 0:
            severity = self._get_severity(null_percentage)
            issues.append(QualityIssue(
                dimension=QualityDimension.COMPLETENESS,
                column=col_name,
                severity=severity,
                description=f"Missing values detected in column '{col_name}'",
                affected_rows=int(null_count),
                affected_percentage=float(null_percentage * 100),
                recommendation=f"Consider imputation or removal of {null_count} missing values"
            ))
        
        return completeness_score, issues

    def _assess_consistency(self, series: pd.Series, col_name: str, col_type: str) -> tuple[float, list[QualityIssue]]:
        """Assess data consistency"""
        issues: list[QualityIssue] = []
        consistency_score = 1.0
        
        # Skip if all values are null
        non_null = series.dropna()
        if len(non_null) == 0:
            return consistency_score, issues
        
        # Check for mixed data types
        if col_type in ["integer", "float"]:
            # Check for non-numeric values
            numeric_mask = pd.to_numeric(non_null, errors='coerce').isna()
            inconsistent_count = numeric_mask.sum()
            
            if inconsistent_count > 0:
                inconsistent_pct = inconsistent_count / len(non_null)
                consistency_score -= inconsistent_pct
                
                issues.append(QualityIssue(
                    dimension=QualityDimension.CONSISTENCY,
                    column=col_name,
                    severity=self._get_severity(inconsistent_pct),
                    description=f"Non-numeric values found in numeric column '{col_name}'",
                    affected_rows=int(inconsistent_count),
                    affected_percentage=float(inconsistent_pct * 100),
                    recommendation="Clean or convert non-numeric values"
                ))
        
        # Check for inconsistent formatting in string columns
        elif col_type in ["string", "categorical"]:
            # Check for inconsistent casing
            str_series = non_null.astype(str)
            unique_values = str_series.unique()
            unique_lower = str_series.str.lower().unique()
            
            if len(unique_values) > len(unique_lower):
                case_issues = len(unique_values) - len(unique_lower)
                consistency_score -= 0.1  # Minor penalty for case inconsistency
                
                issues.append(QualityIssue(
                    dimension=QualityDimension.CONSISTENCY,
                    column=col_name,
                    severity="low",
                    description=f"Inconsistent casing detected in '{col_name}'",
                    affected_rows=case_issues,
                    affected_percentage=float(case_issues / len(unique_values) * 100),
                    recommendation="Standardize text casing for consistency"
                ))
        
        # Check for date format consistency
        elif col_type in ["date", "datetime"]:
            # Try to parse dates and check for failures
            date_parsed = pd.to_datetime(non_null, errors='coerce')
            parse_failures = date_parsed.isna().sum()
            
            if parse_failures > 0:
                failure_pct = parse_failures / len(non_null)
                consistency_score -= failure_pct
                
                issues.append(QualityIssue(
                    dimension=QualityDimension.CONSISTENCY,
                    column=col_name,
                    severity=self._get_severity(failure_pct),
                    description=f"Inconsistent date formats in '{col_name}'",
                    affected_rows=int(parse_failures),
                    affected_percentage=float(failure_pct * 100),
                    recommendation="Standardize date format across all values"
                ))
        
        return max(0.0, consistency_score), issues

    def _assess_validity(self, series: pd.Series, col_name: str, col_type: str) -> tuple[float, list[QualityIssue]]:
        """Assess data validity"""
        issues: list[QualityIssue] = []
        validity_score = 1.0
        
        non_null = series.dropna()
        if len(non_null) == 0:
            return validity_score, issues
        
        # Type-specific validity checks
        if col_type == "email":
            # Check email format validity
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            invalid_emails = ~non_null.astype(str).str.match(email_pattern)
            invalid_count = invalid_emails.sum()
            
            if invalid_count > 0:
                invalid_pct = invalid_count / len(non_null)
                validity_score -= invalid_pct
                
                issues.append(QualityIssue(
                    dimension=QualityDimension.VALIDITY,
                    column=col_name,
                    severity=self._get_severity(invalid_pct),
                    description=f"Invalid email formats in '{col_name}'",
                    affected_rows=int(invalid_count),
                    affected_percentage=float(invalid_pct * 100),
                    recommendation="Validate and correct email formats"
                ))
        
        elif col_type == "phone":
            # Check phone number validity (basic check for length)
            phone_lengths = non_null.astype(str).str.replace(r'[^0-9]', '', regex=True).str.len()
            invalid_phones = (phone_lengths < 10) | (phone_lengths > 15)
            invalid_count = invalid_phones.sum()
            
            if invalid_count > 0:
                invalid_pct = invalid_count / len(non_null)
                validity_score -= invalid_pct * 0.5  # Less severe penalty
                
                issues.append(QualityIssue(
                    dimension=QualityDimension.VALIDITY,
                    column=col_name,
                    severity=self._get_severity(invalid_pct * 0.5),
                    description=f"Potentially invalid phone numbers in '{col_name}'",
                    affected_rows=int(invalid_count),
                    affected_percentage=float(invalid_pct * 100),
                    recommendation="Validate phone number formats and lengths"
                ))
        
        elif col_type in ["integer", "float"]:
            # Check for outliers as potential validity issues
            numeric_series = pd.to_numeric(non_null, errors='coerce').dropna()
            if len(numeric_series) > 0:
                q1 = numeric_series.quantile(0.25)
                q3 = numeric_series.quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 3 * iqr  # Using 3*IQR for extreme outliers
                upper_bound = q3 + 3 * iqr
                
                extreme_outliers = (numeric_series < lower_bound) | (numeric_series > upper_bound)
                outlier_count = extreme_outliers.sum()
                
                if outlier_count > 0:
                    outlier_pct = outlier_count / len(numeric_series)
                    validity_score -= outlier_pct * 0.3  # Moderate penalty for outliers
                    
                    issues.append(QualityIssue(
                        dimension=QualityDimension.VALIDITY,
                        column=col_name,
                        severity=self._get_severity(outlier_pct * 0.3),
                        description=f"Extreme outliers detected in '{col_name}'",
                        affected_rows=int(outlier_count),
                        affected_percentage=float(outlier_pct * 100),
                        recommendation="Review extreme values for data entry errors"
                    ))
        
        return max(0.0, validity_score), issues

    def _assess_uniqueness(self, series: pd.Series, col_name: str, col_type: str) -> tuple[float, list[QualityIssue]]:
        """Assess data uniqueness"""
        issues: list[QualityIssue] = []

        non_null = series.dropna()
        if len(non_null) == 0:
            return 1.0, issues
        
        # Calculate uniqueness ratio
        unique_count = non_null.nunique()
        uniqueness_ratio = unique_count / len(non_null)
        
        # For IDs and keys, we expect high uniqueness
        if any(keyword in col_name.lower() for keyword in ['id', 'key', 'code', 'identifier']):
            if uniqueness_ratio < 0.95:  # Less than 95% unique
                duplicate_count = len(non_null) - unique_count
                duplicate_pct = duplicate_count / len(non_null)
                
                issues.append(QualityIssue(
                    dimension=QualityDimension.UNIQUENESS,
                    column=col_name,
                    severity="high",  # Always high for ID columns
                    description=f"Duplicate values in identifier column '{col_name}'",
                    affected_rows=int(duplicate_count),
                    affected_percentage=float(duplicate_pct * 100),
                    recommendation="Investigate and resolve duplicate identifiers"
                ))
                
                return 1.0 - duplicate_pct, issues
        
        # For other columns, just track if there are many duplicates
        elif uniqueness_ratio < 0.01:  # Less than 1% unique values
            issues.append(QualityIssue(
                dimension=QualityDimension.UNIQUENESS,
                column=col_name,
                severity="low",
                description=f"Low cardinality in '{col_name}' (only {unique_count} unique values)",
                affected_rows=len(non_null),
                affected_percentage=100.0,
                recommendation="Consider if this column should be categorical"
            ))
        
        return 1.0, issues  # Don't penalize uniqueness for non-ID columns

    def _calculate_dimension_scores(self, column_scores: list[ColumnQualityScore]) -> dict[QualityDimension, float]:
        """Calculate average scores for each quality dimension"""
        if not column_scores:
            # Return zeros for empty dataframe
            return {dim: 0.0 for dim in QualityDimension}
        
        dimension_scores: dict[QualityDimension, float] = {
            QualityDimension.COMPLETENESS: float(np.mean([cs.completeness_score for cs in column_scores])),
            QualityDimension.CONSISTENCY: float(np.mean([cs.consistency_score for cs in column_scores])),
            QualityDimension.VALIDITY: float(np.mean([cs.validity_score for cs in column_scores])),
            QualityDimension.UNIQUENESS: float(np.mean([cs.uniqueness_score for cs in column_scores]))
        }
        
        # Add accuracy and timeliness as placeholders (would need domain knowledge)
        dimension_scores[QualityDimension.ACCURACY] = dimension_scores[QualityDimension.VALIDITY]
        dimension_scores[QualityDimension.TIMELINESS] = 1.0  # Assume fresh data
        
        return {k: float(v) for k, v in dimension_scores.items()}

    def _generate_recommendations(self, issues: list[QualityIssue], column_types: dict[str, str]) -> list[str]:
        """Generate actionable recommendations based on issues"""
        recommendations = []
        
        # Group issues by dimension
        dimension_issues: dict[QualityDimension, list[QualityIssue]] = {}
        for issue in issues:
            if issue.dimension not in dimension_issues:
                dimension_issues[issue.dimension] = []
            dimension_issues[issue.dimension].append(issue)
        
        # Completeness recommendations
        if QualityDimension.COMPLETENESS in dimension_issues:
            missing_cols = set(issue.column for issue in dimension_issues[QualityDimension.COMPLETENESS])
            if len(missing_cols) > 3:
                recommendations.append(
                    f"Multiple columns have missing data ({len(missing_cols)} columns). "
                    "Consider implementing a comprehensive imputation strategy."
                )
            else:
                recommendations.append(
                    "Address missing values through imputation, removal, or data collection."
                )
        
        # Consistency recommendations
        if QualityDimension.CONSISTENCY in dimension_issues:
            recommendations.append(
                "Standardize data formats and implement validation rules for consistent data entry."
            )
        
        # Validity recommendations
        if QualityDimension.VALIDITY in dimension_issues:
            validity_issues = dimension_issues[QualityDimension.VALIDITY]
            if any(issue.severity == "high" for issue in validity_issues):
                recommendations.append(
                    "Critical validity issues detected. Review and correct invalid data before analysis."
                )
        
        # Uniqueness recommendations
        if QualityDimension.UNIQUENESS in dimension_issues:
            recommendations.append(
                "Resolve duplicate records in identifier columns to ensure data integrity."
            )
        
        # General recommendations based on overall quality
        overall_critical = len([i for i in issues if i.severity == "high"])
        if overall_critical > 5:
            recommendations.insert(0, 
                f"⚠️ {overall_critical} critical issues found. Prioritize data cleaning before analysis."
            )
        
        return recommendations

    def _generate_actionable_recommendations(
        self, issues: list[QualityIssue]
    ) -> list[ActionableRecommendation]:
        """Map quality issues to concrete transformations (issue #102, AC2).

        Groups issues by (dimension, transformation) so the frontend can offer a
        single "apply fix" action per transformation across all affected columns.
        """
        severity_rank = {"low": 0, "medium": 1, "high": 2}
        grouped: dict[tuple[QualityDimension, str], dict[str, Any]] = {}

        for issue in issues:
            transform = _recommended_transformation(issue)
            if transform is None:
                continue
            key = (issue.dimension, transform.value)
            entry = grouped.setdefault(
                key,
                {"columns": [], "severity": "low", "recommendation": issue.recommendation},
            )
            if issue.column and issue.column not in entry["columns"]:
                entry["columns"].append(issue.column)
            if severity_rank[issue.severity] > severity_rank[entry["severity"]]:
                entry["severity"] = issue.severity

        recommendations = []
        for (dimension, transform_value), entry in grouped.items():
            cols = entry["columns"]
            scope = ", ".join(cols) if cols else "the dataset"
            recommendations.append(
                ActionableRecommendation(
                    dimension=dimension,
                    description=f"Apply '{transform_value}' to {scope}: {entry['recommendation']}",
                    transformation_type=transform_value,
                    affected_columns=cols,
                    severity=entry["severity"],
                )
            )

        # Highest-severity first so the dashboard surfaces the most impactful fixes.
        recommendations.sort(key=lambda r: severity_rank[r.severity], reverse=True)
        return recommendations

    def _get_severity(self, affected_percentage: float) -> str:
        """Determine severity based on affected percentage"""
        if affected_percentage >= self.severity_thresholds["high"]:
            return "high"
        elif affected_percentage >= self.severity_thresholds["medium"]:
            return "medium"
        else:
            return "low"