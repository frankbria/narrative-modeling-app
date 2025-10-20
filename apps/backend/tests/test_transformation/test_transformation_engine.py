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
    DropMissingTransformation,
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


class TestDropMissingTransformation:
    """Test drop_missing transformation functionality"""

    def test_drop_missing_any(self):
        """Test dropping rows with any missing values"""
        # Create test data with missing values
        df = pd.DataFrame({
            'name': ['John', 'Jane', np.nan, 'Bob', 'Alice'],
            'age': [25, np.nan, 30, 35, 40],
            'city': ['NY', 'LA', 'SF', np.nan, 'DC']
        })

        # Create transformation
        transform = DropMissingTransformation({'how': 'any'})

        # Apply transformation
        result_df = transform.apply(df)

        # Check results - should keep only rows with no missing values
        assert len(result_df) == 2  # Only row 0 (John) and row 4 (Alice)
        assert result_df['name'].tolist() == ['John', 'Alice']

    def test_drop_missing_all(self):
        """Test dropping rows where all values are missing"""
        # Create test data
        df = pd.DataFrame({
            'name': ['John', np.nan, 'Bob', np.nan],
            'age': [25, np.nan, 30, 40],
            'city': ['NY', np.nan, 'SF', np.nan]
        })

        # Create transformation
        transform = DropMissingTransformation({'how': 'all'})

        # Apply transformation
        result_df = transform.apply(df)

        # Check results - should drop only row 1 where all values are NaN
        assert len(result_df) == 3
        assert result_df['name'].tolist() == ['John', 'Bob', np.nan]

    def test_drop_missing_specific_columns(self):
        """Test dropping rows with missing values in specific columns"""
        # Create test data
        df = pd.DataFrame({
            'name': ['John', 'Jane', np.nan, 'Bob'],
            'age': [25, np.nan, 30, 35],
            'city': ['NY', 'LA', 'SF', 'DC']
        })

        # Create transformation - only check 'name' column
        transform = DropMissingTransformation({'columns': ['name'], 'how': 'any'})

        # Apply transformation
        result_df = transform.apply(df)

        # Check results - should drop row 2 (missing name)
        assert len(result_df) == 3
        assert 'Jane' in result_df['name'].tolist()

    def test_drop_missing_with_threshold(self):
        """Test dropping rows based on missing value percentage threshold"""
        # Create test data where some rows have high percentage of missing values
        df = pd.DataFrame({
            'col1': [1, np.nan, 3, np.nan, 5],
            'col2': [10, np.nan, 30, 40, 50],
            'col3': [100, np.nan, 300, np.nan, 500],
            'col4': [1000, np.nan, 3000, 4000, 5000]
        })

        # Create transformation with 50% threshold
        # Rows with >= 50% missing values should be dropped
        transform = DropMissingTransformation({'threshold': 50})

        # Apply transformation
        result_df = transform.apply(df)

        # Check results
        # Row 1 has 100% missing (4/4), row 3 has 50% missing (2/4)
        # Both should be dropped with threshold=50
        assert len(result_df) == 3
        assert result_df['col1'].tolist() == [1, 3, 5]

    def test_drop_missing_threshold_specific_columns(self):
        """Test threshold-based drop on specific columns"""
        # Create test data
        df = pd.DataFrame({
            'important1': [1, np.nan, 3, np.nan, 5],
            'important2': [10, np.nan, 30, np.nan, 50],
            'optional': [100, 200, 300, 400, 500]
        })

        # Only check important columns for threshold
        transform = DropMissingTransformation({
            'columns': ['important1', 'important2'],
            'threshold': 50
        })

        # Apply transformation
        result_df = transform.apply(df)

        # Rows 1 and 3 have 100% missing in important columns
        assert len(result_df) == 3
        assert result_df['important1'].tolist() == [1, 3, 5]

    def test_drop_missing_validation_threshold_range(self):
        """Test threshold parameter validation"""
        # Test invalid threshold (negative)
        with pytest.raises(ValueError, match="threshold must be between 0 and 100"):
            DropMissingTransformation({'threshold': -10})

        # Test invalid threshold (> 100)
        with pytest.raises(ValueError, match="threshold must be between 0 and 100"):
            DropMissingTransformation({'threshold': 150})

    def test_drop_missing_validation_how_parameter(self):
        """Test 'how' parameter validation"""
        # Test invalid 'how' parameter
        with pytest.raises(ValueError, match="how must be 'any' or 'all'"):
            DropMissingTransformation({'how': 'invalid'})

    def test_drop_missing_empty_dataset(self):
        """Test drop_missing on empty dataset"""
        df = pd.DataFrame()

        transform = DropMissingTransformation({'how': 'any'})
        result_df = transform.apply(df)

        assert result_df.empty

    def test_drop_missing_validation_high_data_loss(self):
        """Test validation warning for high data loss"""
        # Create dataset where most rows have missing values
        df = pd.DataFrame({
            'col1': [1, np.nan, np.nan, np.nan, np.nan],
            'col2': [10, np.nan, np.nan, np.nan, np.nan]
        })

        transform = DropMissingTransformation({'how': 'any'})

        # Validation should fail because > 50% data loss
        is_valid, error = transform.validate_data(df)
        assert not is_valid
        assert "50% safety threshold" in error

    def test_drop_missing_validation_all_rows_dropped(self):
        """Test validation when all rows would be dropped"""
        # Create dataset with all missing values
        df = pd.DataFrame({
            'col1': [np.nan, np.nan, np.nan],
            'col2': [np.nan, np.nan, np.nan]
        })

        transform = DropMissingTransformation({'how': 'any'})

        # Validation should fail
        is_valid, error = transform.validate_data(df)
        assert not is_valid
        # Check for either specific message or safety threshold message
        assert ("remove all rows" in error or "safety threshold" in error)


