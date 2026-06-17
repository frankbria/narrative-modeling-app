"""
Unit tests for DataIssueDetectionService.

Tests rule-based detection, fix suggestion generation, and detection summary creation.
"""

import pandas as pd
import pytest

from app.models.data_issue import (
    IssueSeverity,
    IssueType,
)
from app.schemas.data_issue import DetectionOptions
from app.services.data_issue_detection_service import DataIssueDetectionService


class TestDataIssueDetectionService:
    """Tests for DataIssueDetectionService."""

    @pytest.fixture
    def service(self):
        """Create a detection service instance."""
        return DataIssueDetectionService()

    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame with various issues."""
        return pd.DataFrame({
            'id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'name': ['Alice', 'Bob', 'Charlie', 'alice', 'Bob ', None, 'Eve', 'Frank', 'Grace', 'Helen'],
            'age': [25, 30, None, 35, 40, 45, 150, 28, 32, 27],  # 150 is outlier
            'email': ['a@test.com', 'b@test.com', 'c@test.com', 'a@test.com', 'd@test.com',
                      'e@test.com', 'f@test.com', 'g@test.com', 'h@test.com', 'i@test.com'],
            'salary': [50000, 60000, 70000, 55000, 65000, None, 75000, 58000, 62000, 1000000],  # 1M is outlier
        })

    @pytest.fixture
    def column_types(self):
        """Define column types for the sample DataFrame."""
        return {
            'id': 'integer',
            'name': 'string',
            'age': 'integer',
            'email': 'string',
            'salary': 'float',
        }

    @pytest.mark.asyncio
    async def test_detect_missing_values(self, service, sample_df, column_types):
        """Test detection of missing values."""
        options = DetectionOptions(
            check_missing_values=True,
            check_duplicates=False,
            check_outliers=False,
            check_inconsistencies=False,
            include_ai_analysis=False,
        )

        issues, summary = await service.detect_issues(
            sample_df, column_types, options, include_ai_analysis=False
        )

        # Should detect missing values in 'name', 'age', and 'salary'
        missing_issues = [i for i in issues if i.issue_type == IssueType.MISSING_VALUES]
        assert len(missing_issues) >= 2  # At least name and age have nulls

    @pytest.mark.asyncio
    async def test_detect_outliers(self, service):
        """Test detection of outliers."""
        # Create a dataset with clear outliers (need enough data points for IQR)
        outlier_df = pd.DataFrame({
            'value': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                     11, 12, 13, 14, 15, 16, 17, 18, 19,
                     500]  # 500 is a clear outlier
        })

        options = DetectionOptions(
            check_missing_values=False,
            check_duplicates=False,
            check_outliers=True,
            check_inconsistencies=False,
            include_ai_analysis=False,
            outlier_method='iqr',
            outlier_threshold=1.5,
        )

        issues, summary = await service.detect_issues(
            outlier_df, {'value': 'float'}, options, include_ai_analysis=False
        )

        outlier_issues = [i for i in issues if i.issue_type == IssueType.OUTLIERS]
        # Should detect the outlier (500)
        assert len(outlier_issues) >= 1

    @pytest.mark.asyncio
    async def test_detect_whitespace_issues(self, service, sample_df, column_types):
        """Test detection of whitespace issues."""
        options = DetectionOptions(
            check_missing_values=False,
            check_duplicates=False,
            check_outliers=False,
            check_inconsistencies=True,
            include_ai_analysis=False,
        )

        issues, summary = await service.detect_issues(
            sample_df, column_types, options, include_ai_analysis=False
        )

        whitespace_issues = [i for i in issues if i.issue_type == IssueType.WHITESPACE_ISSUES]
        # Should detect 'Bob ' has trailing whitespace
        assert len(whitespace_issues) >= 1

    @pytest.mark.asyncio
    async def test_detect_casing_issues(self, service, sample_df, column_types):
        """Test detection of inconsistent casing."""
        options = DetectionOptions(
            check_missing_values=False,
            check_duplicates=False,
            check_outliers=False,
            check_inconsistencies=True,
            include_ai_analysis=False,
        )

        issues, summary = await service.detect_issues(
            sample_df, column_types, options, include_ai_analysis=False
        )

        casing_issues = [i for i in issues if i.issue_type == IssueType.INCONSISTENT_CASING]
        # Should detect 'Alice' vs 'alice'
        assert len(casing_issues) >= 1

    @pytest.mark.asyncio
    async def test_detection_summary(self, service, sample_df, column_types):
        """Test that detection summary is correctly calculated."""
        options = DetectionOptions(
            include_ai_analysis=False,
        )

        issues, summary = await service.detect_issues(
            sample_df, column_types, options, include_ai_analysis=False
        )

        assert summary.total_issues == len(issues)
        assert summary.columns_analyzed == len(sample_df.columns)
        assert summary.rows_analyzed == len(sample_df)
        assert summary.detection_time_ms >= 0

    @pytest.mark.asyncio
    async def test_fix_suggestions_for_missing_values(self, service, sample_df, column_types):
        """Test that appropriate fix suggestions are generated for missing values."""
        options = DetectionOptions(
            check_missing_values=True,
            check_duplicates=False,
            check_outliers=False,
            check_inconsistencies=False,
            include_ai_analysis=False,
        )

        issues, summary = await service.detect_issues(
            sample_df, column_types, options, include_ai_analysis=False
        )

        missing_issues = [i for i in issues if i.issue_type == IssueType.MISSING_VALUES]

        for issue in missing_issues:
            assert len(issue.suggested_fixes) > 0
            # Check that appropriate fix types are suggested
            fix_types = [f.transformation_type for f in issue.suggested_fixes]

            # Numeric columns should have mean/median suggestions
            if issue.affected_column in ['age', 'salary']:
                assert any('fill_missing' in ft or 'impute' in ft for ft in fix_types)

    @pytest.mark.asyncio
    async def test_empty_dataframe(self, service):
        """Test handling of empty DataFrame."""
        empty_df = pd.DataFrame()
        column_types = {}

        options = DetectionOptions(include_ai_analysis=False)

        issues, summary = await service.detect_issues(
            empty_df, column_types, options, include_ai_analysis=False
        )

        assert len(issues) == 0
        assert summary.total_issues == 0

    @pytest.mark.asyncio
    async def test_clean_dataframe(self, service):
        """Test detection on a clean DataFrame with no issues."""
        clean_df = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'value': [10, 20, 30, 40, 50],
        })
        column_types = {'id': 'integer', 'value': 'integer'}

        options = DetectionOptions(
            check_duplicates=True,
            check_outliers=False,  # Disable outlier detection as small sample
            include_ai_analysis=False,
        )

        issues, summary = await service.detect_issues(
            clean_df, column_types, options, include_ai_analysis=False
        )

        # Should have no or very few issues
        critical_issues = [i for i in issues if i.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]]
        assert len(critical_issues) == 0

    @pytest.mark.asyncio
    async def test_severity_calculation(self, service):
        """Test that severity is correctly calculated based on affected percentage."""
        # Create a DataFrame with 50% missing values
        df_high_missing = pd.DataFrame({
            'value': [1, 2, None, None, None, None, None, None, None, None]
        })

        options = DetectionOptions(
            check_missing_values=True,
            check_duplicates=False,
            check_outliers=False,
            include_ai_analysis=False,
        )

        issues, summary = await service.detect_issues(
            df_high_missing, {'value': 'integer'}, options, include_ai_analysis=False
        )

        missing_issues = [i for i in issues if i.issue_type == IssueType.MISSING_VALUES]
        if missing_issues:
            # 80% missing should be high/critical severity
            assert missing_issues[0].severity in [IssueSeverity.HIGH, IssueSeverity.CRITICAL]

    @pytest.mark.asyncio
    async def test_sampling_large_dataset(self, service):
        """Test that large datasets are sampled correctly."""
        # Create a larger DataFrame
        large_df = pd.DataFrame({
            'id': range(10000),
            'value': [i if i % 10 != 0 else None for i in range(10000)],
        })

        options = DetectionOptions(
            sample_size=1000,
            include_ai_analysis=False,
        )

        issues, summary = await service.detect_issues(
            large_df, {'id': 'integer', 'value': 'integer'}, options, include_ai_analysis=False
        )

        # Summary should show sampled rows, not full dataset
        assert summary.rows_analyzed <= 1000


class TestDetectionOptions:
    """Tests for DetectionOptions schema."""

    def test_default_options(self):
        """Test that default options are sensible."""
        options = DetectionOptions()

        assert options.include_ai_analysis is True
        assert options.check_missing_values is True
        assert options.check_duplicates is True
        assert options.check_outliers is True
        assert options.outlier_method == 'iqr'
        assert options.outlier_threshold == 1.5

    def test_custom_options(self):
        """Test custom option configuration."""
        options = DetectionOptions(
            include_ai_analysis=False,
            check_missing_values=False,
            outlier_method='zscore',
            outlier_threshold=3.0,
            columns=['col1', 'col2'],
        )

        assert options.include_ai_analysis is False
        assert options.check_missing_values is False
        assert options.outlier_method == 'zscore'
        assert options.outlier_threshold == 3.0
        assert options.columns == ['col1', 'col2']


class TestSeverityThresholds:
    """Tests for severity threshold calculations."""

    @pytest.fixture
    def service(self):
        return DataIssueDetectionService()

    def test_critical_threshold(self, service):
        """Test critical severity threshold (>50%)."""
        severity = service._get_severity_from_percentage(55.0)
        assert severity == IssueSeverity.CRITICAL

    def test_high_threshold(self, service):
        """Test high severity threshold (30-50%)."""
        severity = service._get_severity_from_percentage(35.0)
        assert severity == IssueSeverity.HIGH

    def test_medium_threshold(self, service):
        """Test medium severity threshold (10-30%)."""
        severity = service._get_severity_from_percentage(15.0)
        assert severity == IssueSeverity.MEDIUM

    def test_low_threshold(self, service):
        """Test low severity threshold (<10%)."""
        severity = service._get_severity_from_percentage(5.0)
        assert severity == IssueSeverity.LOW
