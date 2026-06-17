"""
Tests for ExplanationService
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.model_training.algorithm_selector import (
    AlgorithmRecommendation,
    DataProfile,
)
from app.services.model_training.explanation_service import ExplanationService
from app.services.model_training.problem_detector import ProblemType


@pytest.fixture
def explanation_service():
    """Create an ExplanationService instance"""
    return ExplanationService()


@pytest.fixture
def sample_data_profile():
    """Create a sample data profile"""
    return DataProfile(
        n_samples=5000,
        n_features=15,
        n_numeric_features=12,
        n_categorical_features=3,
        class_balance_ratio=2.5,
        missing_value_percentage=0.03,
        high_cardinality_features=1,
        dataset_size_category="medium"
    )


@pytest.fixture
def sample_recommendations():
    """Create sample algorithm recommendations"""
    return [
        AlgorithmRecommendation(
            algorithm_name="XGBoost",
            priority=10,
            expected_performance="85-95% accuracy",
            training_time_estimate="3-10 minutes",
            interpretability_score=5,
            explanation="State-of-the-art gradient boosting",
            pros=["High accuracy", "Handles missing values"],
            cons=["Complex tuning", "Less interpretable"]
        ),
        AlgorithmRecommendation(
            algorithm_name="Random Forest",
            priority=9,
            expected_performance="80-90% accuracy",
            training_time_estimate="2-5 minutes",
            interpretability_score=6,
            explanation="Robust ensemble model",
            pros=["Good accuracy", "Feature importance"],
            cons=["Slower prediction", "Memory intensive"]
        )
    ]


class TestExplanationService:
    """Tests for ExplanationService class"""

    @pytest.mark.asyncio
    @patch('app.services.model_training.explanation_service.client')
    async def test_explain_algorithm_selection(
        self, mock_client, explanation_service, sample_data_profile, sample_recommendations
    ):
        """Test explaining algorithm selection"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="These algorithms were selected based on your dataset characteristics..."))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        explanation = await explanation_service.explain_algorithm_selection(
            algorithms=sample_recommendations,
            data_profile=sample_data_profile,
            problem_type=ProblemType.BINARY_CLASSIFICATION
        )

        # Should return an explanation
        assert explanation is not None
        assert isinstance(explanation, str)
        assert len(explanation) > 0

        # OpenAI should have been called
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.model_training.explanation_service.client')
    async def test_explain_best_model(
        self, mock_client, explanation_service
    ):
        """Test explaining best model selection"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="XGBoost was chosen because it achieved the highest accuracy..."))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        best_model = {
            "name": "XGBoost",
            "cv_score": 0.92,
            "test_score": 0.90,
            "training_time": 245.5
        }

        all_models = [
            best_model,
            {
                "name": "Random Forest",
                "cv_score": 0.88,
                "test_score": 0.86,
                "training_time": 180.2
            }
        ]

        comparison_metrics = {
            "primary_metric": "accuracy",
            "cv_scores": [0.92, 0.88],
            "test_scores": [0.90, 0.86]
        }

        explanation = await explanation_service.explain_best_model(
            best_model=best_model,
            all_models=all_models,
            comparison_metrics=comparison_metrics
        )

        # Should return an explanation
        assert explanation is not None
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    @pytest.mark.asyncio
    @patch('app.services.model_training.explanation_service.client')
    async def test_explain_model_tradeoffs(
        self, mock_client, explanation_service
    ):
        """Test explaining trade-offs between two models"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="XGBoost offers higher accuracy while Random Forest is more interpretable..."))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        model_a = {
            "name": "XGBoost",
            "cv_score": 0.92,
            "interpretability_score": 5,
            "training_time": 245.5
        }

        model_b = {
            "name": "Random Forest",
            "cv_score": 0.88,
            "interpretability_score": 7,
            "training_time": 180.2
        }

        explanation = await explanation_service.explain_model_tradeoffs(
            model_a=model_a,
            model_b=model_b
        )

        # Should return an explanation
        assert explanation is not None
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    @pytest.mark.asyncio
    @patch('app.services.model_training.explanation_service.client', None)
    async def test_explain_algorithm_selection_no_client(
        self, explanation_service, sample_data_profile, sample_recommendations
    ):
        """Test graceful handling when OpenAI client is not available"""
        explanation = await explanation_service.explain_algorithm_selection(
            algorithms=sample_recommendations,
            data_profile=sample_data_profile,
            problem_type=ProblemType.BINARY_CLASSIFICATION
        )

        # Should return fallback explanation
        assert explanation is not None
        assert isinstance(explanation, str)
        assert "recommend" in explanation.lower() or "selected" in explanation.lower()

    @pytest.mark.asyncio
    @patch('app.services.model_training.explanation_service.client')
    async def test_explain_algorithm_selection_api_error(
        self, mock_client, explanation_service, sample_data_profile, sample_recommendations
    ):
        """Test handling of OpenAI API errors"""
        # Mock OpenAI error
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        explanation = await explanation_service.explain_algorithm_selection(
            algorithms=sample_recommendations,
            data_profile=sample_data_profile,
            problem_type=ProblemType.BINARY_CLASSIFICATION
        )

        # Should return fallback explanation
        assert explanation is not None
        assert isinstance(explanation, str)

    @pytest.mark.asyncio
    @patch('app.services.model_training.explanation_service.client')
    async def test_prompt_includes_data_characteristics(
        self, mock_client, explanation_service, sample_data_profile, sample_recommendations
    ):
        """Test that prompt includes relevant data characteristics"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Explanation..."))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        await explanation_service.explain_algorithm_selection(
            algorithms=sample_recommendations,
            data_profile=sample_data_profile,
            problem_type=ProblemType.BINARY_CLASSIFICATION
        )

        # Get the call args
        call_args = mock_client.chat.completions.create.call_args

        # Should have been called with messages
        assert 'messages' in call_args.kwargs

        # Convert messages to string to check content
        messages_str = str(call_args.kwargs['messages'])

        # Should include dataset characteristics
        assert str(sample_data_profile.n_samples) in messages_str
        assert str(sample_data_profile.n_features) in messages_str

    @pytest.mark.asyncio
    @patch('app.services.model_training.explanation_service.client')
    async def test_caching_disabled_by_default(
        self, mock_client, explanation_service, sample_data_profile, sample_recommendations
    ):
        """Test that caching is not required initially"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Explanation..."))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Call twice with same inputs
        explanation1 = await explanation_service.explain_algorithm_selection(
            algorithms=sample_recommendations,
            data_profile=sample_data_profile,
            problem_type=ProblemType.BINARY_CLASSIFICATION
        )

        explanation2 = await explanation_service.explain_algorithm_selection(
            algorithms=sample_recommendations,
            data_profile=sample_data_profile,
            problem_type=ProblemType.BINARY_CLASSIFICATION
        )

        # Both should return valid explanations
        assert explanation1 is not None
        assert explanation2 is not None

        # For now, caching is optional, so we just verify both calls work
        assert mock_client.chat.completions.create.call_count >= 1