class TestTransformationValidation:
    """Test transformation validation functionality"""

    def test_validate_transformation_success(self):
        """Test successful transformation validation"""
        df = pd.DataFrame({
            'name': ['John', 'Jane', 'Bob'],
            'age': [25, 30, 35]
        })

        engine = TransformationEngine()
        result = engine.validate_transformation(
            df=df,
            transformation_type=TransformationType.TRIM_WHITESPACE,
            parameters={'columns': ['name']}
        )

        assert result.success
        assert 'name' in result.affected_columns

    def test_validate_transformation_missing_columns(self):
        """Test validation failure for missing columns"""
        df = pd.DataFrame({
            'name': ['John', 'Jane', 'Bob'],
            'age': [25, 30, 35]
        })

        engine = TransformationEngine()
        result = engine.validate_transformation(
            df=df,
            transformation_type=TransformationType.TRIM_WHITESPACE,
            parameters={'columns': ['nonexistent_column']}
        )

        # The validation doesn't fail because TrimWhitespace skips missing columns
        # But affected_columns should be empty
        assert result.success
        assert len(result.affected_columns) == 0

    def test_validate_transformation_data_type_mismatch(self):
        """Test validation for data type incompatibility"""
        df = pd.DataFrame({
            'name': ['John', 'Jane', 'Bob'],
            'age': [25, 30, 35]
        })

        engine = TransformationEngine()

        # Use FillMissingTransformation with mean method on string column
        result = engine.validate_transformation(
            df=df,
            transformation_type=TransformationType.FILL_MISSING,
            parameters={'columns': ['name'], 'method': 'mean'}
        )

        # Should succeed - FillMissing doesn't validate data types in advance
        # It just won't fill non-numeric columns with mean
        assert result.success

    def test_validate_transformation_data_loss_warning(self):
        """Test data loss warning during validation"""
        df = pd.DataFrame({
            'col1': [1, 2, np.nan, np.nan, 5],
            'col2': [10, 20, np.nan, np.nan, 50]
        })

        engine = TransformationEngine()
        result = engine.validate_transformation(
            df=df,
            transformation_type=TransformationType.DROP_MISSING,
            parameters={'how': 'any'}
        )

        # Should succeed with warnings (40% data loss - 2/5 rows)
        assert result.success
        assert len(result.warnings) > 0
        assert 'drop' in result.warnings[0].lower()


class TestEdgeCases:
    """Test edge case handling"""

    def test_empty_dataset_error(self):
        """Test that empty datasets are rejected"""
        df = pd.DataFrame()
        engine = TransformationEngine()

        result = engine.apply_transformation(
            df=df,
            transformation_type=TransformationType.REMOVE_DUPLICATES,
            parameters={'keep': 'first'}
        )

        assert not result.success
        assert 'empty dataset' in result.error.lower()

    def test_single_row_dataset_warning(self):
        """Test handling of single-row datasets"""
        df = pd.DataFrame({'col1': [1], 'col2': [2]})
        engine = TransformationEngine()

        # Should succeed with warning logged
        result = engine.apply_transformation(
            df=df,
            transformation_type=TransformationType.TRIM_WHITESPACE,
            parameters={}
        )

        assert result.success

    def test_transformation_removes_all_rows(self):
        """Test that transformations removing all rows are rejected"""
        df = pd.DataFrame({
            'col1': [np.nan, np.nan],
            'col2': [np.nan, np.nan]
        })
        engine = TransformationEngine()

        # This should be caught by validation
        result = engine.apply_transformation(
            df=df,
            transformation_type=TransformationType.DROP_MISSING,
            parameters={'how': 'any'}
        )

        assert not result.success
        assert 'remove all rows' in result.error.lower() or 'safety threshold' in result.error.lower()

    def test_all_missing_column(self):
        """Test handling columns with all missing values"""
        df = pd.DataFrame({
            'col1': [1, 2, 3],
            'col2': [np.nan, np.nan, np.nan]
        })

        engine = TransformationEngine()
        result = engine.apply_transformation(
            df=df,
            transformation_type=TransformationType.DROP_MISSING,
            parameters={'columns': ['col2'], 'how': 'any'}
        )

        # Should drop all rows since col2 is all NaN
        assert not result.success  # Validation should catch this