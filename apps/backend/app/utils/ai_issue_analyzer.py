"""
AI-powered issue analyzer for enhanced data quality detection.

This utility uses OpenAI to analyze data patterns, detect semantic issues,
and generate context-aware fix suggestions.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
from openai import AsyncOpenAI, OpenAIError

from app.models.data_issue import (
    DataIssue,
    IssueSeverity,
    IssueType,
    SuggestedFix,
)
from app.utils.circuit_breaker import with_circuit_breaker

logger = logging.getLogger(__name__)

# Get the model name from environment variable
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")

# Maximum sample size to send to AI
MAX_AI_SAMPLE_ROWS = 100
MAX_AI_SAMPLE_COLS = 20


class AIIssueAnalyzer:
    """
    AI-powered analyzer for detecting semantic data quality issues.

    This analyzer uses OpenAI to:
    - Detect patterns that rule-based analysis might miss
    - Provide context-aware explanations for issues
    - Suggest domain-appropriate fixes
    """

    def __init__(self):
        """Initialize the AI analyzer."""
        self.client = self._initialize_client()

    def _initialize_client(self) -> Optional[AsyncOpenAI]:
        """Initialize the async OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, AI analysis will be disabled")
            return None
        return AsyncOpenAI(api_key=api_key)

    async def analyze_data_patterns(
        self,
        df: pd.DataFrame,
        column_types: Dict[str, str],
        existing_issues: List[DataIssue],
    ) -> List[DataIssue]:
        """
        Analyze data for patterns that may indicate quality issues.

        Args:
            df: DataFrame to analyze
            column_types: Column type mappings
            existing_issues: Issues already detected by rule-based analysis

        Returns:
            List of AI-detected data issues
        """
        if not self.client:
            logger.info("OpenAI client not available, skipping AI analysis")
            return []

        try:
            # Create privacy-safe sample
            sample_data = self._create_privacy_safe_sample(df, column_types)

            # Prepare context about existing issues
            existing_issues_summary = self._summarize_existing_issues(existing_issues)

            # Call OpenAI for analysis
            ai_response = await self._call_openai_analysis(
                sample_data,
                column_types,
                existing_issues_summary
            )

            if not ai_response:
                return []

            # Parse response into DataIssue objects
            ai_issues = self._parse_ai_response(ai_response, df)

            return ai_issues

        except Exception as e:
            logger.error(f"AI analysis failed: {str(e)}")
            return []

    def _create_privacy_safe_sample(
        self,
        df: pd.DataFrame,
        column_types: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Create a privacy-safe sample of the data for AI analysis.

        This method:
        - Samples a limited number of rows
        - Masks potentially sensitive columns
        - Converts to statistics where possible
        """
        # Sample rows
        n_rows = min(len(df), MAX_AI_SAMPLE_ROWS)
        sample_df = df.sample(n=n_rows, random_state=42) if len(df) > n_rows else df.copy()

        # Select columns (prioritize numeric and categorical)
        selected_cols = self._select_columns_for_analysis(sample_df, column_types)

        # Build safe sample data
        sample_data = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "sample_size": n_rows,
            "columns": {}
        }

        for col in selected_cols:
            if col not in sample_df.columns:
                continue

            col_type = column_types.get(col, "unknown")
            col_data = {
                "name": col,
                "type": col_type,
                "null_count": int(sample_df[col].isna().sum()),
                "null_percentage": float(sample_df[col].isna().mean() * 100),
                "unique_count": int(sample_df[col].nunique()),
            }

            # Add type-specific statistics
            if col_type in ["integer", "float"]:
                numeric_series = pd.to_numeric(sample_df[col], errors='coerce')
                col_data.update({
                    "mean": float(numeric_series.mean()) if not numeric_series.isna().all() else None,
                    "std": float(numeric_series.std()) if not numeric_series.isna().all() else None,
                    "min": float(numeric_series.min()) if not numeric_series.isna().all() else None,
                    "max": float(numeric_series.max()) if not numeric_series.isna().all() else None,
                    "sample_values": list(numeric_series.dropna().head(5))
                })
            elif col_type in ["string", "categorical"]:
                # Only include non-sensitive sample values
                if not self._is_potentially_sensitive(col):
                    col_data["sample_values"] = list(sample_df[col].dropna().head(5).astype(str))
                    col_data["value_counts"] = dict(sample_df[col].value_counts().head(10))
                else:
                    col_data["sample_values"] = ["[MASKED]"]
                    col_data["note"] = "Potentially sensitive column - values masked"

            sample_data["columns"][col] = col_data

        return sample_data

    def _select_columns_for_analysis(
        self,
        df: pd.DataFrame,
        column_types: Dict[str, str],
    ) -> List[str]:
        """Select most relevant columns for AI analysis."""
        selected = []

        # Prioritize columns with issues
        for col in df.columns:
            if len(selected) >= MAX_AI_SAMPLE_COLS:
                break

            # Include columns with missing values
            if df[col].isna().any():
                selected.append(col)
                continue

            # Include numeric columns
            if column_types.get(col) in ["integer", "float"]:
                selected.append(col)
                continue

            # Include categorical columns with reasonable cardinality
            if column_types.get(col) in ["string", "categorical"]:
                if 2 <= df[col].nunique() <= 100:
                    selected.append(col)

        return selected[:MAX_AI_SAMPLE_COLS]

    def _is_potentially_sensitive(self, column_name: str) -> bool:
        """Check if a column might contain sensitive data based on name."""
        sensitive_patterns = [
            'email', 'mail', 'phone', 'tel', 'mobile', 'ssn', 'social',
            'password', 'pwd', 'secret', 'token', 'key', 'api',
            'name', 'address', 'addr', 'street', 'city', 'zip', 'postal',
            'credit', 'card', 'account', 'bank', 'routing',
            'dob', 'birth', 'age', 'gender', 'sex', 'race', 'ethnicity',
            'salary', 'income', 'wage', 'pay', 'compensation',
            'medical', 'health', 'diagnosis', 'patient',
        ]

        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in sensitive_patterns)

    def _summarize_existing_issues(
        self,
        existing_issues: List[DataIssue]
    ) -> List[Dict[str, Any]]:
        """Create a summary of existing issues for context."""
        return [
            {
                "type": issue.issue_type.value,
                "severity": issue.severity.value,
                "column": issue.affected_column,
                "description": issue.description,
                "affected_percentage": issue.affected_percentage,
            }
            for issue in existing_issues[:10]  # Limit to top 10 for context
        ]

    @with_circuit_breaker(
        "openai_issue_analyzer",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(OpenAIError, Exception),
        fallback_value=None
    )
    async def _call_openai_analysis(
        self,
        sample_data: Dict[str, Any],
        column_types: Dict[str, str],
        existing_issues: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Call OpenAI API for data quality analysis."""
        if not self.client:
            return None

        system_prompt = """You are a data quality expert analyzing a dataset for quality issues.

Your task is to identify potential data quality issues that might not be caught by simple rule-based checks.

Focus on:
1. Semantic inconsistencies (e.g., values that don't make sense in context)
2. Unusual patterns that might indicate data entry errors
3. Potential relationships between columns that are violated
4. Domain-specific issues based on column names and types

Return your analysis as JSON with this structure:
{
    "issues": [
        {
            "issue_type": "string - one of: missing_values, outliers, inconsistent_format, duplicates, invalid_values, type_mismatch, inconsistent_casing, semantic_issue",
            "severity": "string - one of: critical, high, medium, low",
            "affected_column": "string or null",
            "description": "string - clear description of the issue",
            "impact": "string - how this affects data analysis",
            "suggested_fix": {
                "transformation_type": "string - suggested fix type",
                "explanation": "string - why this fix is recommended"
            }
        }
    ],
    "summary": "string - brief overall assessment"
}

Only report NEW issues not already covered in the existing issues list.
Be conservative - only flag issues you're confident about.
Do not report more than 5 issues."""

        user_prompt = f"""Analyze this dataset for data quality issues:

Dataset Overview:
- Total rows: {sample_data['row_count']}
- Total columns: {sample_data['column_count']}
- Sample size analyzed: {sample_data['sample_size']}

Column Information:
{json.dumps(sample_data['columns'], indent=2, default=str)}

Column Types:
{json.dumps(column_types, indent=2)}

Issues already detected (DO NOT duplicate these):
{json.dumps(existing_issues, indent=2)}

Please identify any additional data quality issues not covered above."""

        try:
            response = await self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise

    def _parse_ai_response(
        self,
        ai_response: Dict[str, Any],
        df: pd.DataFrame
    ) -> List[DataIssue]:
        """Parse AI response into DataIssue objects."""
        issues: List[DataIssue] = []

        if not ai_response or "issues" not in ai_response:
            return issues

        for issue_data in ai_response.get("issues", []):
            try:
                # Map issue type
                issue_type_str = issue_data.get("issue_type", "invalid_values")
                try:
                    issue_type = IssueType(issue_type_str)
                except ValueError:
                    issue_type = IssueType.INVALID_VALUES

                # Map severity
                severity_str = issue_data.get("severity", "medium")
                severity_map = {
                    "critical": IssueSeverity.CRITICAL,
                    "high": IssueSeverity.HIGH,
                    "medium": IssueSeverity.MEDIUM,
                    "low": IssueSeverity.LOW,
                }
                severity = severity_map.get(severity_str, IssueSeverity.MEDIUM)

                # Get affected column info
                affected_col = issue_data.get("affected_column")
                affected_rows = 0
                affected_pct = 0.0

                if affected_col and affected_col in df.columns:
                    # Estimate affected rows based on issue type
                    if issue_type == IssueType.MISSING_VALUES:
                        affected_rows = int(df[affected_col].isna().sum())
                        affected_pct = float(df[affected_col].isna().mean() * 100)
                    else:
                        # Default estimate
                        affected_rows = int(len(df) * 0.1)
                        affected_pct = 10.0

                # Create suggested fix if provided
                suggested_fixes: List[SuggestedFix] = []
                fix_data = issue_data.get("suggested_fix")
                if fix_data:
                    suggested_fixes.append(SuggestedFix(
                        transformation_type=fix_data.get("transformation_type", ""),
                        parameters={},
                        explanation=fix_data.get("explanation", ""),
                        ai_generated=True,
                        confidence_score=0.7,
                        estimated_rows_affected=affected_rows,
                    ))

                # Create the issue
                issue = DataIssue(
                    issue_type=issue_type,
                    severity=severity,
                    affected_column=affected_col,
                    affected_columns=[affected_col] if affected_col else [],
                    affected_rows=affected_rows,
                    affected_percentage=affected_pct,
                    description=issue_data.get("description", "AI-detected issue"),
                    impact=issue_data.get("impact", ""),
                    suggested_fixes=suggested_fixes,
                    ai_generated=True,
                    ai_explanation=ai_response.get("summary", ""),
                )

                issues.append(issue)

            except Exception as e:
                logger.warning(f"Failed to parse AI issue: {str(e)}")
                continue

        return issues

    async def generate_fix_explanation(
        self,
        issue: DataIssue,
        fix: SuggestedFix,
    ) -> str:
        """Generate a plain-language explanation for a fix."""
        if not self.client:
            return fix.explanation or "Apply the suggested transformation to fix this issue."

        prompt = f"""Explain this data fix in simple terms:

Issue: {issue.description}
Fix Type: {fix.transformation_type}
Parameters: {json.dumps(fix.parameters)}

Provide a brief (1-2 sentences) explanation of:
1. What this fix does
2. Why it helps resolve the issue

Keep the explanation non-technical and easy to understand."""

        try:
            response = await self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate fix explanation: {str(e)}")
            return fix.explanation or "Apply the suggested transformation to fix this issue."

    async def assess_fix_impact(
        self,
        issue: DataIssue,
        fix: SuggestedFix,
        sample_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assess the potential impact of applying a fix."""
        if not self.client:
            return {
                "risk_level": "unknown",
                "explanation": "AI assessment unavailable"
            }

        prompt = f"""Assess the impact of this data fix:

Issue: {issue.description}
Severity: {issue.severity.value}
Affected Rows: {issue.affected_rows}

Proposed Fix: {fix.transformation_type}
Parameters: {json.dumps(fix.parameters)}
Estimated Data Loss: {fix.estimated_data_loss}%

Briefly assess:
1. Risk level (low/medium/high)
2. Potential consequences
3. Any considerations before applying

Return as JSON: {{"risk_level": "...", "consequences": "...", "considerations": "..."}}"""

        try:
            response = await self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Failed to assess fix impact: {str(e)}")
            return {
                "risk_level": "unknown",
                "explanation": "AI assessment failed"
            }
