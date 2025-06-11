"""
Tests for problem type detection
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.services.model_training.problem_detector import ProblemDetector, ProblemType


class TestProblemDetector:
    """Test suite for problem type detection"""
    
    @pytest.fixture
    def detector(self):
        """Create problem detector instance"""
        return ProblemDetector()
    
    @pytest.fixture
    def binary_classification_data(self):
        """Create binary classification dataset"""
        np.random.seed(42)
        n_samples = 100
        return pd.DataFrame({
            'feature1': np.random.randn(n_samples),
            'feature2': np.random.randn(n_samples),
            'feature3': np.random.choice(['A', 'B', 'C'], n_samples),
            'target': np.random.choice([0, 1], n_samples)
        })
    
    @pytest.fixture
    def multiclass_classification_data(self):
        """Create multiclass classification dataset"""
        np.random.seed(42)
        n_samples = 100
        return pd.DataFrame({
            'feature1': np.random.randn(n_samples),
            'feature2': np.random.randn(n_samples),
            'feature3': np.random.choice(['A', 'B', 'C'], n_samples),
            'class': np.random.choice(['cat', 'dog', 'bird'], n_samples)
        })
    
    @pytest.fixture
    def regression_data(self):
        """Create regression dataset"""
        np.random.seed(42)
        n_samples = 100
        X = np.random.randn(n_samples)
        return pd.DataFrame({
            'feature1': X,
            'feature2': np.random.randn(n_samples),
            'feature3': np.random.choice(['A', 'B', 'C'], n_samples),
            'price': 100 + 50 * X + 10 * np.random.randn(n_samples)
        })
    
    @pytest.fixture
    def time_series_data(self):
        """Create time series dataset"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        values = np.cumsum(np.random.randn(100)) + 100
        return pd.DataFrame({
            'date': dates,
            'feature1': np.random.randn(100),
            'value': values
        })
    
    @pytest.mark.asyncio
    async def test_detect_binary_classification(self, detector, binary_classification_data):
        """Test binary classification detection"""
        result = await detector.detect_problem_type(
            binary_classification_data,
            target_column='target'
        )
        
        assert result.problem_type == ProblemType.BINARY_CLASSIFICATION
        assert result.target_column == 'target'
        assert result.confidence >= 0.9
        assert 'binary classification' in result.reasoning.lower()
        assert result.metadata['unique_values'] == 2
    
    @pytest.mark.asyncio
    async def test_detect_multiclass_classification(self, detector, multiclass_classification_data):
        """Test multiclass classification detection"""
        result = await detector.detect_problem_type(
            multiclass_classification_data,
            target_column='class'
        )
        
        assert result.problem_type == ProblemType.MULTICLASS_CLASSIFICATION
        assert result.target_column == 'class'
        assert result.confidence >= 0.9
        assert 'multiclass classification' in result.reasoning.lower()
        assert result.metadata['unique_values'] == 3
    
    @pytest.mark.asyncio
    async def test_detect_regression(self, detector, regression_data):
        """Test regression detection"""
        result = await detector.detect_problem_type(
            regression_data,
            target_column='price'
        )
        
        assert result.problem_type == ProblemType.REGRESSION
        assert result.target_column == 'price'
        assert result.confidence >= 0.9
        assert 'regression' in result.reasoning.lower()
        assert 'target_stats' in result.metadata
    
    @pytest.mark.asyncio
    async def test_detect_time_series_regression(self, detector, time_series_data):
        """Test time series regression detection"""
        result = await detector.detect_problem_type(
            time_series_data,
            target_column='value',
            datetime_column='date'
        )
        
        assert result.problem_type == ProblemType.TIME_SERIES_REGRESSION
        assert result.target_column == 'value'
        assert result.confidence >= 0.85
        assert 'time series' in result.reasoning.lower()
        assert result.metadata['datetime_column'] == 'date'
    
    @pytest.mark.asyncio
    async def test_detect_clustering_no_target(self, detector):
        """Test clustering detection when no target specified"""
        # Create data without obvious target column
        # Use high cardinality for last column to avoid target inference
        df = pd.DataFrame({
            'feature_a': np.random.randn(50),
            'feature_b': np.random.randn(50),
            'feature_c': np.random.uniform(0, 100, 50)  # High cardinality continuous
        })
        
        result = await detector.detect_problem_type(
            df,
            target_column=None
        )
        
        assert result.problem_type == ProblemType.CLUSTERING
        assert result.target_column is None
        assert result.confidence >= 0.8
        assert 'clustering' in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_infer_target_column(self, detector):
        """Test target column inference"""
        # Test with common target names
        df = pd.DataFrame({
            'feature1': np.random.randn(50),
            'feature2': np.random.randn(50),
            'target': np.random.choice([0, 1], 50)
        })
        
        result = await detector.detect_problem_type(df, target_column=None)
        assert result.target_column == 'target'
        
        # Test with 'label' column
        df2 = pd.DataFrame({
            'feature1': np.random.randn(50),
            'feature2': np.random.randn(50),
            'label': np.random.choice(['A', 'B'], 50)
        })
        
        result2 = await detector.detect_problem_type(df2, target_column=None)
        assert result2.target_column == 'label'
    
    @pytest.mark.asyncio
    async def test_numeric_categorical_detection(self, detector):
        """Test detection of numeric columns that are actually categorical"""
        # Create data with numeric categories (0, 1, 2, 3, 4)
        df = pd.DataFrame({
            'feature1': np.random.randn(100),
            'category_id': np.random.choice([0, 1, 2, 3, 4], 100)
        })
        
        result = await detector.detect_problem_type(df, target_column='category_id')
        assert result.problem_type == ProblemType.MULTICLASS_CLASSIFICATION
        assert 'discrete values' in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_insufficient_data(self, detector):
        """Test handling of insufficient data"""
        df = pd.DataFrame({
            'feature1': [1, 2, 3],
            'target': [0, 1, 0]
        })
        
        result = await detector.detect_problem_type(df, target_column='target')
        assert result.problem_type == ProblemType.UNKNOWN
        assert result.confidence == 0.0
        assert 'not enough samples' in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_missing_target_column(self, detector):
        """Test handling of missing target column"""
        df = pd.DataFrame({
            'feature1': np.random.randn(50),
            'feature2': np.random.randn(50)
        })
        
        result = await detector.detect_problem_type(df, target_column='non_existent')
        assert result.problem_type == ProblemType.UNKNOWN
        assert result.confidence == 0.0
        assert 'not found' in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_datetime_index_detection(self, detector):
        """Test detection with datetime index"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        df = pd.DataFrame({
            'feature1': np.random.randn(100),
            'sales': np.cumsum(np.random.randn(100)) + 100
        }, index=dates)
        
        result = await detector.detect_problem_type(df, target_column='sales')
        assert result.problem_type == ProblemType.TIME_SERIES_REGRESSION
        assert result.metadata['has_datetime_index'] is True