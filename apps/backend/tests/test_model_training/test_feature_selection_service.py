"""
Tests for Feature Selection Service
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.model_training.feature_selection_service import (
    FeatureSelectionService,
    FeatureSelectionConfig
)
from app.schemas.feature_selection import (
    FeatureScore,
    RedundantPair,
    SelectionMethod
)


class TestFeatureSelectionService:
    """Test suite for feature selection service"""

    @pytest.fixture
    def service(self):
        """Create feature selection service instance"""
        return FeatureSelectionService()

    @pytest.fixture
    def config(self):
        """Create default configuration"""
        return FeatureSelectionConfig(
            top_k=5,
            threshold=None,
            correlation_threshold=0.7,
            problem_type="classification",
            sample_size=None,
            algorithm_params={}
        )

    @pytest.fixture
    def classification_data(self):
        """Create classification dataset"""
        np.random.seed(42)
        n_samples = 200

        # Create features with varying importance
        feature1 = np.random.randn(n_samples) * 2 + 5  # High variance
        feature2 = np.random.randn(n_samples) * 0.5 + 3  # Low variance
        feature3 = feature1 + np.random.randn(n_samples) * 0.1  # Highly correlated with feature1
        feature4 = np.random.choice([0, 1, 2], n_samples)  # Categorical
        feature5 = np.random.randn(n_samples)  # Independent

        # Create target that depends on feature1 and feature4
        target = (feature1 > 5).astype(int)
        target = (target + feature4 > 1).astype(int)

        df = pd.DataFrame({
            'feature1': feature1,
            'feature2': feature2,
            'feature3': feature3,
            'feature4': feature4,
            'feature5': feature5,
            'target': target
        })

        return df

    @pytest.fixture
    def regression_data(self):
        """Create regression dataset"""
        np.random.seed(42)
        n_samples = 200

        feature1 = np.random.randn(n_samples) * 2
        feature2 = np.random.randn(n_samples) * 3
        feature3 = feature1 + feature2 + np.random.randn(n_samples) * 0.5
        noise = np.random.randn(n_samples)

        # Target depends on feature1, feature2, and feature3
        target = 2 * feature1 + 3 * feature2 + 1.5 * feature3 + noise

        df = pd.DataFrame({
            'feature1': feature1,
            'feature2': feature2,
            'feature3': feature3,
            'noise': noise,
            'target': target
        })

        return df

    @pytest.fixture
    def mock_dataset(self):
        """Create mock dataset metadata"""
        dataset = MagicMock()
        dataset.dataset_id = "test_dataset_123"
        dataset.s3_url = "https://bucket.s3.amazonaws.com/datasets/user123/test.csv"
        dataset.file_type = "csv"
        return dataset

    # ========== Test Data Preparation ==========

    @pytest.mark.asyncio
    async def test_prepare_data_classification(self, service, classification_data):
        """Test data preparation for classification"""
        X, y, problem_type = await service._prepare_data(
            classification_data,
            target_column="target",
            problem_type="classification"
        )

        assert isinstance(X, pd.DataFrame)
        assert isinstance(y, pd.Series)
        assert problem_type == "classification"
        # After one-hot encoding, feature4 becomes feature4_0, feature4_1, feature4_2
        # So we have: feature1, feature2, feature3, feature5, feature4_0, feature4_1, feature4_2 = 7 columns
        assert len(X.columns) == 7  # Excludes target, includes one-hot encoded features
        assert len(X) == len(y)
        assert "target" not in X.columns

    @pytest.mark.asyncio
    async def test_prepare_data_auto_detect_classification(self, service, classification_data):
        """Test automatic problem type detection for classification"""
        X, y, problem_type = await service._prepare_data(
            classification_data,
            target_column="target",
            problem_type=None
        )

        assert problem_type == "classification"

    @pytest.mark.asyncio
    async def test_prepare_data_regression(self, service, regression_data):
        """Test data preparation for regression"""
        X, y, problem_type = await service._prepare_data(
            regression_data,
            target_column="target",
            problem_type="regression"
        )

        assert isinstance(X, pd.DataFrame)
        assert isinstance(y, pd.Series)
        assert problem_type == "regression"

    @pytest.mark.asyncio
    async def test_prepare_data_sampling(self, service, classification_data):
        """Test data sampling for large datasets"""
        X, y, problem_type = await service._prepare_data(
            classification_data,
            target_column="target",
            problem_type="classification",
            sample_size=50
        )

        assert len(X) == 50
        assert len(y) == 50

    # ========== Test Selection Algorithms ==========

    @pytest.mark.asyncio
    async def test_correlation_selection(self, service, classification_data):
        """Test correlation-based feature selection"""
        X, y, _ = await service._prepare_data(
            classification_data, "target", "classification"
        )

        scores = await service._select_correlation(X, y)

        assert isinstance(scores, dict)
        assert len(scores) > 0
        assert all(0 <= v <= 1 for v in scores.values())

    @pytest.mark.asyncio
    async def test_mutual_info_selection_classification(self, service, classification_data):
        """Test mutual information for classification"""
        X, y, _ = await service._prepare_data(
            classification_data, "target", "classification"
        )

        scores = await service._select_mutual_info(X, y, "classification")

        assert isinstance(scores, dict)
        assert len(scores) == len(X.columns)
        assert all(v >= 0 for v in scores.values())

    @pytest.mark.asyncio
    async def test_mutual_info_selection_regression(self, service, regression_data):
        """Test mutual information for regression"""
        X, y, _ = await service._prepare_data(
            regression_data, "target", "regression"
        )

        scores = await service._select_mutual_info(X, y, "regression")

        assert isinstance(scores, dict)
        assert len(scores) == len(X.columns)
        assert all(v >= 0 for v in scores.values())

    @pytest.mark.asyncio
    async def test_random_forest_selection(self, service, classification_data, config):
        """Test Random Forest feature selection"""
        X, y, _ = await service._prepare_data(
            classification_data, "target", "classification"
        )

        scores = await service._select_random_forest(X, y, "classification", config)

        assert isinstance(scores, dict)
        assert len(scores) == len(X.columns)
        assert all(v >= 0 for v in scores.values())
        # Importances should sum to approximately 1.0
        assert 0.9 < sum(scores.values()) < 1.1

    @pytest.mark.asyncio
    async def test_rfe_selection(self, service, classification_data, config):
        """Test Recursive Feature Elimination"""
        X, y, _ = await service._prepare_data(
            classification_data, "target", "classification"
        )

        scores = await service._select_rfe(X, y, "classification", config)

        assert isinstance(scores, dict)
        assert len(scores) == len(X.columns)
        assert all(v >= 0 for v in scores.values())

    @pytest.mark.asyncio
    async def test_lasso_selection(self, service, regression_data, config):
        """Test LASSO selection"""
        X, y, _ = await service._prepare_data(
            regression_data, "target", "regression"
        )

        scores = await service._select_lasso(X, y, "regression", config)

        assert isinstance(scores, dict)
        assert len(scores) == len(X.columns)
        assert all(v >= 0 for v in scores.values())

    @pytest.mark.asyncio
    async def test_statistical_selection_classification(self, service, classification_data):
        """Test statistical selection for classification"""
        X, y, _ = await service._prepare_data(
            classification_data, "target", "classification"
        )

        scores = await service._select_statistical(X, y, "classification")

        assert isinstance(scores, dict)
        assert len(scores) == len(X.columns)
        assert all(v >= 0 for v in scores.values())

    @pytest.mark.asyncio
    async def test_statistical_selection_regression(self, service, regression_data):
        """Test statistical selection for regression"""
        X, y, _ = await service._prepare_data(
            regression_data, "target", "regression"
        )

        scores = await service._select_statistical(X, y, "regression")

        assert isinstance(scores, dict)
        assert len(scores) == len(X.columns)
        assert all(v >= 0 for v in scores.values())

    # ========== Test Score Normalization ==========

    def test_normalize_scores(self, service):
        """Test score normalization"""
        scores = {
            'feature1': 10.0,
            'feature2': 5.0,
            'feature3': 0.0
        }

        normalized = service._normalize_scores(scores)

        assert normalized['feature1'] == 1.0  # Maximum
        assert normalized['feature3'] == 0.0  # Minimum
        assert 0 <= normalized['feature2'] <= 1

    def test_normalize_scores_all_equal(self, service):
        """Test normalization when all scores are equal"""
        scores = {
            'feature1': 5.0,
            'feature2': 5.0,
            'feature3': 5.0
        }

        normalized = service._normalize_scores(scores)

        assert all(v == 1.0 for v in normalized.values())

    # ========== Test Selection Criteria ==========

    def test_apply_selection_top_k(self, service):
        """Test top-k selection"""
        scores = {
            'feature1': 0.9,
            'feature2': 0.7,
            'feature3': 0.5,
            'feature4': 0.3,
            'feature5': 0.1
        }

        selected = service._apply_selection_criteria(scores, top_k=3, threshold=None)

        assert len(selected) == 3
        assert set(selected) == {'feature1', 'feature2', 'feature3'}

    def test_apply_selection_threshold(self, service):
        """Test threshold-based selection"""
        scores = {
            'feature1': 0.9,
            'feature2': 0.7,
            'feature3': 0.5,
            'feature4': 0.3,
            'feature5': 0.1
        }

        selected = service._apply_selection_criteria(scores, top_k=None, threshold=0.6)

        assert len(selected) == 2
        assert set(selected) == {'feature1', 'feature2'}

    def test_apply_selection_default(self, service):
        """Test default selection (top 50%)"""
        scores = {
            'feature1': 0.9,
            'feature2': 0.7,
            'feature3': 0.5,
            'feature4': 0.3
        }

        selected = service._apply_selection_criteria(scores, top_k=None, threshold=None)

        assert len(selected) == 2  # Top 50%

    # ========== Test Redundancy Detection ==========

    @pytest.mark.asyncio
    async def test_detect_redundancy(self, service):
        """Test redundancy detection"""
        # Create highly correlated features
        np.random.seed(42)
        n_samples = 100

        feature1 = np.random.randn(n_samples)
        feature2 = feature1 + np.random.randn(n_samples) * 0.1  # Highly correlated
        feature3 = np.random.randn(n_samples)  # Independent

        df = pd.DataFrame({
            'feature1': feature1,
            'feature2': feature2,
            'feature3': feature3
        })

        redundant_pairs = await service.detect_redundancy(df, threshold=0.7)

        assert len(redundant_pairs) >= 1
        # Should detect feature1 and feature2 as redundant
        pair = redundant_pairs[0]
        assert set([pair.feature1, pair.feature2]) == {'feature1', 'feature2'}
        assert pair.correlation > 0.7
        assert len(pair.recommendation) > 0

    @pytest.mark.asyncio
    async def test_detect_redundancy_none(self, service):
        """Test redundancy detection with independent features"""
        np.random.seed(42)
        n_samples = 100

        df = pd.DataFrame({
            'feature1': np.random.randn(n_samples),
            'feature2': np.random.randn(n_samples),
            'feature3': np.random.randn(n_samples)
        })

        redundant_pairs = await service.detect_redundancy(df, threshold=0.9)

        assert len(redundant_pairs) == 0

    # ========== Test Feature Score Creation ==========

    def test_create_feature_scores(self, service):
        """Test FeatureScore object creation"""
        scores = {
            'feature1': 0.9,
            'feature2': 0.7,
            'feature3': 0.5
        }

        selected_features = ['feature1', 'feature2']

        feature_scores = service._create_feature_scores(scores, selected_features)

        assert len(feature_scores) == 3
        assert all(isinstance(fs, FeatureScore) for fs in feature_scores)

        # Check ranking
        assert feature_scores[0].feature_name == 'feature1'
        assert feature_scores[0].rank == 1
        assert feature_scores[0].selected is True

        assert feature_scores[1].feature_name == 'feature2'
        assert feature_scores[1].rank == 2
        assert feature_scores[1].selected is True

        assert feature_scores[2].feature_name == 'feature3'
        assert feature_scores[2].rank == 3
        assert feature_scores[2].selected is False

    # ========== Test Explanation Generation ==========

    def test_explain_selection(self, service):
        """Test explanation generation"""
        selected_features = ['feature1', 'feature2']
        feature_scores = [
            FeatureScore(feature_name='feature1', score=0.9, rank=1, selected=True),
            FeatureScore(feature_name='feature2', score=0.7, rank=2, selected=True),
            FeatureScore(feature_name='feature3', score=0.5, rank=3, selected=False)
        ]
        redundant_pairs = []

        explanation = service._explain_selection(
            method="correlation",
            selected_features=selected_features,
            feature_scores=feature_scores,
            redundant_pairs=redundant_pairs,
            problem_type="classification"
        )

        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "correlation" in explanation.lower()
        assert "classification" in explanation.lower()

    # ========== Test Caching ==========

    def test_generate_cache_key(self, service, config):
        """Test cache key generation and security isolation"""
        cache_key1 = service._generate_cache_key(
            dataset_id="dataset123",
            user_id="user_A",
            method="correlation",
            target_column="target",
            config=config
        )

        # Same parameters should generate same key
        cache_key2 = service._generate_cache_key(
            dataset_id="dataset123",
            user_id="user_A",
            method="correlation",
            target_column="target",
            config=config
        )

        assert cache_key1 == cache_key2

        # Different parameters should generate different keys
        config2 = FeatureSelectionConfig(
            top_k=10,  # Different
            threshold=None,
            correlation_threshold=0.7,
            problem_type="classification"
        )

        cache_key3 = service._generate_cache_key(
            dataset_id="dataset123",
            user_id="user_A",
            method="correlation",
            target_column="target",
            config=config2
        )

        assert cache_key1 != cache_key3

        # SECURITY: Different user_ids must generate different keys
        # to prevent cache poisoning/authorization bypass
        cache_key4 = service._generate_cache_key(
            dataset_id="dataset123",
            user_id="user_B",  # Different user
            method="correlation",
            target_column="target",
            config=config
        )

        assert cache_key1 != cache_key4, "Cache keys must differ by user_id to prevent authorization bypass"

    # ========== Test End-to-End Selection ==========

    @pytest.mark.asyncio
    @patch('app.services.model_training.feature_selection_service.download_file_from_s3')
    @patch('app.services.model_training.feature_selection_service.cache_service')
    async def test_select_features_e2e(
        self,
        mock_cache,
        mock_download,
        service,
        classification_data,
        config,
        mock_dataset,
        tmp_path
    ):
        """Test end-to-end feature selection"""
        # Setup mocks
        mock_cache.get = AsyncMock(return_value=None)  # Cache miss
        mock_cache.set = AsyncMock(return_value=True)

        # Create temporary CSV file
        csv_file = tmp_path / "test_data.csv"
        classification_data.to_csv(csv_file, index=False)
        mock_download.return_value = str(csv_file)

        # Mock dataset service
        service.dataset_service.get_by_id = AsyncMock(return_value=mock_dataset)

        # Run feature selection
        result = await service.select_features(
            dataset_id="test_dataset_123",
            user_id="user_123",
            target_column="target",
            method="correlation",
            config=config
        )

        # Verify result structure
        assert result["dataset_id"] == "test_dataset_123"
        assert result["method"] == "correlation"
        assert isinstance(result["selected_features"], list)
        assert len(result["selected_features"]) <= config.top_k
        assert isinstance(result["feature_scores"], list)
        assert all(isinstance(fs, FeatureScore) for fs in result["feature_scores"])
        assert isinstance(result["redundant_pairs"], list)
        assert "explanation" in result
        assert "metadata" in result
        assert "execution_time_ms" in result

        # Verify cache was called
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.model_training.feature_selection_service.download_file_from_s3')
    @patch('app.services.model_training.feature_selection_service.cache_service')
    async def test_select_features_cache_hit(
        self,
        mock_cache,
        mock_download,
        service,
        config
    ):
        """Test feature selection with cache hit"""
        # Setup cache hit
        cached_result = {
            "dataset_id": "test_dataset_123",
            "method": "correlation",
            "selected_features": ["feature1", "feature2"],
            "feature_scores": [],
            "redundant_pairs": [],
            "correlation_matrix": {},
            "explanation": "Cached result",
            "metadata": {},
            "execution_time_ms": 100.0,
            "created_at": datetime.now(timezone.utc)
        }

        mock_cache.get = AsyncMock(return_value=cached_result)

        # Run feature selection
        result = await service.select_features(
            dataset_id="test_dataset_123",
            user_id="user_123",
            target_column="target",
            method="correlation",
            config=config
        )

        # Verify result is from cache
        assert result == cached_result

        # Verify download was not called (cache hit)
        mock_download.assert_not_called()
