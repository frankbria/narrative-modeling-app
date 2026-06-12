"""Tests for EvaluationExplanationService (issue #79).

The service follows the DatasetSummarizationService pattern: an OpenAI
JSON-mode call behind a circuit breaker, with a deterministic rule-based
fallback so the evaluation endpoint works fully without an API key.
"""

import json
from unittest.mock import MagicMock

import pytest
from openai import OpenAIError

from app.schemas.evaluation import (
    AIExplanation,
    ClassificationMetrics,
    ConfusionMatrixData,
    PerClassMetrics,
    RegressionMetrics,
)
from app.services.evaluation_explanation_service import EvaluationExplanationService
from app.utils.circuit_breaker import get_circuit_breaker

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_openai_breaker():
    """Isolate the shared 'openai' circuit breaker.

    Failure-path tests now genuinely record breaker failures (the service no
    longer swallows exceptions before the decorator can count them), so state
    must be reset around each test to avoid opening the circuit for other
    suites that share the 'openai' breaker.
    """
    breaker = get_circuit_breaker("openai")
    breaker.reset()
    yield breaker
    breaker.reset()


@pytest.fixture
def classification_metrics() -> ClassificationMetrics:
    return ClassificationMetrics(
        accuracy=0.91,
        precision_macro=0.90,
        precision_weighted=0.91,
        recall_macro=0.89,
        recall_weighted=0.91,
        f1_macro=0.895,
        f1_weighted=0.91,
        roc_auc=0.95,
        log_loss=0.25,
        per_class_metrics={
            "no": PerClassMetrics(precision=0.92, recall=0.94, f1=0.93, support=60),
            "yes": PerClassMetrics(precision=0.88, recall=0.84, f1=0.86, support=40),
        },
    )


@pytest.fixture
def confusion() -> ConfusionMatrixData:
    return ConfusionMatrixData(labels=["no", "yes"], matrix=[[56, 4], [6, 34]])


@pytest.fixture
def regression_metrics() -> RegressionMetrics:
    return RegressionMetrics(mae=2.1, mse=8.4, rmse=2.9, r2=0.87, mape=4.2)


def _report_card_kwargs(metrics, confusion_matrix=None):
    return dict(
        problem_type="binary_classification",
        metrics=metrics,
        confusion_matrix=confusion_matrix,
        feature_importance={"age": 0.4, "income": 0.35, "region": 0.25},
        n_test_samples=100,
        model_name="Churn Model",
        algorithm="Random Forest",
    )


class TestOpenAIPath:
    @pytest.mark.asyncio
    async def test_successful_openai_call(self, classification_metrics, confusion):
        service = EvaluationExplanationService()
        ai_payload = {
            "overall_assessment": "Strong model overall.",
            "metric_explanations": {"accuracy": "91 out of 100 correct."},
            "strengths": ["High accuracy"],
            "concerns": ["Slightly weaker on the 'yes' class"],
            "recommendations": ["Collect more 'yes' examples"],
        }
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps(ai_payload)))
        ]
        mock_client.chat.completions.create = MagicMock(return_value=mock_response)
        service.client = mock_client

        result = await service.generate_report_card(
            **_report_card_kwargs(classification_metrics, confusion)
        )

        assert isinstance(result, AIExplanation)
        assert result.generated_by == "openai"
        assert result.overall_assessment == "Strong model overall."
        assert result.metric_explanations["accuracy"] == "91 out of 100 correct."
        assert result.strengths == ["High accuracy"]
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}


