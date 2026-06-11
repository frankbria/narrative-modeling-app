"""AI 'Model Report Card' explanations for the evaluation dashboard (issue #79).

Follows the DatasetSummarizationService pattern: an instance OpenAI client
(None-safe when OPENAI_API_KEY is unset), JSON-mode responses behind the
shared OpenAI circuit breaker, and a deterministic rule-based fallback so
GET /api/v1/ml/{model_id}/evaluation works fully without an API key.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI, OpenAIError

from app.schemas.evaluation import (
    AIExplanation,
    ClassificationMetrics,
    ConfusionMatrixData,
    RegressionMetrics,
)
from app.utils.circuit_breaker import with_circuit_breaker

logger = logging.getLogger(__name__)


class EvaluationExplanationService:
    """Generate plain-language model report cards (OpenAI with rule-based fallback)."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning(
                "OPENAI_API_KEY not set - evaluation explanations will use the "
                "rule-based fallback"
            )
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)

        self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo")

    async def generate_report_card(
        self,
        problem_type: str,
        metrics: Union[ClassificationMetrics, RegressionMetrics],
        confusion_matrix: Optional[ConfusionMatrixData],
        feature_importance: Optional[Dict[str, float]],
        n_test_samples: int,
        model_name: Optional[str],
        algorithm: Optional[str],
    ) -> AIExplanation:
        """Build the AIExplanation report card; never raises.

        Tries OpenAI when a client is configured and falls back to the
        deterministic rule-based explanation on any failure.
        """
        context = self._build_context(
            problem_type,
            metrics,
            confusion_matrix,
            feature_importance,
            n_test_samples,
            model_name,
            algorithm,
        )
        if self.client is not None:
            explanation = await self._generate_openai_explanation(context)
            if explanation is not None:
                return explanation
        return self._generate_fallback_explanation(context)

    def _build_context(
        self,
        problem_type: str,
        metrics: Union[ClassificationMetrics, RegressionMetrics],
        confusion_matrix: Optional[ConfusionMatrixData],
        feature_importance: Optional[Dict[str, float]],
        n_test_samples: int,
        model_name: Optional[str],
        algorithm: Optional[str],
    ) -> Dict[str, Any]:
        """Normalize inputs into one dict shared by the prompt and the fallback."""
        top_features = (
            dict(
                sorted(
                    feature_importance.items(), key=lambda item: item[1], reverse=True
                )[:5]
            )
            if feature_importance
            else {}
        )
        return {
            "problem_type": problem_type,
            "is_classification": isinstance(metrics, ClassificationMetrics),
            "metrics": metrics.model_dump(),
            "confusion_matrix": (
                confusion_matrix.model_dump() if confusion_matrix else None
            ),
            "top_features": top_features,
            "n_test_samples": n_test_samples,
            "model_name": model_name or "the model",
            "algorithm": algorithm or "the selected algorithm",
        }

    @with_circuit_breaker(
        "openai",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(OpenAIError, Exception),
        fallback_value=None,
    )
    async def _generate_openai_explanation(
        self, context: Dict[str, Any]
    ) -> Optional[AIExplanation]:
        """Call OpenAI in JSON mode; returns None on any failure (fallback kicks in)."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._create_system_prompt()},
                    {"role": "user", "content": self._create_user_prompt(context)},
                ],
                temperature=0.4,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return AIExplanation(
                overall_assessment=str(data.get("overall_assessment", "")),
                metric_explanations={
                    str(key): str(value)
                    for key, value in (data.get("metric_explanations") or {}).items()
                },
                strengths=[str(item) for item in (data.get("strengths") or [])],
                concerns=[str(item) for item in (data.get("concerns") or [])],
                recommendations=[
                    str(item) for item in (data.get("recommendations") or [])
                ],
                generated_by="openai",
            )
        except Exception as exc:
            logger.error(f"OpenAI report-card generation failed: {exc}")
            return None

    @staticmethod
    def _create_system_prompt() -> str:
        return """You are a machine-learning educator explaining model evaluation results to a business analyst with no ML background.

