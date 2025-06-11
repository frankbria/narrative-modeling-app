"""
Tests for feature engineering
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

from app.services.model_training.feature_engineer import (
    FeatureEngineer,
    FeatureEngineeringConfig,
    FeatureEngineeringResult
)


class TestFeatureEngineer:
    """Test suite for feature engineering"""
    
    @pytest.fixture
    def config(self):
        """Create feature engineering config"""
        return FeatureEngineeringConfig(
            handle_missing=True,
            scale_features=True,
            encode_categorical=True,
            create_interactions=False,
            select_features=True,
            max_features=10
        )
    
    @pytest.fixture
    def engineer(self, config):
        """Create feature engineer instance"""
        return FeatureEngineer(config)
    
    @pytest.fixture
    def mixed_data(self):
        """Create dataset with mixed types and missing values"""
        np.random.seed(42)
        n_samples = 100
        return pd.DataFrame({
            'numeric1': np.random.randn(n_samples),
            'numeric2': np.random.randn(n_samples),
            'numeric3': np.concatenate([np.random.randn(90), [np.nan] * 10]),
            'categorical1': np.random.choice(['A', 'B', 'C'], n_samples),
            'categorical2': np.concatenate([
                np.random.choice(['X', 'Y', 'Z'], 95),
                [np.nan] * 5
            ]),
            'numeric_categorical': np.random.choice([0, 1, 2, 3], n_samples)  # 4 values < 5% threshold
        })
    
    @pytest.fixture
    def target_classification(self):
        """Create classification target"""
        np.random.seed(42)
        return pd.Series(np.random.choice([0, 1], 100))
    
    @pytest.fixture
    def target_regression(self):
        """Create regression target"""
        np.random.seed(42)
        return pd.Series(np.random.randn(100) * 10 + 50)
    
    @pytest.mark.asyncio
    async def test_identify_feature_types(self, engineer, mixed_data):
        """Test feature type identification"""
        engineer._identify_feature_types(mixed_data)
        
        # Check numeric features (numeric_categorical should be moved to categorical)
        assert set(engineer.numeric_features) == {'numeric1', 'numeric2', 'numeric3'}
        
        # Check categorical features
        assert set(engineer.categorical_features) == {
            'categorical1', 'categorical2', 'numeric_categorical'
        }
    
    @pytest.mark.asyncio
    async def test_handle_missing_values(self, engineer, mixed_data):
        """Test missing value handling"""
        engineer._identify_feature_types(mixed_data)
        
        # Handle missing values
        result = await engineer._handle_missing_values(mixed_data.copy())
        
        # Check no missing values remain
        assert result.isnull().sum().sum() == 0
        
        # Check transformers were saved
        assert 'imputer_numeric' in engineer.transformers
        assert 'imputer_categorical' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_encode_categorical_onehot(self, engineer, mixed_data):
        """Test one-hot encoding of categorical features"""
        engineer._identify_feature_types(mixed_data)
        engineer.config.encoding_method = "onehot"
        
        # Clean data first
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        
        # Encode categorical
        result = await engineer._encode_categorical_features(clean_data)
        
        # Check original categorical columns were removed
        for col in engineer.categorical_features:
            assert col not in result.columns
        
        # Check new encoded columns exist
        assert len(result.columns) > len(mixed_data.columns)
        
        # Check encoder was saved
        assert 'encoder' in engineer.transformers
        assert 'encoded_columns' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_encode_categorical_label(self, engineer, mixed_data):
        """Test label encoding of categorical features"""
        engineer._identify_feature_types(mixed_data)
        engineer.config.encoding_method = "label"
        
        # Clean data first
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        
        # Encode categorical
        result = await engineer._encode_categorical_features(clean_data)
        
        # Check categorical columns are now numeric
        for col in engineer.categorical_features:
            assert pd.api.types.is_numeric_dtype(result[col])
        
        # Check label encoders were saved
        assert 'label_encoders' in engineer.transformers
        assert len(engineer.transformers['label_encoders']) == len(engineer.categorical_features)
    
    @pytest.mark.asyncio
    async def test_scale_numeric_features(self, engineer, mixed_data):
        """Test numeric feature scaling"""
        engineer._identify_feature_types(mixed_data)
        
        # Clean data first
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        
        # Scale features
        result = await engineer._scale_numeric_features(clean_data)
        
        # Check scaled values
        for col in engineer.numeric_features:
            # Standard scaling should have mean ~0 and std ~1
            assert abs(result[col].mean()) < 0.1
            assert abs(result[col].std() - 1) < 0.1
        
        # Check scaler was saved
        assert 'scaler' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_create_interaction_features(self, engineer):
        """Test interaction feature creation"""
        # Create simple numeric data
        df = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5],
            'feature2': [2, 4, 6, 8, 10],
            'feature3': [1, 1, 1, 1, 1]
        })
        
        engineer.numeric_features = ['feature1', 'feature2', 'feature3']
        engineer.config.create_interactions = True
        
        result = await engineer._create_interaction_features(df.copy())
        
        # Check interaction columns were created
        assert 'feature1_x_feature2' in result.columns
        assert 'feature1_div_feature2' in result.columns
        
        # Check interaction values
        assert list(result['feature1_x_feature2']) == [2, 8, 18, 32, 50]
        
        # Check interaction features were saved
        assert 'interaction_features' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_select_features_classification(self, engineer, mixed_data, target_classification):
        """Test feature selection for classification"""
        engineer._identify_feature_types(mixed_data)
        
        # Prepare data
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        encoded_data = await engineer._encode_categorical_features(clean_data)
        
        # Select features
        result, importance = await engineer._select_features(
            encoded_data, target_classification, "classification"
        )
        
        # Check dimensions
        assert result.shape[1] <= engineer.config.max_features
        assert result.shape[1] <= encoded_data.shape[1]
        
        # Check importance scores
        assert importance is not None
        assert len(importance) == result.shape[1]
        assert all(score >= 0 for score in importance.values())
        
        # Check selector was saved
        assert 'selector' in engineer.transformers
        assert 'selected_features' in engineer.transformers
    
    @pytest.mark.asyncio
    async def test_fit_transform_complete_pipeline(self, engineer, mixed_data, target_classification):
        """Test complete fit_transform pipeline"""
        result = await engineer.fit_transform(
            mixed_data,
            target_classification,
            "classification"
        )
        
        # Check result type
        assert isinstance(result, FeatureEngineeringResult)
        
        # Check transformed data
        assert isinstance(result.X_transformed, pd.DataFrame)
        assert result.X_transformed.shape[0] == mixed_data.shape[0]
        assert result.X_transformed.isnull().sum().sum() == 0  # No missing values
        
        # Check feature names
        assert len(result.feature_names) == result.X_transformed.shape[1]
        assert result.feature_names == list(result.X_transformed.columns)
        
        # Check metadata
        assert 'original_features' in result.metadata
        assert 'numeric_features' in result.metadata
        assert 'categorical_features' in result.metadata
        assert result.metadata['final_feature_count'] == len(result.feature_names)
    
    @pytest.mark.asyncio
    async def test_transform_new_data(self, engineer, mixed_data, target_classification):
        """Test transforming new data with fitted engineer"""
        # Fit on training data
        await engineer.fit_transform(
            mixed_data.iloc[:80],
            target_classification.iloc[:80],
            "classification"
        )
        
        # Transform test data
        test_data = mixed_data.iloc[80:].copy()
        result = await engineer.transform(test_data)
        
        # Check result
        assert isinstance(result, pd.DataFrame)
        assert result.shape[0] == test_data.shape[0]
        assert result.shape[1] == len(engineer.feature_names)
        assert list(result.columns) == engineer.feature_names
    
    @pytest.mark.asyncio
    async def test_different_scaling_methods(self, engineer, mixed_data):
        """Test different scaling methods"""
        engineer._identify_feature_types(mixed_data)
        clean_data = await engineer._handle_missing_values(mixed_data.copy())
        
        # Test MinMax scaling
        engineer.config.scaling_method = "minmax"
        result_minmax = await engineer._scale_numeric_features(clean_data.copy())
        
        for col in engineer.numeric_features:
            assert result_minmax[col].min() >= -1e-10  # Allow small numerical errors
            assert result_minmax[col].max() <= 1 + 1e-10
        
        # Test Robust scaling
        engineer.config.scaling_method = "robust"
        engineer.transformers = {}  # Reset transformers
        result_robust = await engineer._scale_numeric_features(clean_data.copy())
        
        # Robust scaling centers on median
        for col in engineer.numeric_features:
            assert abs(result_robust[col].median()) < 0.1
    
    @pytest.mark.asyncio
    async def test_no_feature_selection(self, engineer, mixed_data, target_classification):
        """Test pipeline without feature selection"""
        engineer.config.select_features = False
        
        result = await engineer.fit_transform(
            mixed_data,
            target_classification,
            "classification"
        )
        
        # All features should be kept (after encoding)
        assert 'selector' not in engineer.transformers
        assert result.feature_importance is None
    
    @pytest.mark.asyncio
    async def test_handle_edge_cases(self, engineer):
        """Test handling of edge cases"""
        # Empty dataframe
        empty_df = pd.DataFrame()
        result = await engineer.fit_transform(empty_df)
        assert result.X_transformed.empty
        
        # Single column
        single_col = pd.DataFrame({'col1': [1, 2, 3, 4, 5]})
        result = await engineer.fit_transform(single_col)
        assert result.X_transformed.shape[1] == 1
        
        # All missing values
        all_missing = pd.DataFrame({
            'col1': [np.nan] * 5,
            'col2': [np.nan] * 5
        })
        result = await engineer.fit_transform(all_missing)
        assert result.X_transformed.isnull().sum().sum() == 0