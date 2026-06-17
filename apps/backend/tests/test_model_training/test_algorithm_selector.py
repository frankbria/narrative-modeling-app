"""
Tests for AlgorithmSelector
"""

import pytest

from app.services.model_training.algorithm_selector import (
    AlgorithmRecommendation,
    AlgorithmSelector,
    DataProfile,
)
from app.services.model_training.problem_detector import ProblemType


@pytest.fixture
def algorithm_selector():
    """Create an AlgorithmSelector instance"""
    return AlgorithmSelector()


class TestDataProfile:
    """Tests for DataProfile dataclass"""

    def test_data_profile_creation(self):
        """Test creating a DataProfile"""
        profile = DataProfile(
            n_samples=1000,
            n_features=10,
            n_numeric_features=8,
            n_categorical_features=2,
            class_balance_ratio=2.5,
            missing_value_percentage=0.05,
            high_cardinality_features=1,
            dataset_size_category="medium"
        )

        assert profile.n_samples == 1000
        assert profile.n_features == 10
        assert profile.dataset_size_category == "medium"


class TestAlgorithmRecommendation:
    """Tests for AlgorithmRecommendation dataclass"""

    def test_algorithm_recommendation_creation(self):
        """Test creating an AlgorithmRecommendation"""
        rec = AlgorithmRecommendation(
            algorithm_name="Random Forest",
            priority=9,
            expected_performance="85-90%",
            training_time_estimate="2-5 minutes",
            interpretability_score=6,
            explanation="Good for most datasets",
            pros=["Handles non-linearity", "Feature importance"],
            cons=["Can overfit", "Memory intensive"]
        )

        assert rec.algorithm_name == "Random Forest"
        assert rec.priority == 9
        assert len(rec.pros) == 2
        assert len(rec.cons) == 2


