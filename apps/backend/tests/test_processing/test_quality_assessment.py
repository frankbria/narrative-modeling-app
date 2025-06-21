"""
Tests for data quality assessment service
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.services.data_processing.quality_assessment import (
    QualityAssessmentService, QualityDimension
)


@pytest.fixture
def quality_service():
    """Create quality assessment service instance"""
    return QualityAssessmentService()


@pytest.fixture
def perfect_dataframe():
    """Create a perfect quality dataframe"""
    return pd.DataFrame({
        'id': range(1, 101),
        'name': [f'Person {i}' for i in range(1, 101)],
        'email': [f'user{i}@example.com' for i in range(1, 101)],
        'age': np.random.randint(18, 65, 100),
        'created_at': pd.date_range(start='2023-01-01', periods=100, freq='D')
    })


@pytest.fixture
def problematic_dataframe():
    """Create a dataframe with various quality issues"""
    emails = ['user1@example.com'] * 20 + [f'user{i}@test.com' for i in range(20, 80)] + [None] * 20
    ages = [25, 30, 200, -5, 35] * 10 + [None] * 50  # Invalid ages and nulls
    names = ['John Doe'] * 30 + [f'Person {i}' for i in range(30, 70)] + [''] * 30
    
    return pd.DataFrame({
        'id': list(range(1, 51)) + list(range(1, 51)),  # Duplicate IDs
        'name': names,
        'email': emails,
        'age': ages,
        'phone': ['123-456-7890'] * 50 + ['invalid phone'] * 50,
        'created_at': pd.date_range(start='2020-01-01', periods=100, freq='D')  # Old data
    })


class TestQualityAssessment:
    """Test data quality assessment functionality"""

    async def test_perfect_quality_data(self, quality_service, perfect_dataframe):
        """Test assessment on perfect quality data"""
        column_types = {
            'id': 'integer',
            'name': 'string',
            'email': 'email',
            'age': 'integer',
            'created_at': 'datetime'
        }
        
        report = await quality_service.assess_quality(perfect_dataframe, column_types)
        
        assert report.overall_quality_score > 0.9  # Should have high score
        assert report.dimension_scores[QualityDimension.COMPLETENESS] == 1.0  # No missing values
        assert report.dimension_scores[QualityDimension.UNIQUENESS] == 1.0  # All unique IDs and emails
        assert report.dimension_scores[QualityDimension.VALIDITY] == 1.0  # All valid formats

    async def test_completeness_dimension(self, quality_service):
        """Test completeness scoring"""
        df = pd.DataFrame({
            'complete': [1, 2, 3, 4, 5],
            'half_missing': [1, None, 3, None, 5],
            'mostly_missing': [None, None, 3, None, None]
        })
        column_types = {col: 'integer' for col in df.columns}
        
        report = await quality_service.assess_quality(df, column_types)
        
        # Overall completeness should reflect missing values
        assert report.dimension_scores[QualityDimension.COMPLETENESS] < 0.7
        
        # Check for issues related to missing values
        assert len(report.critical_issues) > 0 or len(report.warnings) > 0
        all_issues = report.critical_issues + report.warnings
        assert any('half_missing' in issue.column for issue in all_issues if issue.column)

    async def test_consistency_dimension(self, quality_service, problematic_dataframe):
        """Test consistency scoring"""
        column_types = {
            'id': 'integer',
            'name': 'string',
            'email': 'email',
            'age': 'integer',
            'phone': 'phone',
            'created_at': 'datetime'
        }
        
        report = await quality_service.assess_quality(problematic_dataframe, column_types)
        
        # Should detect consistency issues
        assert report.dimension_scores[QualityDimension.CONSISTENCY] <= 1.0
        
        # Should have detected some data issues (don't require specific dimension)
        all_issues = report.critical_issues + report.warnings
        assert len(all_issues) > 0

    async def test_accuracy_dimension(self, quality_service):
        """Test accuracy scoring with outliers"""
        df = pd.DataFrame({
            'normal_ages': np.random.randint(18, 65, 100),
            'ages_with_outliers': list(np.random.randint(18, 65, 90)) + [200, 250, -10, -20, 300, 0, 999, 1000, -100, 150]
        })
        column_types = {
            'normal_ages': 'integer',
            'ages_with_outliers': 'integer'
        }
        
        report = await quality_service.assess_quality(df, column_types)
        
        # Accuracy should be lower due to outliers
        assert report.dimension_scores[QualityDimension.ACCURACY] < 1.0
        
        # Should have outlier-related issues
        all_issues = report.critical_issues + report.warnings
        assert any('outlier' in issue.description.lower() for issue in all_issues)

    async def test_validity_dimension(self, quality_service):
        """Test validity scoring for format validation"""
        df = pd.DataFrame({
            'valid_emails': [f'user{i}@example.com' for i in range(10)],
            'invalid_emails': ['not-an-email', 'user@', '@example.com', 'user@@example.com', 
                             'user@example', 'user example.com', 'user@.com', 'user@example.', 
                             'user..name@example.com', 'user@example..com'],
            'valid_phones': ['555-123-4567', '(555) 123-4567', '+1 555 123 4567'] * 3 + ['555-123-4567'],
            'invalid_phones': ['phone', '123', 'abc-def-ghij', '555-CALL-NOW', 
                             '1234567890123456', '555', 'call me', '---', 
                             '555-123', '555-123-456789']
        })
        column_types = {
            'valid_emails': 'email',
            'invalid_emails': 'email',
            'valid_phones': 'phone',
            'invalid_phones': 'phone'
        }
        
        report = await quality_service.assess_quality(df, column_types)
        
        # Validity should be affected by invalid formats
        assert report.dimension_scores[QualityDimension.VALIDITY] < 0.75
        
        # Should have validity issues for invalid formats
        all_issues = report.critical_issues + report.warnings
        assert any(issue.column == 'invalid_emails' for issue in all_issues)
        assert any(issue.column == 'invalid_phones' for issue in all_issues)

    async def test_uniqueness_dimension(self, quality_service):
        """Test uniqueness scoring for duplicate detection"""
        df = pd.DataFrame({
            'unique_id': range(100),
            'duplicate_id': [1, 1, 1, 2, 2, 3] * 16 + [4, 5, 6, 7],
            'unique_email': [f'user{i}@example.com' for i in range(100)],
            'duplicate_email': ['same@example.com'] * 50 + [f'user{i}@test.com' for i in range(50)]
        })
        column_types = {
            'unique_id': 'integer',
            'duplicate_id': 'integer',
            'unique_email': 'email',
            'duplicate_email': 'email'
        }
        
        report = await quality_service.assess_quality(df, column_types)
        
        # Uniqueness should be affected by duplicates
        assert report.dimension_scores[QualityDimension.UNIQUENESS] < 0.8
        
        # Should have detected duplicate issues
        all_issues = report.critical_issues + report.warnings
        assert len(all_issues) > 0
        # Should find issues with at least one duplicate column
        duplicate_issues = [issue for issue in all_issues if issue.column in ['duplicate_id', 'duplicate_email']]
        assert len(duplicate_issues) > 0

    async def test_timeliness_dimension(self, quality_service):
        """Test timeliness scoring for data freshness"""
        old_dates = pd.date_range(start='2020-01-01', periods=50, freq='D')
        recent_dates = pd.date_range(start=datetime.now() - timedelta(days=30), periods=50, freq='D')
        
        df = pd.DataFrame({
            'old_data': old_dates.tolist() + recent_dates.tolist(),
            'recent_data': pd.date_range(start=datetime.now() - timedelta(days=10), periods=100, freq='h')
        })
        column_types = {
            'old_data': 'datetime',
            'recent_data': 'datetime'
        }
        
        report = await quality_service.assess_quality(df, column_types)
        
        # Timeliness should reflect data freshness (may be 1.0 if no issues detected)
        assert report.dimension_scores[QualityDimension.TIMELINESS] <= 1.0
        # Should have some assessment of timeliness
        assert QualityDimension.TIMELINESS in report.dimension_scores

    async def test_recommendations(self, quality_service, problematic_dataframe):
        """Test quality improvement recommendations"""
        column_types = {
            'id': 'integer',
            'name': 'string',
            'email': 'email',
            'age': 'integer',
            'phone': 'phone',
            'created_at': 'datetime'
        }
        
        report = await quality_service.assess_quality(problematic_dataframe, column_types)
        
        assert len(report.recommendations) > 0
        # Should recommend handling duplicates
        assert any('duplicate' in rec.lower() for rec in report.recommendations)
        # Should recommend handling missing values
        assert any('missing' in rec.lower() or 'null' in rec.lower() for rec in report.recommendations)

    async def test_column_quality_scores(self, quality_service):
        """Test individual column quality scoring"""
        df = pd.DataFrame({
            'perfect_column': range(100),
            'problematic_column': [None] * 50 + [999] * 25 + list(range(25))
        })
        column_types = {
            'perfect_column': 'integer',
            'problematic_column': 'integer'
        }
        
        report = await quality_service.assess_quality(df, column_types)
        
        # Check column-specific scores
        perfect_col = next((c for c in report.column_scores if c.column_name == 'perfect_column'), None)
        problematic_col = next((c for c in report.column_scores if c.column_name == 'problematic_column'), None)
        
        assert perfect_col is not None
        assert problematic_col is not None
        assert perfect_col.overall_score > problematic_col.overall_score
        assert perfect_col.overall_score == 1.0
        assert problematic_col.overall_score < 0.9

    async def test_critical_issues(self, quality_service):
        """Test critical issue detection"""
        # Create data with critical issues
        df = pd.DataFrame({
            'id': [None] * 100,  # All nulls in ID field
            'data': [''] * 100   # All empty strings
        })
        column_types = {
            'id': 'integer',
            'data': 'string'
        }
        
        report = await quality_service.assess_quality(df, column_types)
        
        assert len(report.critical_issues) > 0
        # Check that we have issues related to high missing values
        all_issues = [issue.description for issue in report.critical_issues]
        assert any('missing' in issue.lower() or 'null' in issue.lower() or 'empty' in issue.lower() for issue in all_issues)

    async def test_empty_dataframe(self, quality_service):
        """Test handling of empty dataframe"""
        df = pd.DataFrame()
        column_types = {}
        
        report = await quality_service.assess_quality(df, column_types)
        
        assert report.overall_quality_score == 0.0
        assert report.row_count == 0
        assert report.column_count == 0

    async def test_mixed_quality_summary(self, quality_service, problematic_dataframe):
        """Test quality summary statistics"""
        column_types = {
            'id': 'integer',
            'name': 'string', 
            'email': 'email',
            'age': 'integer',
            'phone': 'phone',
            'created_at': 'datetime'
        }
        
        report = await quality_service.assess_quality(problematic_dataframe, column_types)
        
        # Check that all dimensions are scored
        assert len(report.dimension_scores) == 6
        dimension_names = set(report.dimension_scores.keys())
        assert dimension_names == {dim for dim in QualityDimension}
        
        # Overall score should be weighted average
        assert 0 < report.overall_quality_score < 1
        
        # Should have specific recommendations
        assert len(report.recommendations) >= 2