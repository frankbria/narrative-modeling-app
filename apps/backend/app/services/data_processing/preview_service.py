"""
Preview Service for transformation impact analysis.

Provides functionality to preview transformations and calculate their impact
on data by comparing original vs transformed DataFrames.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from app.schemas.preview import ImpactStatistics

from .quality_assessment import QualityAssessmentService


class PreviewService:
    """Service for previewing transformations and calculating their impact"""

    def __init__(self, quality_service: Optional[QualityAssessmentService] = None):
        """
        Initialize preview service.

        Args:
            quality_service: Optional QualityAssessmentService instance.
                           If not provided, a new one will be created.
        """
        self.quality_service = quality_service or QualityAssessmentService()

    async def calculate_impact(
        self,
        original_df: pd.DataFrame,
        transformed_df: pd.DataFrame,
        column_types: Optional[Dict[str, str]] = None,
    ) -> ImpactStatistics:
        """
        Calculate impact statistics by comparing original vs transformed DataFrames.

        Compares cell-by-cell to identify:
        - rows_affected: Number of rows with ANY changes
        - values_changed: Total number of cells modified
        - columns_affected: List of columns that have changes
        - quality_score_before/after: Quality assessment scores
        - value_distributions: Before/after value distribution for each affected column

        Args:
            original_df: Original DataFrame before transformation
            transformed_df: Transformed DataFrame after transformation
            column_types: Optional dict mapping column names to data types.
                         If not provided, will infer from DataFrame dtypes.

        Returns:
            ImpactStatistics with all metrics

        Raises:
            ValueError: If DataFrames have incompatible structures
        """
        # Validate DataFrames have compatible structures
        self._validate_dataframes(original_df, transformed_df)

        # Infer column types if not provided
        if column_types is None:
            column_types = self._infer_column_types(original_df)

        # Step 1: Calculate basic metrics (rows and values affected)
        rows_affected, values_changed, columns_affected = self._calculate_basic_metrics(
            original_df, transformed_df
        )

        # Step 2: Calculate value distributions for affected columns
        value_distributions = self._calculate_value_distributions(
            original_df, transformed_df, columns_affected
        )

        # Step 3: Calculate quality scores before and after
        quality_score_before, quality_score_after = (
            await self._calculate_quality_scores(
                original_df, transformed_df, column_types
            )
        )

        # Step 4: Return ImpactStatistics
        return ImpactStatistics(
            rows_affected=int(rows_affected),
            values_changed=int(values_changed),
            columns_affected=columns_affected,
            quality_score_before=quality_score_before,
            quality_score_after=quality_score_after,
            value_distributions=value_distributions,
        )

    def _validate_dataframes(
        self, original_df: pd.DataFrame, transformed_df: pd.DataFrame
    ) -> None:
        """
        Validate that DataFrames have compatible structures.

        Args:
            original_df: Original DataFrame
            transformed_df: Transformed DataFrame

        Raises:
            ValueError: If structures are incompatible
        """
        if len(original_df) != len(transformed_df):
            raise ValueError(
                f"DataFrames must have the same number of rows. "
                f"Original: {len(original_df)}, Transformed: {len(transformed_df)}"
            )

        # Check if columns are the same (order doesn't matter)
        original_cols = set(original_df.columns)
        transformed_cols = set(transformed_df.columns)

        if original_cols != transformed_cols:
            missing_in_transformed = original_cols - transformed_cols
            added_in_transformed = transformed_cols - original_cols

            if missing_in_transformed:
                raise ValueError(
                    f"Columns missing in transformed DataFrame: {missing_in_transformed}"
                )
            if added_in_transformed:
                raise ValueError(
                    f"New columns in transformed DataFrame: {added_in_transformed}. "
                    f"PreviewService expects same columns."
                )

    def _infer_column_types(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Infer column types from DataFrame dtypes.

        Args:
            df: Input DataFrame

        Returns:
            Dictionary mapping column names to inferred types
        """
        column_types = {}
        for col in df.columns:
            dtype = str(df[col].dtype)

            if "int" in dtype:
                column_types[col] = "integer"
            elif "float" in dtype:
                column_types[col] = "float"
            elif "datetime" in dtype:
                column_types[col] = "datetime"
            elif "bool" in dtype:
                column_types[col] = "boolean"
            else:
                column_types[col] = "string"

        return column_types

    def _calculate_basic_metrics(
        self, original_df: pd.DataFrame, transformed_df: pd.DataFrame
    ) -> tuple[int, int, List[str]]:
        """
        Calculate basic impact metrics.

        Args:
            original_df: Original DataFrame
            transformed_df: Transformed DataFrame

        Returns:
            Tuple of (rows_affected, values_changed, columns_affected)
        """
        # Compare DataFrames element-wise
        # Handle NaN comparison: NaN == NaN is False in pandas, so we need special handling
        # Create comparison mask: True where values differ
        comparison_mask = pd.DataFrame(False, index=original_df.index, columns=original_df.columns)

        for col in original_df.columns:
            original_col = original_df[col]
            transformed_col = transformed_df[col]

            # Case 1: Both are NaN -> no difference (no action needed; mask stays False)

            # Case 2: One is NaN, one isn't -> difference
            nan_mismatch = original_col.isna() != transformed_col.isna()

            # Case 3: Neither is NaN, but values differ -> difference
            neither_nan = ~original_col.isna() & ~transformed_col.isna()
            values_differ = original_col[neither_nan] != transformed_col[neither_nan]

            # Combine all differences (exclude both_nan which should be False)
            mask = pd.Series(False, index=original_col.index)
            mask[nan_mismatch] = True
            mask[neither_nan] = values_differ.values

            comparison_mask[col] = mask

        # Count rows affected (any cell changed in that row)
        rows_affected = comparison_mask.any(axis=1).sum()

        # Count total values changed
        values_changed = comparison_mask.sum().sum()

        # Identify affected columns (columns with at least one change)
        columns_affected = list(comparison_mask.columns[comparison_mask.any(axis=0)])

        return int(rows_affected), int(values_changed), columns_affected

    def _calculate_value_distributions(
        self,
        original_df: pd.DataFrame,
        transformed_df: pd.DataFrame,
        columns_affected: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate value distribution changes for affected columns.

        Args:
            original_df: Original DataFrame
            transformed_df: Transformed DataFrame
            columns_affected: List of columns that have changes

        Returns:
            Dictionary with before/after value distributions per column
        """
        value_distributions = {}

        for col in columns_affected:
            if col not in original_df.columns:
                continue

            # Get value counts for before and after (dropna=True excludes NaN by default)
            original_counts = original_df[col].value_counts().head(10)
            transformed_counts = transformed_df[col].value_counts().head(10)

            # Convert to dictionaries, handling NaN values
            original_dist = {}
            for value, count in original_counts.items():
                # Convert value to string for JSON serialization
                key = str(value) if pd.notna(value) else "null"
                original_dist[key] = int(count)

            # Add NaN count if present
            original_nan_count = original_df[col].isna().sum()
            if original_nan_count > 0:
                original_dist["null"] = int(original_nan_count)

            transformed_dist = {}
            for value, count in transformed_counts.items():
                # Convert value to string for JSON serialization
                key = str(value) if pd.notna(value) else "null"
                transformed_dist[key] = int(count)

            # Add NaN count if present
            transformed_nan_count = transformed_df[col].isna().sum()
            if transformed_nan_count > 0:
                transformed_dist["null"] = int(transformed_nan_count)

            value_distributions[col] = {
                "before": original_dist,
                "after": transformed_dist,
            }

        return value_distributions

    async def _calculate_quality_scores(
        self,
        original_df: pd.DataFrame,
        transformed_df: pd.DataFrame,
        column_types: Dict[str, str],
    ) -> tuple[float, float]:
        """
        Calculate quality scores before and after transformation.

        Args:
            original_df: Original DataFrame
            transformed_df: Transformed DataFrame
            column_types: Dictionary mapping column names to data types

        Returns:
            Tuple of (quality_score_before, quality_score_after)
        """
        try:
            # Calculate quality scores using QualityAssessmentService
            quality_before = await self.quality_service.assess_quality(
                original_df, column_types
            )
            quality_after = await self.quality_service.assess_quality(
                transformed_df, column_types
            )

            # Extract overall quality scores
            quality_score_before = quality_before.overall_quality_score
            quality_score_after = quality_after.overall_quality_score

            # Ensure scores are between 0 and 1
            quality_score_before = max(0.0, min(1.0, float(quality_score_before)))
            quality_score_after = max(0.0, min(1.0, float(quality_score_after)))

            return quality_score_before, quality_score_after
        except Exception as e:
            # If quality assessment fails, return neutral scores
            # This allows the preview to continue working
            print(f"Warning: Could not calculate quality scores: {e}")
            return 0.5, 0.5
