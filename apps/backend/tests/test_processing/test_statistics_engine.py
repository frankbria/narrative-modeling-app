"""
Tests for statistics calculation engine
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.services.data_processing.statistics_engine import StatisticsEngine, ColumnStatistics


@pytest.fixture
def stats_engine():
    """Create statistics engine instance"""
    return StatisticsEngine(outlier_method="iqr", correlation_threshold=0.7)


@pytest.fixture
def numeric_dataframe():
    """Create sample numeric dataframe"""
    np.random.seed(42)
    return pd.DataFrame({
        'normal_dist': np.random.normal(100, 15, 1000),
        'uniform_dist': np.random.uniform(0, 100, 1000),
        'skewed_dist': np.random.exponential(scale=2, size=1000),
        'with_outliers': np.concatenate([
            np.random.normal(50, 5, 950),
            np.random.normal(200, 10, 50)  # Outliers
        ])
    })


@pytest.fixture
def mixed_dataframe():
    """Create dataframe with mixed types"""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    
    return pd.DataFrame({
        'id': range(1, 101),
        'value': np.random.normal(50, 10, 100),
        'category': np.random.choice(['A', 'B', 'C'], 100),
        'date': dates,
        'text': [f'Description {i}' for i in range(100)],
        'has_nulls': [None if i % 10 == 0 else i for i in range(100)]
    })


class TestStatisticsEngine:
    """Test statistics calculation functionality"""

    async def test_basic_numeric_statistics(self, stats_engine):
        """Test basic statistics for numeric column"""
        df = pd.DataFrame({'col': [1, 2, 3, 4, 5]})
        column_types = {'col': 'integer'}
        
        stats = await stats_engine.calculate_statistics(df, column_types)
        
        assert stats.row_count == 5
        assert stats.column_count == 1
        
        col_stats = stats.column_statistics[0]
        assert col_stats.column_name == 'col'
        assert col_stats.mean == 3.0
        assert col_stats.median == 3.0
        assert col_stats.min_value == 1.0
        assert col_stats.max_value == 5.0
        assert col_stats.std_dev == pytest.approx(1.58, rel=0.01)

    async def test_quartiles_and_percentiles(self, stats_engine, numeric_dataframe):
        """Test quartile and percentile calculations"""
        column_types = {col: 'float' for col in numeric_dataframe.columns}
        stats = await stats_engine.calculate_statistics(numeric_dataframe, column_types)
        
        # Check normal distribution statistics
        normal_stats = next(cs for cs in stats.column_statistics if cs.column_name == 'normal_dist')
        
        assert normal_stats.q1 is not None
        assert normal_stats.q3 is not None
        assert normal_stats.iqr == pytest.approx(normal_stats.q3 - normal_stats.q1)
        assert normal_stats.percentile_5 < normal_stats.q1
        assert normal_stats.percentile_95 > normal_stats.q3

    async def test_outlier_detection_iqr(self, stats_engine, numeric_dataframe):
        """Test outlier detection using IQR method"""
        column_types = {col: 'float' for col in numeric_dataframe.columns}
        stats = await stats_engine.calculate_statistics(numeric_dataframe, column_types)
        
        # Check outliers in the column designed to have outliers
        outlier_stats = next(cs for cs in stats.column_statistics if cs.column_name == 'with_outliers')
        
        assert outlier_stats.outlier_count > 0
        assert outlier_stats.outlier_percentage > 0
        assert outlier_stats.lower_fence is not None
        assert outlier_stats.upper_fence is not None

    async def test_distribution_metrics(self, stats_engine, numeric_dataframe):
        """Test skewness and kurtosis calculations"""
        column_types = {col: 'float' for col in numeric_dataframe.columns}
        stats = await stats_engine.calculate_statistics(numeric_dataframe, column_types)
        
        # Check skewed distribution
        skewed_stats = next(cs for cs in stats.column_statistics if cs.column_name == 'skewed_dist')
        
        assert skewed_stats.skewness is not None
        assert skewed_stats.skewness > 0  # Exponential distribution is right-skewed
        assert skewed_stats.kurtosis is not None

    async def test_null_value_handling(self, stats_engine, mixed_dataframe):
        """Test handling of null values"""
        column_types = {
            'id': 'integer',
            'value': 'float',
            'category': 'categorical',
            'date': 'datetime',
            'text': 'string',
            'has_nulls': 'integer'
        }
        
        stats = await stats_engine.calculate_statistics(mixed_dataframe, column_types)
        
        # Check null statistics
        null_col_stats = next(cs for cs in stats.column_statistics if cs.column_name == 'has_nulls')
        
        assert null_col_stats.null_count == 10  # Every 10th value is null
        assert null_col_stats.null_percentage == 10.0
        assert null_col_stats.unique_count < null_col_stats.total_count

    async def test_categorical_statistics(self, stats_engine, mixed_dataframe):
        """Test statistics for categorical columns"""
        column_types = {'category': 'categorical'}
        df = mixed_dataframe[['category']]
        
        stats = await stats_engine.calculate_statistics(df, column_types)
        col_stats = stats.column_statistics[0]
        
        assert col_stats.unique_count == 3  # A, B, C
        assert len(col_stats.most_frequent_values) > 0
        assert col_stats.most_frequent_values[0]['value'] in ['A', 'B', 'C']
        assert col_stats.mode in ['A', 'B', 'C']

    async def test_datetime_statistics(self, stats_engine, mixed_dataframe):
        """Test statistics for datetime columns"""
        column_types = {'date': 'datetime'}
        df = mixed_dataframe[['date']]
        
        stats = await stats_engine.calculate_statistics(df, column_types)
        col_stats = stats.column_statistics[0]
        
        assert col_stats.earliest_date is not None
        assert col_stats.latest_date is not None
        assert col_stats.date_range_days == 99  # 100 days from 2023-01-01

    async def test_string_statistics(self, stats_engine):
        """Test statistics for string columns"""
        df = pd.DataFrame({
            'text': ['short', 'medium length', 'this is a longer string', 'tiny']
        })
        column_types = {'text': 'string'}
        
        stats = await stats_engine.calculate_statistics(df, column_types)
        col_stats = stats.column_statistics[0]
        
        assert col_stats.avg_length > 0
        assert col_stats.min_length == 4  # 'tiny'
        assert col_stats.max_length == 23  # 'this is a longer string'

    async def test_correlation_matrix(self, stats_engine, numeric_dataframe):
        """Test correlation matrix calculation"""
        column_types = {col: 'float' for col in numeric_dataframe.columns}
        stats = await stats_engine.calculate_statistics(numeric_dataframe, column_types)
        
        assert stats.correlation_matrix is not None
        assert len(stats.correlation_matrix) == len(numeric_dataframe.columns)
        
        # Check diagonal is 1.0 (self-correlation)
        for col in numeric_dataframe.columns:
            assert stats.correlation_matrix[col][col] == pytest.approx(1.0)

    async def test_missing_value_summary(self, stats_engine):
        """Test missing value pattern analysis"""
        df = pd.DataFrame({
            'complete': [1, 2, 3, 4, 5],
            'some_missing': [1, None, 3, None, 5],
            'mostly_missing': [None, None, 3, None, None]
        })
        column_types = {col: 'integer' for col in df.columns}
        
        stats = await stats_engine.calculate_statistics(df, column_types)
        missing_summary = stats.missing_value_summary
        
        assert missing_summary['total_missing_values'] == 6
        assert missing_summary['columns_with_missing'] == 2
        assert missing_summary['complete_columns'] == 1
        assert missing_summary['missing_by_column']['some_missing']['count'] == 2
        assert missing_summary['missing_by_column']['mostly_missing']['percentage'] == 80.0

    async def test_currency_statistics(self, stats_engine):
        """Test statistics for currency data"""
        df = pd.DataFrame({
            'price': ['$100.50', '$1,234.56', '$50.00', '$999.99']
        })
        column_types = {'price': 'currency'}
        
        stats = await stats_engine.calculate_statistics(df, column_types)
        col_stats = stats.column_statistics[0]
        
        assert col_stats.mean is not None
        assert col_stats.min_value == 50.00
        assert col_stats.max_value == 1234.56

    async def test_percentage_statistics(self, stats_engine):
        """Test statistics for percentage data"""
        df = pd.DataFrame({
            'rate': ['10%', '25.5%', '50%', '75%', '100%']
        })
        column_types = {'rate': 'percentage'}
        
        stats = await stats_engine.calculate_statistics(df, column_types)
        col_stats = stats.column_statistics[0]
        
        assert col_stats.mean == pytest.approx(0.521)  # Average of 0.1, 0.255, 0.5, 0.75, 1.0
        assert col_stats.min_value == 0.1
        assert col_stats.max_value == 1.0

    async def test_most_frequent_values(self, stats_engine):
        """Test most frequent value tracking"""
        df = pd.DataFrame({
            'col': ['A', 'A', 'B', 'A', 'C', 'B', 'A', 'D', 'E', 'F']
        })
        column_types = {'col': 'categorical'}
        
        stats = await stats_engine.calculate_statistics(df, column_types)
        col_stats = stats.column_statistics[0]
        
        assert len(col_stats.most_frequent_values) > 0
        assert col_stats.most_frequent_values[0]['value'] == 'A'
        assert col_stats.most_frequent_values[0]['count'] == 4
        assert col_stats.most_frequent_values[0]['percentage'] == 40.0

    async def test_memory_usage(self, stats_engine, numeric_dataframe):
        """Test memory usage calculation"""
        column_types = {col: 'float' for col in numeric_dataframe.columns}
        stats = await stats_engine.calculate_statistics(numeric_dataframe, column_types)
        
        assert stats.memory_usage_mb > 0
        # Rough estimate: 1000 rows * 4 columns * 8 bytes per float / 1MB
        assert stats.memory_usage_mb < 1.0  # Should be less than 1MB for this data

    async def test_empty_dataframe(self, stats_engine):
        """Test handling of empty dataframe"""
        df = pd.DataFrame()
        column_types = {}
        
        stats = await stats_engine.calculate_statistics(df, column_types)
        
        assert stats.row_count == 0
        assert stats.column_count == 0
        assert len(stats.column_statistics) == 0