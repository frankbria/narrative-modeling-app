"""
Tests for AutoML engine
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from app.services.model_training.automl_engine import (
    AutoMLEngine,
    AutoMLResult,
    ModelCandidate
)
from app.services.model_training.problem_detector import ProblemType, ProblemDetectionResult
from app.services.model_training.feature_engineer import FeatureEngineeringResult


class TestAutoMLEngine:
    """Test suite for AutoML engine"""
    
    @pytest.fixture
    def engine(self):
        """Create AutoML engine instance"""
        return AutoMLEngine(
            max_models=5,
            cv_folds=3,
            test_size=0.2,
            random_state=42
        )
    
    @pytest.fixture
    def classification_data(self):
        """Create classification dataset"""
        np.random.seed(42)
        n_samples = 200
        X = pd.DataFrame({
            'feature1': np.random.randn(n_samples),
            'feature2': np.random.randn(n_samples),
            'feature3': np.random.choice(['A', 'B', 'C'], n_samples),
            'feature4': np.random.randint(0, 10, n_samples)
        })
        y = pd.Series(np.random.choice([0, 1], n_samples, p=[0.4, 0.6]))
        return X, y
    
    @pytest.fixture
    def regression_data(self):
        """Create regression dataset"""
        np.random.seed(42)
        n_samples = 200
        X = pd.DataFrame({
            'feature1': np.random.randn(n_samples),
            'feature2': np.random.randn(n_samples),
            'feature3': np.random.uniform(0, 100, n_samples),
            'category': np.random.choice(['X', 'Y', 'Z'], n_samples)
        })
        # Create target with some relationship to features
        y = pd.Series(
            10 + 2 * X['feature1'] + 3 * X['feature2'] + 
            0.1 * X['feature3'] + np.random.randn(n_samples)
        )
        return X, y
    
    @pytest.mark.asyncio
    async def test_run_classification_pipeline(self, engine, classification_data):
        """Test complete AutoML pipeline for classification"""
        X, y = classification_data
        df = pd.concat([X, pd.DataFrame({'target': y})], axis=1)
        
        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column='target',
            confidence=0.95,
            reasoning="Binary classification detected",
            metadata={'unique_values': 2}
        )
        
        async def mock_detect(df, target):
            return mock_detection
        
        with patch.object(engine.problem_detector, 'detect_problem_type', 
                         side_effect=mock_detect):
            result = await engine.run(df, 'target')
        
        # Check result structure
        assert isinstance(result, AutoMLResult)
        assert result.problem_type == ProblemType.BINARY_CLASSIFICATION
        assert isinstance(result.best_model, ModelCandidate)
        assert len(result.all_models) > 0
        assert result.training_time > 0
        
        # Check best model has scores
        assert result.best_model.cv_score is not None
        assert result.best_model.test_score is not None
        assert result.best_model.training_time is not None
        
        # Check metadata
        assert 'n_samples' in result.metadata
        assert 'n_features_original' in result.metadata
        assert result.metadata['n_samples'] == len(df)
    
    @pytest.mark.asyncio
    async def test_run_regression_pipeline(self, engine, regression_data):
        """Test complete AutoML pipeline for regression"""
        X, y = regression_data
        df = pd.concat([X, pd.DataFrame({'price': y})], axis=1)
        
        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.REGRESSION,
            target_column='price',
            confidence=0.95,
            reasoning="Regression problem detected",
            metadata={'target_stats': {'mean': 10.0, 'std': 5.0}}
        )
        
        async def mock_detect(df, target):
            return mock_detection
        
        with patch.object(engine.problem_detector, 'detect_problem_type',
                         side_effect=mock_detect):
            result = await engine.run(df, 'price')
        
        # Check result
        assert result.problem_type == ProblemType.REGRESSION
        assert result.best_model is not None
        assert all(m.cv_score is not None for m in result.all_models)
    
    @pytest.mark.asyncio
    async def test_get_candidate_models_classification(self, engine):
        """Test candidate model selection for classification"""
        candidates = engine._get_candidate_models(
            ProblemType.BINARY_CLASSIFICATION,
            (1000, 20)  # n_samples, n_features
        )
        
        # Check we get appropriate models
        model_names = [c.name for c in candidates]
        assert "Logistic Regression" in model_names
        assert "Random Forest" in model_names
        assert "XGBoost" in model_names
        assert "LightGBM" in model_names
        
        # KNN should be included for this size
        assert "K-Nearest Neighbors" in model_names
        
        # Check each candidate has required attributes
        for candidate in candidates:
            assert hasattr(candidate, 'name')
            assert hasattr(candidate, 'estimator')
            assert hasattr(candidate, 'hyperparameters')
    
    @pytest.mark.asyncio
    async def test_get_candidate_models_large_dataset(self, engine):
        """Test candidate model selection for large datasets"""
        candidates = engine._get_candidate_models(
            ProblemType.BINARY_CLASSIFICATION,
            (50000, 100)  # Large dataset
        )
        
        model_names = [c.name for c in candidates]
        
        # SVM and Gradient Boosting should be excluded for large datasets
        assert "SVM" not in model_names
        assert "Gradient Boosting" not in model_names
        
        # Fast models should still be included
        assert "XGBoost" in model_names
        assert "LightGBM" in model_names
    
    def test_get_scoring_metric(self, engine):
        """Test scoring metric selection"""
        assert engine._get_scoring_metric(ProblemType.BINARY_CLASSIFICATION) == "roc_auc"
        assert engine._get_scoring_metric(ProblemType.MULTICLASS_CLASSIFICATION) == "f1_weighted"
        assert engine._get_scoring_metric(ProblemType.REGRESSION) == "neg_mean_squared_error"
        assert engine._get_scoring_metric(ProblemType.CLUSTERING) == "accuracy"
    
    def test_calculate_test_score(self, engine):
        """Test test score calculation"""
        y_true = pd.Series([0, 1, 0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 1, 1, 1])
        
        # Classification score (accuracy)
        score = engine._calculate_test_score(
            y_true, y_pred, ProblemType.BINARY_CLASSIFICATION
        )
        assert score == 5/6  # 5 correct out of 6
        
        # Regression score (R²)
        y_true_reg = pd.Series([1.0, 2.0, 3.0, 4.0])
        y_pred_reg = np.array([1.1, 1.9, 3.2, 3.8])
        score_reg = engine._calculate_test_score(
            y_true_reg, y_pred_reg, ProblemType.REGRESSION
        )
        assert 0.9 < score_reg < 1.0  # Should be close to 1
    
    def test_get_feature_importance_tree_model(self, engine):
        """Test feature importance extraction from tree-based models"""
        from sklearn.ensemble import RandomForestClassifier
        
        # Create and fit a simple model
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        X = np.random.randn(100, 3)
        y = np.random.choice([0, 1], 100)
        model.fit(X, y)
        
        feature_names = ['feat1', 'feat2', 'feat3']
        importance = engine._get_feature_importance(model, feature_names)
        
        assert importance is not None
        assert len(importance) == 3
        assert all(0 <= v <= 1 for v in importance.values())
        assert sum(importance.values()) > 0
    
    def test_get_feature_importance_linear_model(self, engine):
        """Test feature importance extraction from linear models"""
        from sklearn.linear_model import LogisticRegression
        
        # Create and fit a simple model
        model = LogisticRegression(random_state=42)
        X = np.random.randn(100, 3)
        y = np.random.choice([0, 1], 100)
        model.fit(X, y)
        
        feature_names = ['feat1', 'feat2', 'feat3']
        importance = engine._get_feature_importance(model, feature_names)
        
        assert importance is not None
        assert len(importance) == 3
        assert all(v >= 0 for v in importance.values())
    
    @pytest.mark.asyncio
    async def test_model_training_error_handling(self, engine, classification_data):
        """Test error handling during model training"""
        X, y = classification_data
        df = pd.concat([X, pd.DataFrame({'target': y})], axis=1)
        
        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column='target',
            confidence=0.95,
            reasoning="Binary classification",
            metadata={}
        )
        
        # Create a faulty model candidate
        faulty_model = MagicMock()
        faulty_model.fit.side_effect = Exception("Training failed")
        
        # Create a working model
        working_model = MagicMock()
        working_model.fit.return_value = None
        working_model.predict.return_value = np.array([0] * 40)  # For test set
        working_model.feature_importances_ = np.array([0.5, 0.3, 0.2, 0.1])
        
        async def mock_detect(df, target):
            return mock_detection
        
        with patch.object(engine.problem_detector, 'detect_problem_type',
                         side_effect=mock_detect):
            with patch.object(engine, '_get_candidate_models') as mock_candidates:
                mock_candidates.return_value = [
                    ModelCandidate(
                        name="Faulty Model",
                        estimator=faulty_model,
                        hyperparameters={}
                    ),
                    ModelCandidate(
                        name="Working Model",
                        estimator=working_model,
                        hyperparameters={}
                    )
                ]
                
                # Mock cross_val_score to return good scores for working model
                with patch('app.services.model_training.automl_engine.cross_val_score') as mock_cv:
                    mock_cv.return_value = np.array([0.85, 0.87, 0.86])
                    
                    # Should still complete even with one failing model
                    result = await engine.run(df, 'target')
                    
                    # Only successful models should be in results
                    assert len(result.all_models) == 1
                    assert result.all_models[0].name == "Working Model"
                    assert result.all_models[0].cv_score > 0.8
    
    @pytest.mark.asyncio
    async def test_max_models_limit(self, engine, classification_data):
        """Test that max_models limit is respected"""
        engine.max_models = 2
        X, y = classification_data
        df = pd.concat([X, pd.DataFrame({'target': y})], axis=1)
        
        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column='target',
            confidence=0.95,
            reasoning="Binary classification",
            metadata={}
        )
        
        async def mock_detect(df, target):
            return mock_detection
        
        with patch.object(engine.problem_detector, 'detect_problem_type',
                         side_effect=mock_detect):
            result = await engine.run(df, 'target')
            
            # Should train at most max_models
            assert len(result.all_models) <= engine.max_models
    
    @pytest.mark.asyncio
    async def test_feature_engineering_integration(self, engine):
        """Test integration with feature engineering"""
        # Use simpler test without actual model training
        n_samples = 100
        X = pd.DataFrame({
            'num1': np.random.randn(n_samples),
            'num2': np.random.randn(n_samples),
        })
        y = pd.Series(np.random.choice([0, 1], n_samples))
        df = pd.concat([X, pd.DataFrame({'target': y})], axis=1)
        
        # Mock feature engineering result
        mock_feature_result = FeatureEngineeringResult(
            X_transformed=X,
            feature_names=list(X.columns),
            transformers={},
            feature_importance=None,
            metadata={'original_features': list(X.columns)}
        )
        
        # Mock problem detection
        mock_detection = ProblemDetectionResult(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            target_column='target',
            confidence=0.95,
            reasoning="Binary classification",
            metadata={}
        )
        
        async def mock_detect(df, target):
            return mock_detection
        
        with patch.object(engine.problem_detector, 'detect_problem_type',
                         side_effect=mock_detect):
            async def mock_fit_transform(X, y, problem_type):
                return mock_feature_result
            
            async def mock_transform(X):
                # Return data as-is since no categorical columns
                return X
                
            with patch.object(engine.feature_engineer, 'fit_transform',
                            side_effect=mock_fit_transform):
                with patch.object(engine.feature_engineer, 'transform',
                                side_effect=mock_transform):
                    # Mock model candidates
                    mock_model = MagicMock()
                    mock_model.fit.return_value = None
                    mock_model.predict.return_value = np.array([0] * 20)
                    mock_model.feature_importances_ = np.array([0.6, 0.4])
                    
                    with patch.object(engine, '_get_candidate_models') as mock_candidates:
                        mock_candidates.return_value = [
                            ModelCandidate(
                                name="Mock Model",
                                estimator=mock_model,
                                hyperparameters={}
                            )
                        ]
                        
                        with patch('app.services.model_training.automl_engine.cross_val_score') as mock_cv:
                            mock_cv.return_value = np.array([0.9, 0.91, 0.89])
                            
                            result = await engine.run(df, 'target')
                            
                            # Check feature engineering metadata is included
                            assert 'feature_engineering' in result.metadata
                            assert result.metadata['feature_engineering']['original_features'] == ['num1', 'num2']