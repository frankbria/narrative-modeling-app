"""
Tests for transformation engine
"""
import pytest
import pandas as pd
import numpy as np
from app.services.transformation_service.transformation_engine import (
    TransformationEngine,
    TransformationType,
    RemoveDuplicatesTransformation,
    TrimWhitespaceTransformation,
    FillMissingTransformation,
)


class TestTransformationEngine:
    """Test transformation engine functionality"""
    
    def test_remove_duplicates(self):
        """Test removing duplicate rows"""
        # Create test data with duplicates
        df = pd.DataFrame({
            'id': [1, 2, 2, 3, 3, 3],
            'name': ['A', 'B', 'B', 'C', 'C', 'C'],
            'value': [10, 20, 20, 30, 30, 30]
        })
        
        # Create transformation
        transform = RemoveDuplicatesTransformation({'keep': 'first'})
        
        # Apply transformation
        result_df = transform.apply(df)
        
        # Check results
        assert len(result_df) == 3
        assert result_df['id'].tolist() == [1, 2, 3]
        assert result_df['name'].tolist() == ['A', 'B', 'C']
    
    def test_trim_whitespace(self):
        """Test trimming whitespace from strings"""
        # Create test data with whitespace
        df = pd.DataFrame({
            'name': ['  John  ', 'Jane\t', '\nBob'],
            'value': [1, 2, 3]
        })
        
        # Create transformation
        transform = TrimWhitespaceTransformation({'columns': ['name']})
        
        # Apply transformation
        result_df = transform.apply(df)
        
        # Check results
        assert result_df['name'].tolist() == ['John', 'Jane', 'Bob']
        assert result_df['value'].tolist() == [1, 2, 3]
    
    def test_fill_missing_with_value(self):
        """Test filling missing values with specific value"""
        # Create test data with missing values
        df = pd.DataFrame({
            'name': ['John', np.nan, 'Bob'],
            'age': [25, np.nan, 30],
            'city': ['NY', 'LA', np.nan]
        })
        
        # Create transformation
        transform = FillMissingTransformation({
            'columns': ['name', 'city'],
            'value': 'Unknown'
        })
        
        # Apply transformation
        result_df = transform.apply(df)
        
        # Check results
        assert result_df['name'].tolist() == ['John', 'Unknown', 'Bob']
        assert result_df['city'].tolist() == ['NY', 'LA', 'Unknown']
        assert pd.isna(result_df['age'].iloc[1])  # age not in columns list
    
    def test_fill_missing_with_mean(self):
        """Test filling missing values with mean"""
        # Create test data
        df = pd.DataFrame({
            'age': [20, np.nan, 30, np.nan, 40],
            'score': [85, 90, np.nan, 95, 100]
        })
        
        # Create transformation
        transform = FillMissingTransformation({
            'columns': ['age', 'score'],
            'method': 'mean'
        })
        
        # Apply transformation
        result_df = transform.apply(df)
        
        # Check results
        assert result_df['age'].tolist() == [20, 30, 30, 30, 40]  # mean of [20,30,40] = 30
        assert result_df['score'].tolist() == [85, 90, 92.5, 95, 100]  # mean of [85,90,95,100] = 92.5
    
    def test_transformation_engine_preview(self):
        """Test transformation preview functionality"""
        # Create test data
        df = pd.DataFrame({
            'id': list(range(200)),
            'value': [i * 2 for i in range(200)]
        })
        
        # Create engine
        engine = TransformationEngine()
        
        # Preview transformation
        result = engine.preview_transformation(
            df=df,
            transformation_type=TransformationType.REMOVE_DUPLICATES,
            parameters={'keep': 'first'},
            n_rows=50
        )
        
        # Check results
        assert result.success
        assert len(result.preview_data) == 50
        assert result.stats_before['row_count'] == 50
        assert result.stats_after['row_count'] == 50
    
    def test_transformation_engine_apply(self):
        """Test applying transformation"""
        # Create test data with duplicates
        df = pd.DataFrame({
            'id': [1, 1, 2, 2, 3],
            'name': ['A', 'A', 'B', 'B', 'C']
        })
        
        # Create engine
        engine = TransformationEngine()
        
        # Apply transformation
        result = engine.apply_transformation(
            df=df,
            transformation_type=TransformationType.REMOVE_DUPLICATES,
            parameters={'keep': 'first'}
        )
        
        # Check results
        assert result.success
        assert len(result.transformed_data) == 3
        assert result.affected_rows == 2
        assert len(engine.get_history()) == 1
    
    def test_transformation_validation(self):
        """Test parameter validation"""
        # Test invalid keep parameter
        with pytest.raises(ValueError):
            RemoveDuplicatesTransformation({'keep': 'invalid'})
        
        # Test missing value or method
        with pytest.raises(ValueError):
            FillMissingTransformation({'columns': ['test']})
        
        # Test invalid method
        with pytest.raises(ValueError):
            FillMissingTransformation({'method': 'invalid'})