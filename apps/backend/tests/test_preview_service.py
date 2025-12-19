"""
Unit tests for PreviewService and calculate_impact() method.

Tests cover:
- Basic metrics calculation (rows_affected, values_changed, columns_affected)
- Value distribution calculation
- Quality score integration
- Edge cases (empty DataFrames, NaN values, incompatible shapes)
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.data_processing import PreviewService
from app.services.data_processing.quality_assessment import (
    QualityAssessmentService,
    QualityReport,
    QualityDimension,
)
from app.schemas.preview import ImpactStatistics


@pytest.fixture
def quality_service_mock():
    """Create a mocked QualityAssessmentService"""
    mock = AsyncMock(spec=QualityAssessmentService)
    return mock


@pytest.fixture
def preview_service(quality_service_mock):
    """Create a PreviewService with mocked quality service"""
    return PreviewService(quality_service=quality_service_mock)


@pytest.fixture
def sample_df_before():
    """Create a sample DataFrame before transformation"""
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "age": [25, 30, None, 40, 35],
        "salary": [50000, 75000, 60000, 85000, 70000],
        "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
    })


@pytest.fixture
def sample_df_after():
    """Create a sample DataFrame after transformation (with some changes)"""
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "age": [25, 30, 28, 40, 35],  # Changed: filled None with 28
        "salary": [50000, 75000, 60000, 85000, 70000],
        "name": ["Alice", "Bob", "Charlie", "David", "Evelyn"],  # Changed: Eve -> Evelyn
    })


class TestCalculateImpactBasicMetrics:
    """Test basic metrics calculation"""

    @pytest.mark.asyncio
    async def test_rows_affected_single_change(self, preview_service, sample_df_before, sample_df_after):
        """Test counting rows with at least one change"""
        # Mock quality service
        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.75
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(
            sample_df_before, sample_df_after
        )

        # Row 3 and 5 have changes (age: None->28, name: Eve->Evelyn)
        # Rows are 0-indexed, so indices 2 and 4
        assert impact.rows_affected == 2

    @pytest.mark.asyncio
    async def test_values_changed_count(self, preview_service, sample_df_before, sample_df_after):
        """Test counting total cells changed"""
        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.75
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(
            sample_df_before, sample_df_after
        )

        # 2 cells changed (age[2] and name[4])
        assert impact.values_changed == 2

    @pytest.mark.asyncio
    async def test_columns_affected(self, preview_service, sample_df_before, sample_df_after):
        """Test identifying affected columns"""
        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.75
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(
            sample_df_before, sample_df_after
        )

        # Columns 'age' and 'name' should be affected
        assert set(impact.columns_affected) == {"age", "name"}

    @pytest.mark.asyncio
    async def test_no_changes(self, preview_service, sample_df_before):
        """Test when DataFrames are identical"""
        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.75
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(
            sample_df_before, sample_df_before.copy()
        )

        assert impact.rows_affected == 0
        assert impact.values_changed == 0
        assert impact.columns_affected == []


class TestValueDistributions:
    """Test value distribution calculation"""

    @pytest.mark.asyncio
    async def test_value_distribution_calculation(self, preview_service, sample_df_before, sample_df_after):
        """Test value distribution before/after"""
        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.75
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(
            sample_df_before, sample_df_after
        )

        # Check that value distributions include affected columns
        assert "age" in impact.value_distributions
        assert "name" in impact.value_distributions

        # Check structure
        assert "before" in impact.value_distributions["age"]
        assert "after" in impact.value_distributions["age"]
        assert isinstance(impact.value_distributions["age"]["before"], dict)
        assert isinstance(impact.value_distributions["age"]["after"], dict)

    @pytest.mark.asyncio
    async def test_nan_handling_in_distributions(self, preview_service):
        """Test that NaN values are handled correctly in distributions"""
        df_before = pd.DataFrame({
            "col": [1, 2, None, 1, 2, None],
        })
        df_after = pd.DataFrame({
            "col": [1, 2, 1, 1, 2, 2],  # NaN filled
        })

        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.75
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(df_before, df_after)

        # Should have "null" key in before distribution
        assert "null" in impact.value_distributions["col"]["before"]


class TestQualityScores:
    """Test quality score integration"""

    @pytest.mark.asyncio
    async def test_quality_scores_extracted(self, preview_service, sample_df_before, sample_df_after):
        """Test that quality scores are correctly extracted"""
        # Create mock quality reports
        mock_report_before = MagicMock(spec=QualityReport)
        mock_report_before.overall_quality_score = 0.72

        mock_report_after = MagicMock(spec=QualityReport)
        mock_report_after.overall_quality_score = 0.89

        preview_service.quality_service.assess_quality = AsyncMock(
            side_effect=[mock_report_before, mock_report_after]
        )

        impact = await preview_service.calculate_impact(
            sample_df_before, sample_df_after
        )

        assert impact.quality_score_before == 0.72
        assert impact.quality_score_after == 0.89

    @pytest.mark.asyncio
    async def test_quality_scores_clamped_to_valid_range(self, preview_service, sample_df_before, sample_df_after):
        """Test that quality scores are clamped to [0, 1]"""
        mock_report = MagicMock(spec=QualityReport)
        # Invalid scores that need clamping
        mock_report.overall_quality_score = 1.5  # Should be clamped to 1.0

        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(
            sample_df_before, sample_df_after
        )

        assert impact.quality_score_before == 1.0
        assert impact.quality_score_after == 1.0

    @pytest.mark.asyncio
    async def test_quality_score_fallback_on_error(self, preview_service, sample_df_before, sample_df_after):
        """Test that neutral scores are returned if quality assessment fails"""
        preview_service.quality_service.assess_quality = AsyncMock(
            side_effect=Exception("Quality assessment failed")
        )

        impact = await preview_service.calculate_impact(
            sample_df_before, sample_df_after
        )

        # Should return neutral scores (0.5)
        assert impact.quality_score_before == 0.5
        assert impact.quality_score_after == 0.5


class TestDataFrameValidation:
    """Test DataFrame validation"""

    def test_different_row_counts_raises_error(self, preview_service):
        """Test that error is raised if DataFrames have different row counts"""
        df1 = pd.DataFrame({"col": [1, 2, 3]})
        df2 = pd.DataFrame({"col": [1, 2]})

        with pytest.raises(ValueError, match="same number of rows"):
            preview_service._validate_dataframes(df1, df2)

    def test_different_columns_raises_error(self, preview_service):
        """Test that error is raised if DataFrames have different columns"""
        df1 = pd.DataFrame({"col1": [1, 2, 3]})
        df2 = pd.DataFrame({"col2": [1, 2, 3]})

        with pytest.raises(ValueError, match="Columns missing"):
            preview_service._validate_dataframes(df1, df2)

    def test_same_columns_different_order_passes(self, preview_service):
        """Test that same columns in different order passes validation"""
        df1 = pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})
        df2 = pd.DataFrame({"col2": [4, 5, 6], "col1": [1, 2, 3]})

        # Should not raise
        preview_service._validate_dataframes(df1, df2)


class TestColumnTypeInference:
    """Test column type inference"""

    def test_infer_integer_columns(self, preview_service):
        """Test inference of integer columns"""
        df = pd.DataFrame({"col": [1, 2, 3]})
        types = preview_service._infer_column_types(df)

        assert types["col"] == "integer"

    def test_infer_float_columns(self, preview_service):
        """Test inference of float columns"""
        df = pd.DataFrame({"col": [1.1, 2.2, 3.3]})
        types = preview_service._infer_column_types(df)

        assert types["col"] == "float"

    def test_infer_string_columns(self, preview_service):
        """Test inference of string columns"""
        df = pd.DataFrame({"col": ["a", "b", "c"]})
        types = preview_service._infer_column_types(df)

        assert types["col"] == "string"

    def test_infer_datetime_columns(self, preview_service):
        """Test inference of datetime columns"""
        df = pd.DataFrame({"col": pd.to_datetime(["2024-01-01", "2024-01-02"])})
        types = preview_service._infer_column_types(df)

        assert types["col"] == "datetime"


class TestImpactStatisticsSchema:
    """Test that returned ImpactStatistics match schema"""

    @pytest.mark.asyncio
    async def test_impact_statistics_schema_compliance(self, preview_service, sample_df_before, sample_df_after):
        """Test that returned ImpactStatistics is valid"""
        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.75
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(
            sample_df_before, sample_df_after
        )

        # Verify it's the right type
        assert isinstance(impact, ImpactStatistics)

        # Verify all required fields are present
        assert hasattr(impact, "rows_affected")
        assert hasattr(impact, "values_changed")
        assert hasattr(impact, "columns_affected")
        assert hasattr(impact, "quality_score_before")
        assert hasattr(impact, "quality_score_after")
        assert hasattr(impact, "value_distributions")

        # Verify types
        assert isinstance(impact.rows_affected, int)
        assert isinstance(impact.values_changed, int)
        assert isinstance(impact.columns_affected, list)
        assert isinstance(impact.quality_score_before, float)
        assert isinstance(impact.quality_score_after, float)
        assert isinstance(impact.value_distributions, dict)

        # Verify quality scores are in valid range
        assert 0.0 <= impact.quality_score_before <= 1.0
        assert 0.0 <= impact.quality_score_after <= 1.0


class TestEdgeCases:
    """Test edge cases and special scenarios"""

    @pytest.mark.asyncio
    async def test_empty_dataframes(self, preview_service):
        """Test handling of empty DataFrames"""
        df1 = pd.DataFrame({"col": []})
        df2 = pd.DataFrame({"col": []})

        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.5
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(df1, df2)

        assert impact.rows_affected == 0
        assert impact.values_changed == 0

    @pytest.mark.asyncio
    async def test_all_rows_affected(self, preview_service):
        """Test when all rows are affected"""
        df1 = pd.DataFrame({
            "col1": [1, 2, 3],
            "col2": ["a", "b", "c"]
        })
        df2 = pd.DataFrame({
            "col1": [10, 20, 30],
            "col2": ["x", "y", "z"]
        })

        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.75
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(df1, df2)

        assert impact.rows_affected == 3  # All rows affected
        assert impact.values_changed == 6  # All cells changed
        assert set(impact.columns_affected) == {"col1", "col2"}

    @pytest.mark.asyncio
    async def test_multiple_columns_same_row(self, preview_service):
        """Test row with multiple column changes"""
        df1 = pd.DataFrame({
            "col1": [1, 2],
            "col2": ["a", "b"],
            "col3": [10, 20]
        })
        df2 = pd.DataFrame({
            "col1": [1, 99],  # Changed
            "col2": ["a", "z"],  # Changed
            "col3": [10, 20]
        })

        mock_report = MagicMock(spec=QualityReport)
        mock_report.overall_quality_score = 0.75
        preview_service.quality_service.assess_quality = AsyncMock(
            return_value=mock_report
        )

        impact = await preview_service.calculate_impact(df1, df2)

        # Row 1 (index 1) affected in 2 columns
        assert impact.rows_affected == 1
        assert impact.values_changed == 2
        assert set(impact.columns_affected) == {"col1", "col2"}