Explain each metric in plain business terms, always comparing against a sensible baseline (e.g. always predicting the most common class, or predicting the average value). Be honest about weaknesses.

Respond in JSON with exactly this structure:
{
    "overall_assessment": "2-3 plain-language sentences on how good this model is and whether it is ready to use",
    "metric_explanations": {"<metric_name>": "one-sentence plain-language explanation of the value", ...},
    "strengths": ["array of model strengths, max 4"],
    "concerns": ["array of weaknesses or risks, max 4"],
    "recommendations": ["array of concrete next steps, max 4"]
}"""

    @staticmethod
    def _create_user_prompt(context: Dict[str, Any]) -> str:
        return (
            "Explain this model's evaluation results as a report card:\n\n"
            + json.dumps(
                {key: value for key, value in context.items() if value is not None},
                indent=2,
                default=str,
            )
        )

    def _generate_fallback_explanation(self, context: Dict[str, Any]) -> AIExplanation:
        """Deterministic rule-based report card (no API key required)."""
        if context["is_classification"]:
            return self._fallback_classification(context)
        return self._fallback_regression(context)

    @staticmethod
    def _quality_word(score: float) -> str:
        if score >= 0.9:
            return "excellent"
        if score >= 0.75:
            return "good"
        if score >= 0.6:
            return "fair"
        return "weak"

    def _fallback_classification(self, context: Dict[str, Any]) -> AIExplanation:
        metrics = context["metrics"]
        accuracy = metrics["accuracy"]
        f1_macro = metrics["f1_macro"]
        n_samples = context["n_test_samples"]

        strengths: List[str] = []
        concerns: List[str] = []
        recommendations: List[str] = []

        # Baseline: majority-class prevalence from the confusion matrix rows
        baseline = None
        imbalance_ratio = None
        confusion = context.get("confusion_matrix")
        if confusion and confusion["matrix"]:
            supports = [sum(row) for row in confusion["matrix"]]
            total = sum(supports)
            if total > 0:
                baseline = max(supports) / total
            positive_supports = [support for support in supports if support > 0]
            if len(positive_supports) >= 2:
                imbalance_ratio = max(positive_supports) / min(positive_supports)

        baseline_clause = (
            f", compared with {baseline:.0%} for always guessing the most common class"
            if baseline is not None
            else ""
        )
        overall = (
            f"{context['model_name']} ({context['algorithm']}) correctly classified "
            f"{accuracy:.0%} of the {n_samples} held-out test rows{baseline_clause}. "
            f"Overall performance is {self._quality_word(min(accuracy, f1_macro))}."
        )

        metric_explanations = {
            "accuracy": (
                f"Out of every 100 predictions, about {accuracy * 100:.0f} were correct."
            ),
            "f1_macro": (
                f"The balance of precision and recall averaged equally across classes "
                f"is {f1_macro:.2f} (1.00 is perfect); it treats rare classes as "
                f"seriously as common ones."
            ),
            "precision_macro": (
                "When the model predicts a class, this is how often it is right, "
                "averaged across classes."
            ),
            "recall_macro": (
                "Of the rows that truly belong to each class, this is the share "
                "the model finds, averaged across classes."
            ),
        }
        if metrics.get("roc_auc") is not None:
            metric_explanations["roc_auc"] = (
                f"A score of {metrics['roc_auc']:.2f} for ranking ability: 0.50 is "
                f"random guessing, 1.00 is perfect separation of the classes."
            )

        if accuracy >= 0.85:
            strengths.append(f"High overall accuracy ({accuracy:.0%}) on unseen data.")
        if baseline is not None and accuracy > baseline + 0.05:
            strengths.append(
                f"Clearly beats the {baseline:.0%} baseline of always predicting "
                f"the most common class."
            )
        if context["top_features"]:
            top = list(context["top_features"])[:3]
            strengths.append(f"Predictions are driven most by: {', '.join(top)}.")

        if baseline is not None and accuracy <= baseline + 0.02:
            concerns.append(
                "Accuracy is barely above always guessing the most common class; "
                "the model may not have learned a useful pattern."
            )
        if imbalance_ratio is not None and imbalance_ratio > 3:
            concerns.append(
                f"The test classes are imbalanced (about {imbalance_ratio:.0f}:1), "
                f"so accuracy alone can be misleading."
            )
            recommendations.append(
                "Judge the model by per-class F1 and recall rather than accuracy, "
                "and consider collecting more examples of the rare class."
            )
        weak_classes = [
            label
            for label, per_class in metrics.get("per_class_metrics", {}).items()
            if per_class["f1"] < 0.5 and per_class["support"] > 0
        ]
        if weak_classes:
            concerns.append(
                f"The model struggles with: {', '.join(weak_classes)} "
                f"(per-class F1 below 0.50)."
            )
            recommendations.append(
                "Review misclassified examples of the weak classes in the "
                "confusion matrix."
            )
        if f1_macro < 0.6:
            recommendations.append(
                "Try training with more data or additional features before "
                "relying on this model."
            )
        if not concerns:
            concerns.append(
                f"Results are based on {n_samples} held-out rows; verify on new "
                f"data before high-stakes use."
            )
        if not recommendations:
            recommendations.append(
                "Test the model on fresh data and monitor its accuracy over time."
            )

        return AIExplanation(
            overall_assessment=overall,
            metric_explanations=metric_explanations,
            strengths=strengths,
            concerns=concerns,
            recommendations=recommendations,
            generated_by="fallback",
        )

    def _fallback_regression(self, context: Dict[str, Any]) -> AIExplanation:
        metrics = context["metrics"]
        r2 = metrics["r2"]
        n_samples = context["n_test_samples"]

        r2_clamped = max(0.0, min(1.0, r2))
        overall = (
            f"{context['model_name']} ({context['algorithm']}) explains about "
            f"{r2_clamped:.0%} of the variation in the target on the {n_samples} "
            f"held-out test rows. Overall fit is {self._quality_word(r2_clamped)}."
        )

        metric_explanations = {
            "r2": (
                f"R-squared of {r2:.2f}: the share of the target's variation the "
                f"model explains (1.00 is perfect; 0 is no better than predicting "
                f"the average)."
            ),
            "mae": (
                f"On average, predictions are off by {metrics['mae']:.2f} in the "
                f"target's own units."
            ),
            "rmse": (
                f"Typical prediction error is {metrics['rmse']:.2f}; large misses "
                f"are penalized more heavily than in MAE."
            ),
        }
        if metrics.get("mape") is not None:
            metric_explanations["mape"] = (
                f"Predictions are off by about {metrics['mape']:.1f}% of the true "
                f"value on average."
            )

        strengths: List[str] = []
        concerns: List[str] = []
        recommendations: List[str] = []

        if r2 >= 0.75:
            strengths.append(
                f"Strong fit: the model explains {r2_clamped:.0%} of the target's "
                f"variation."
            )
        if context["top_features"]:
            top = list(context["top_features"])[:3]
            strengths.append(f"Predictions are driven most by: {', '.join(top)}.")

        if r2 < 0.3:
            concerns.append(
                "The model explains little of the target's variation; predictions "
                "may be close to just guessing the average."
            )
            recommendations.append(
                "Add more informative features or more training data before "
                "relying on this model."
            )
        if not concerns:
            concerns.append(
                f"Results are based on {n_samples} held-out rows; verify on new "
                f"data before high-stakes use."
            )
        if not recommendations:
            recommendations.append(
                "Compare predicted vs actual values on fresh data to confirm the "
                "error level is acceptable for your use case."
            )

        return AIExplanation(
            overall_assessment=overall,
            metric_explanations=metric_explanations,
            strengths=strengths,
            concerns=concerns,
            recommendations=recommendations,
            generated_by="fallback",
        )


# Singleton instance (mirrors dataset_summarization_service)
evaluation_explanation_service = EvaluationExplanationService()