class TestFallbackPath:
    @pytest.mark.asyncio
    async def test_fallback_when_client_none(self, classification_metrics, confusion):
        service = EvaluationExplanationService()
        service.client = None

        result = await service.generate_report_card(
            **_report_card_kwargs(classification_metrics, confusion)
        )

        assert isinstance(result, AIExplanation)
        assert result.generated_by == "fallback"
        assert result.overall_assessment
        assert result.metric_explanations
        assert result.recommendations

    @pytest.mark.asyncio
    async def test_fallback_when_call_raises(self, classification_metrics, confusion):
        service = EvaluationExplanationService()
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(
            side_effect=RuntimeError("OpenAI unavailable")
        )
        service.client = mock_client

        result = await service.generate_report_card(
            **_report_card_kwargs(classification_metrics, confusion)
        )

        assert result.generated_by == "fallback"
        assert result.overall_assessment

    @pytest.mark.asyncio
    async def test_failures_are_recorded_by_circuit_breaker(
        self, reset_openai_breaker, classification_metrics, confusion
    ):
        """A failing OpenAI call must count toward opening the circuit.

        Guards against the swallowed-exception bug where the method's own
        try/except returned None, the decorator recorded a success, and the
        breaker could never open.
        """
        breaker = reset_openai_breaker
        assert breaker.metrics.consecutive_failures == 0

        service = EvaluationExplanationService()
        mock_client = MagicMock()
        # Must be an OpenAIError: the breaker deliberately counts only API
        # failures, not parse/programming errors (which still fall back via
        # the caller's catch without opening the circuit)
        mock_client.chat.completions.create = MagicMock(
            side_effect=OpenAIError("OpenAI unavailable")
        )
        service.client = mock_client

        result = await service.generate_report_card(
            **_report_card_kwargs(classification_metrics, confusion)
        )

        assert result.generated_by == "fallback"
        assert breaker.metrics.consecutive_failures >= 1

    @pytest.mark.asyncio
    async def test_fallback_when_response_not_json(self, classification_metrics):
        service = EvaluationExplanationService()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="not json"))]
        mock_client.chat.completions.create = MagicMock(return_value=mock_response)
        service.client = mock_client

        result = await service.generate_report_card(
            **_report_card_kwargs(classification_metrics)
        )
        assert result.generated_by == "fallback"

    @pytest.mark.asyncio
    async def test_fallback_regression(self, regression_metrics):
        service = EvaluationExplanationService()
        service.client = None

        result = await service.generate_report_card(
            problem_type="regression",
            metrics=regression_metrics,
            confusion_matrix=None,
            feature_importance={"sqft": 0.6, "rooms": 0.4},
            n_test_samples=40,
            model_name="Price Model",
            algorithm="Ridge Regression",
        )

        assert result.generated_by == "fallback"
        assert result.overall_assessment
        # Regression explanations talk about regression metrics
        assert any(key in result.metric_explanations for key in ("r2", "mae", "rmse"))

    @pytest.mark.asyncio
    async def test_fallback_flags_class_imbalance(self):
        """Heavily imbalanced confusion matrix surfaces an imbalance concern."""
        service = EvaluationExplanationService()
        service.client = None

        metrics = ClassificationMetrics(
            accuracy=0.9,
            precision_macro=0.5,
            precision_weighted=0.85,
            recall_macro=0.5,
            recall_weighted=0.9,
            f1_macro=0.48,
            f1_weighted=0.87,
            roc_auc=None,
            log_loss=None,
            per_class_metrics={
                "no": PerClassMetrics(precision=0.9, recall=1.0, f1=0.95, support=90),
                "yes": PerClassMetrics(precision=0.0, recall=0.0, f1=0.0, support=10),
            },
        )
        confusion_matrix = ConfusionMatrixData(
            labels=["no", "yes"], matrix=[[90, 0], [10, 0]]
        )

        result = await service.generate_report_card(
            problem_type="binary_classification",
            metrics=metrics,
            confusion_matrix=confusion_matrix,
            feature_importance=None,
            n_test_samples=100,
            model_name="Imbalanced Model",
            algorithm="Logistic Regression",
        )

        assert result.generated_by == "fallback"
        combined = " ".join(result.concerns + result.recommendations).lower()
        assert "imbalanc" in combined or "class" in combined