class TestAlgorithmSelector:
    """Tests for AlgorithmSelector class"""

    @pytest.mark.asyncio
    async def test_select_algorithms_binary_classification_small_dataset(
        self, algorithm_selector
    ):
        """Test algorithm selection for small binary classification dataset"""
        profile = DataProfile(
            n_samples=1000,
            n_features=10,
            n_numeric_features=8,
            n_categorical_features=2,
            class_balance_ratio=1.2,
            missing_value_percentage=0.01,
            high_cardinality_features=0,
            dataset_size_category="small"
        )

        recommendations = await algorithm_selector.select_algorithms(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            data_profile=profile,
            config={}
        )

        # Should return recommendations
        assert len(recommendations) > 0

        # Should include appropriate algorithms
        algo_names = [r.algorithm_name for r in recommendations]
        assert "Logistic Regression" in algo_names
        assert "Random Forest" in algo_names

        # For small datasets, should include SVM
        assert "SVM" in algo_names

        # Should be sorted by priority (descending)
        priorities = [r.priority for r in recommendations]
        assert priorities == sorted(priorities, reverse=True)

    @pytest.mark.asyncio
    async def test_select_algorithms_large_dataset(self, algorithm_selector):
        """Test algorithm selection for large dataset"""
        profile = DataProfile(
            n_samples=50000,
            n_features=20,
            n_numeric_features=15,
            n_categorical_features=5,
            class_balance_ratio=1.5,
            missing_value_percentage=0.02,
            high_cardinality_features=2,
            dataset_size_category="large"
        )

        recommendations = await algorithm_selector.select_algorithms(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            data_profile=profile,
            config={}
        )

        algo_names = [r.algorithm_name for r in recommendations]

        # Should prioritize LightGBM/XGBoost for large datasets
        assert "LightGBM" in algo_names
        assert "XGBoost" in algo_names

        # Should NOT include SVM for large datasets (too slow)
        assert "SVM" not in algo_names

    @pytest.mark.asyncio
    async def test_select_algorithms_imbalanced_dataset(self, algorithm_selector):
        """Test algorithm selection for imbalanced dataset"""
        profile = DataProfile(
            n_samples=5000,
            n_features=15,
            n_numeric_features=12,
            n_categorical_features=3,
            class_balance_ratio=5.0,  # Highly imbalanced
            missing_value_percentage=0.03,
            high_cardinality_features=1,
            dataset_size_category="medium"
        )

        recommendations = await algorithm_selector.select_algorithms(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            data_profile=profile,
            config={}
        )

        # Tree-based models should be prioritized for imbalanced data
        algo_names = [r.algorithm_name for r in recommendations]
        assert "Random Forest" in algo_names or "XGBoost" in algo_names

        # Check that at least one recommendation mentions class imbalance
        explanations = [r.explanation for r in recommendations]
        assert any("imbalanc" in exp.lower() for exp in explanations if exp)

    @pytest.mark.asyncio
    async def test_select_algorithms_regression(self, algorithm_selector):
        """Test algorithm selection for regression problems"""
        profile = DataProfile(
            n_samples=3000,
            n_features=12,
            n_numeric_features=10,
            n_categorical_features=2,
            class_balance_ratio=None,  # Not applicable for regression
            missing_value_percentage=0.05,
            high_cardinality_features=1,
            dataset_size_category="medium"
        )

        recommendations = await algorithm_selector.select_algorithms(
            problem_type=ProblemType.REGRESSION,
            data_profile=profile,
            config={}
        )

        algo_names = [r.algorithm_name for r in recommendations]

        # Should include regression algorithms
        assert "Linear Regression" in algo_names or "Ridge Regression" in algo_names
        assert "Random Forest Regressor" in algo_names or "XGBoost Regressor" in algo_names

    @pytest.mark.asyncio
    async def test_select_algorithms_with_interpretability_preference(
        self, algorithm_selector
    ):
        """Test algorithm selection when interpretability is prioritized"""
        profile = DataProfile(
            n_samples=2000,
            n_features=8,
            n_numeric_features=6,
            n_categorical_features=2,
            class_balance_ratio=1.3,
            missing_value_percentage=0.01,
            high_cardinality_features=0,
            dataset_size_category="small"
        )

        recommendations = await algorithm_selector.select_algorithms(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            data_profile=profile,
            config={"optimize_for": "interpretability"}
        )

        # Logistic Regression should be highly prioritized
        top_algos = [r.algorithm_name for r in recommendations[:3]]
        assert "Logistic Regression" in top_algos

    @pytest.mark.asyncio
    async def test_select_algorithms_with_speed_preference(
        self, algorithm_selector
    ):
        """Test algorithm selection when speed is prioritized"""
        profile = DataProfile(
            n_samples=10000,
            n_features=15,
            n_numeric_features=12,
            n_categorical_features=3,
            class_balance_ratio=1.5,
            missing_value_percentage=0.02,
            high_cardinality_features=1,
            dataset_size_category="medium"
        )

        recommendations = await algorithm_selector.select_algorithms(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            data_profile=profile,
            config={"optimize_for": "speed"}
        )

        # LightGBM should be prioritized for speed
        top_algos = [r.algorithm_name for r in recommendations[:3]]
        assert "LightGBM" in top_algos or "Logistic Regression" in top_algos

    @pytest.mark.asyncio
    async def test_recommendation_fields_complete(self, algorithm_selector):
        """Test that all recommendation fields are populated"""
        profile = DataProfile(
            n_samples=1000,
            n_features=10,
            n_numeric_features=8,
            n_categorical_features=2,
            class_balance_ratio=1.2,
            missing_value_percentage=0.01,
            high_cardinality_features=0,
            dataset_size_category="small"
        )

        recommendations = await algorithm_selector.select_algorithms(
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            data_profile=profile,
            config={}
        )

        # Check that all fields are populated for each recommendation
        for rec in recommendations:
            assert rec.algorithm_name is not None
            assert isinstance(rec.priority, int)
            assert 1 <= rec.priority <= 10
            assert rec.expected_performance is not None
            assert rec.training_time_estimate is not None
            assert isinstance(rec.interpretability_score, int)
            assert 1 <= rec.interpretability_score <= 10
            assert rec.explanation is not None
            assert isinstance(rec.pros, list)
            assert isinstance(rec.cons, list)
            assert len(rec.pros) > 0
            assert len(rec.cons) > 0

    @pytest.mark.asyncio
    async def test_high_cardinality_features(self, algorithm_selector):
        """Test algorithm selection with high cardinality features"""
        profile = DataProfile(
            n_samples=5000,
            n_features=20,
            n_numeric_features=10,
            n_categorical_features=10,
            class_balance_ratio=1.5,
            missing_value_percentage=0.02,
            high_cardinality_features=8,  # Many high cardinality features
            dataset_size_category="medium"
        )

        recommendations = await algorithm_selector.select_algorithms(
            problem_type=ProblemType.MULTICLASS_CLASSIFICATION,
            data_profile=profile,
            config={}
        )

        algo_names = [r.algorithm_name for r in recommendations]

        # Tree-based models should be prioritized over linear models
        # for high cardinality
        assert "Random Forest" in algo_names or "XGBoost" in algo_names
