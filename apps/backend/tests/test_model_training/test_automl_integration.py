"""
Integration tests for complete AutoML pipeline
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from app.services.model_training import (
    AutoMLEngine,
    ProblemDetector,
    FeatureEngineer,
    FeatureEngineeringConfig,
    ProblemType
)


class TestAutoMLIntegration:
    """Integration tests for the complete AutoML pipeline"""
    
    @pytest.fixture
    def iris_like_data(self):
        """Create an iris-like classification dataset"""
        np.random.seed(42)
        n_samples = 150
        
        # Create features with some separability
        class_0 = np.random.randn(50, 4) + [5.0, 3.0, 1.5, 0.2]
        class_1 = np.random.randn(50, 4) + [5.9, 2.7, 4.2, 1.3]
        class_2 = np.random.randn(50, 4) + [6.5, 3.0, 5.5, 2.0]
        
        features = np.vstack([class_0, class_1, class_2])
        target = np.array([0] * 50 + [1] * 50 + [2] * 50)
        
        df = pd.DataFrame(
            features,
            columns=['sepal_length', 'sepal_width', 'petal_length', 'petal_width']
        )
        df['species'] = target
        
        return df
    
    @pytest.fixture
    def housing_like_data(self):
        """Create a housing price-like regression dataset"""
        np.random.seed(42)
        n_samples = 200
        
        # Features
        size = np.random.uniform(500, 3000, n_samples)
        bedrooms = np.random.choice([1, 2, 3, 4, 5], n_samples, p=[0.1, 0.3, 0.4, 0.15, 0.05])
        age = np.random.uniform(0, 50, n_samples)
        location = np.random.choice(['urban', 'suburban', 'rural'], n_samples, p=[0.4, 0.4, 0.2])
        
        # Price with relationships
        price = (
            100000 +  # base price
            100 * size +  # $100 per sq ft
            10000 * bedrooms +  # $10k per bedroom
            -1000 * age +  # depreciation
            (location == 'urban').astype(int) * 50000 +  # urban premium
            (location == 'suburban').astype(int) * 20000 +  # suburban premium
            np.random.normal(0, 20000, n_samples)  # noise
        )
        
        df = pd.DataFrame({
            'size_sqft': size,
            'bedrooms': bedrooms,
            'age_years': age,
            'location': location,
            'price': price
        })
        
        return df
    
    @pytest.fixture
    def time_series_data(self):
        """Create time series dataset"""
        dates = pd.date_range(start='2023-01-01', periods=365, freq='D')
        
        # Create seasonal pattern with trend
        trend = np.linspace(100, 150, 365)
        seasonal = 10 * np.sin(2 * np.pi * np.arange(365) / 365)
        noise = np.random.normal(0, 5, 365)
        
        values = trend + seasonal + noise
        
        df = pd.DataFrame({
            'date': dates,
            'temperature': np.random.uniform(10, 30, 365),
            'humidity': np.random.uniform(30, 80, 365),
            'sales': values
        })
        
        return df
    
    @pytest.mark.asyncio
    async def test_multiclass_classification_pipeline(self, iris_like_data):
        """Test full pipeline on multiclass classification"""
        # Initialize components
        engine = AutoMLEngine(max_models=3, cv_folds=3, random_state=42)
        
        # Run AutoML
        result = await engine.run(iris_like_data, 'species')
        
        # Verify problem detection
        assert result.problem_type == ProblemType.MULTICLASS_CLASSIFICATION
        
        # Verify models were trained
        assert len(result.all_models) > 0
        assert result.best_model is not None
        
        # Verify reasonable performance (with random data, scores will be lower)
        assert result.best_model.cv_score > 0.6
        assert result.best_model.test_score > 0.6
        
        # Verify feature importance
        if result.feature_importance:
            # Petal features should be important for iris
            important_features = list(result.feature_importance.keys())[:2]
            assert any('petal' in feat for feat in important_features)
    
    @pytest.mark.asyncio
    async def test_regression_pipeline_with_categorical(self, housing_like_data):
        """Test full pipeline on regression with categorical features"""
        # Initialize with specific config
        config = FeatureEngineeringConfig(
            handle_missing=True,
            scale_features=True,
            encode_categorical=True,
            create_interactions=True,
            select_features=True,
            max_features=15
        )
        
        engine = AutoMLEngine(max_models=4, cv_folds=3, random_state=42)
        
        # Run AutoML
        result = await engine.run(housing_like_data, 'price', config)
        
        # Verify problem detection
        assert result.problem_type == ProblemType.REGRESSION
        
        # Verify categorical encoding happened
        assert result.metadata['n_features_engineered'] > result.metadata['n_features_original']
        
        # Verify models were trained
        assert len(result.all_models) > 0
        
        # Best model should have reasonable R² score
        assert result.best_model.test_score > 0.5  # Adjusted for synthetic data
        
        # Size should be important feature
        if result.feature_importance:
            assert any('size' in feat for feat in result.feature_importance.keys())
    
    @pytest.mark.asyncio
    async def test_binary_classification_with_missing_data(self):
        """Test pipeline with missing data"""
        np.random.seed(42)
        n_samples = 200
        
        # Create data with missing values
        df = pd.DataFrame({
            'feature1': np.concatenate([np.random.randn(180), [np.nan] * 20]),
            'feature2': np.concatenate([np.random.randn(190), [np.nan] * 10]),
            'feature3': np.random.choice(['A', 'B', 'C', np.nan], n_samples),
            'target': np.random.choice([0, 1], n_samples)
        })
        
        engine = AutoMLEngine(max_models=3, cv_folds=3, random_state=42)
        
        # Should handle missing values automatically
        result = await engine.run(df, 'target')
        
        assert result.problem_type == ProblemType.BINARY_CLASSIFICATION
        assert len(result.all_models) > 0
        assert result.best_model.cv_score is not None
    
    @pytest.mark.asyncio
    async def test_time_series_detection_and_handling(self, time_series_data):
        """Test time series problem detection"""
        detector = ProblemDetector()
        
        # Detect with datetime column
        detection_result = await detector.detect_problem_type(
            time_series_data,
            target_column='sales',
            datetime_column='date'
        )
        
        assert detection_result.problem_type == ProblemType.TIME_SERIES_REGRESSION
        assert detection_result.confidence > 0.8
    
    @pytest.mark.asyncio
    async def test_small_dataset_handling(self):
        """Test pipeline with small dataset"""
        # Create tiny dataset
        df = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'feature2': [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            'target': [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
        })
        
        engine = AutoMLEngine(max_models=2, cv_folds=2, test_size=0.3, random_state=42)
        
        # Should still work with small data
        result = await engine.run(df, 'target')
        
        assert result.problem_type == ProblemType.BINARY_CLASSIFICATION
        assert len(result.all_models) > 0
    
    @pytest.mark.asyncio
    async def test_high_cardinality_categorical(self):
        """Test handling of high cardinality categorical features"""
        np.random.seed(42)
        n_samples = 500
        
        # Create dataset with high cardinality feature
        df = pd.DataFrame({
            'user_id': [f'user_{i}' for i in range(n_samples)],  # Unique per row
            'category': np.random.choice(['A', 'B', 'C', 'D', 'E'], n_samples),
            'numeric1': np.random.randn(n_samples),
            'numeric2': np.random.randn(n_samples),
            'target': np.random.choice([0, 1], n_samples)
        })
        
        config = FeatureEngineeringConfig(
            encode_categorical=True,
            select_features=True,
            max_features=10  # Limit features to avoid explosion
        )
        
        engine = AutoMLEngine(max_models=2, cv_folds=3, random_state=42)
        
        result = await engine.run(df, 'target', config)
        
        # Should handle high cardinality without exploding feature count
        assert result.metadata['n_features_engineered'] <= 20  # Reasonable limit
        assert len(result.all_models) > 0
    
    @pytest.mark.asyncio
    async def test_numeric_categorical_detection(self):
        """Test detection of numeric columns that are actually categorical"""
        np.random.seed(42)
        n_samples = 200
        
        df = pd.DataFrame({
            'store_id': np.random.choice([1, 2, 3, 4, 5], n_samples),  # Numeric but categorical
            'month': np.random.choice(range(1, 13), n_samples),  # Also categorical
            'sales_amount': np.random.uniform(100, 1000, n_samples),
            'temperature': np.random.uniform(60, 90, n_samples),
            'is_weekend': np.random.choice([0, 1], n_samples)
        })
        df['target'] = (df['sales_amount'] > 500).astype(int)
        
        engine = AutoMLEngine(max_models=3, cv_folds=3, random_state=42)
        
        result = await engine.run(df, 'target')
        
        # store_id and month should be treated as categorical
        assert 'categorical_features' in result.metadata['feature_engineering']
        categorical_features = result.metadata['feature_engineering']['categorical_features']
        assert 'store_id' in categorical_features or any('store_id' in str(f) for f in result.feature_names)
    
    @pytest.mark.asyncio
    async def test_feature_importance_consistency(self, housing_like_data):
        """Test that feature importance is consistent with known relationships"""
        engine = AutoMLEngine(max_models=3, cv_folds=3, random_state=42)
        
        result = await engine.run(housing_like_data, 'price')
        
        if result.feature_importance:
            # Get top features
            top_features = list(result.feature_importance.keys())[:5]
            top_feature_str = ' '.join(top_features).lower()
            
            # Size should be one of the most important features
            assert 'size' in top_feature_str
            
            # Either bedrooms or age should also be important
            assert 'bedroom' in top_feature_str or 'age' in top_feature_str
    
    @pytest.mark.asyncio
    async def test_model_diversity(self, iris_like_data):
        """Test that different types of models are trained"""
        engine = AutoMLEngine(max_models=5, cv_folds=3, random_state=42)
        
        result = await engine.run(iris_like_data, 'species')
        
        # Check model diversity
        model_types = [m.name for m in result.all_models]
        
        # Should have at least 2 different model types
        assert len(set(model_types)) >= 2
        
        # Common models should be included
        assert any('Forest' in name for name in model_types)  # Random Forest
        assert any('Logistic' in name or 'XGBoost' in name or 'LightGBM' in name 
                  for name in model_types)