"""
AI-powered explanation service for model training decisions
"""

import logging
import os
from typing import Any

from openai import OpenAI

from .algorithm_selector import AlgorithmRecommendation, DataProfile
from .problem_detector import ProblemType

logger = logging.getLogger(__name__)

# Initialize OpenAI client (will be initialized by app startup)
client: OpenAI | None = None


def initialize_openai_client():
    """Initialize the OpenAI client"""
    global client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set - explanations will use fallback text")
        return
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI client initialized for explanations")


# Get model from environment
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")


class ExplanationService:
    """
    Generate AI-powered explanations for model training decisions
    """

    def __init__(self):
        self.model = OPENAI_MODEL

    async def explain_algorithm_selection(
        self,
        algorithms: list[AlgorithmRecommendation],
        data_profile: DataProfile,
        problem_type: ProblemType
    ) -> str:
        """
        Generate explanation for why specific algorithms were selected

        Args:
            algorithms: List of recommended algorithms
            data_profile: Dataset characteristics
            problem_type: Type of ML problem

        Returns:
            Natural language explanation
        """
        if not client:
            return self._fallback_algorithm_explanation(algorithms, data_profile)

        try:
            # Build prompt
            prompt = self._build_algorithm_selection_prompt(
                algorithms, data_profile, problem_type
            )

            # Call OpenAI
            response = self._call_openai(prompt)
            return response

        except Exception as e:
            logger.error(f"Error generating algorithm explanation: {e}")
            return self._fallback_algorithm_explanation(algorithms, data_profile)

    async def explain_best_model(
        self,
        best_model: dict[str, Any],
        all_models: list[dict[str, Any]],
        comparison_metrics: dict[str, Any]
    ) -> str:
        """
        Generate explanation for why a specific model was chosen as best

        Args:
            best_model: The best performing model
            all_models: All trained models
            comparison_metrics: Metrics used for comparison

        Returns:
            Natural language explanation
        """
        if not client:
            return self._fallback_best_model_explanation(best_model, all_models)

        try:
            # Build prompt
            prompt = self._build_best_model_prompt(
                best_model, all_models, comparison_metrics
            )

            # Call OpenAI
            response = self._call_openai(prompt)
            return response

        except Exception as e:
            logger.error(f"Error generating best model explanation: {e}")
            return self._fallback_best_model_explanation(best_model, all_models)

    async def explain_model_tradeoffs(
        self,
        model_a: dict[str, Any],
        model_b: dict[str, Any]
    ) -> str:
        """
        Generate explanation of trade-offs between two models

        Args:
            model_a: First model
            model_b: Second model

        Returns:
            Natural language explanation of trade-offs
        """
        if not client:
            return self._fallback_tradeoff_explanation(model_a, model_b)

        try:
            # Build prompt
            prompt = self._build_tradeoff_prompt(model_a, model_b)

            # Call OpenAI
            response = self._call_openai(prompt)
            return response

        except Exception as e:
            logger.error(f"Error generating tradeoff explanation: {e}")
            return self._fallback_tradeoff_explanation(model_a, model_b)

    def _call_openai(self, prompt: str) -> str:
        """
        Call OpenAI API with the given prompt
        Note: This is synchronous because the OpenAI client is synchronous

        Args:
            prompt: The prompt to send

        Returns:
            Response text
        """
        messages = [
            {
                "role": "system",
                "content": "You are an expert ML engineer explaining model selection decisions to data analysts. "
                          "Provide clear, concise explanations that are technically accurate but accessible. "
                          "Focus on practical implications and trade-offs."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        if client is None:
            raise RuntimeError("OpenAI client is not initialized")

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]  # plain dicts accepted at runtime
            temperature=0.7,
            max_tokens=500
        )

        return response.choices[0].message.content or ""

    def _build_algorithm_selection_prompt(
        self,
        algorithms: list[AlgorithmRecommendation],
        data_profile: DataProfile,
        problem_type: ProblemType
    ) -> str:
        """Build prompt for algorithm selection explanation"""
        algo_list = "\n".join([
            f"- {a.algorithm_name} (priority: {a.priority}, "
            f"expected: {a.expected_performance})"
            for a in algorithms[:5]  # Top 5
        ])

        prompt = f"""
Explain why these algorithms were recommended for a {problem_type.value} task:

Dataset characteristics:
- Samples: {data_profile.n_samples} ({data_profile.dataset_size_category} dataset)
- Features: {data_profile.n_features} ({data_profile.n_numeric_features} numeric, {data_profile.n_categorical_features} categorical)
- Class balance ratio: {data_profile.class_balance_ratio if data_profile.class_balance_ratio else 'N/A (regression)'}
- Missing values: {data_profile.missing_value_percentage:.1%}
- High cardinality features: {data_profile.high_cardinality_features}

Recommended algorithms:
{algo_list}

Provide a brief explanation (2-3 paragraphs) of why these algorithms are well-suited for this dataset.
Focus on how the dataset characteristics influenced the selection.
"""
        return prompt

    def _build_best_model_prompt(
        self,
        best_model: dict[str, Any],
        all_models: list[dict[str, Any]],
        comparison_metrics: dict[str, Any]
    ) -> str:
        """Build prompt for best model explanation"""
        model_comparison = "\n".join([
            f"- {m['name']}: CV Score={m.get('cv_score', 'N/A'):.4f}, "
            f"Test Score={m.get('test_score', 'N/A'):.4f}, "
            f"Time={m.get('training_time', 0):.1f}s"
            for m in all_models[:5]  # Top 5
        ])

        prompt = f"""
Explain why {best_model['name']} was selected as the best model:

Model performance comparison:
{model_comparison}

Primary metric: {comparison_metrics.get('primary_metric', 'accuracy')}

Best model details:
- CV Score: {best_model.get('cv_score', 'N/A')}
- Test Score: {best_model.get('test_score', 'N/A')}
- Training Time: {best_model.get('training_time', 0):.1f}s

Provide a brief explanation (2-3 paragraphs) of why this model was chosen.
Highlight its advantages and any trade-offs compared to other models.
"""
        return prompt

    def _build_tradeoff_prompt(
        self,
        model_a: dict[str, Any],
        model_b: dict[str, Any]
    ) -> str:
        """Build prompt for model tradeoff explanation"""
        prompt = f"""
Compare these two models and explain the trade-offs:

Model A: {model_a.get('name', 'Unknown')}
- CV Score: {model_a.get('cv_score', 'N/A')}
- Interpretability: {model_a.get('interpretability_score', 'N/A')}/10
- Training Time: {model_a.get('training_time', 0):.1f}s

Model B: {model_b.get('name', 'Unknown')}
- CV Score: {model_b.get('cv_score', 'N/A')}
- Interpretability: {model_b.get('interpretability_score', 'N/A')}/10
- Training Time: {model_b.get('training_time', 0):.1f}s

Provide a brief comparison (2 paragraphs) highlighting the key trade-offs.
Help the user understand when they might prefer one over the other.
"""
        return prompt

    def _fallback_algorithm_explanation(
        self,
        algorithms: list[AlgorithmRecommendation],
        data_profile: DataProfile
    ) -> str:
        """Fallback explanation when OpenAI is not available"""
        top_algo = algorithms[0] if algorithms else None
        if not top_algo:
            return "No algorithms were recommended for this dataset."

        explanation = (
            f"Based on your dataset characteristics ({data_profile.n_samples} samples, "
            f"{data_profile.n_features} features), we recommend starting with {top_algo.algorithm_name}. "
        )

        if data_profile.class_balance_ratio and data_profile.class_balance_ratio > 3.0:
            explanation += (
                "Your dataset shows class imbalance, so tree-based models "
                "are prioritized as they handle this better. "
            )

        if data_profile.dataset_size_category == "large":
            explanation += (
                "For large datasets, we prioritize algorithms like LightGBM and XGBoost "
                "that scale well. "
            )

        explanation += (
            f"The top recommendation is {top_algo.algorithm_name} because: "
            f"{', '.join(top_algo.pros[:2])}."
        )

        return explanation

    def _fallback_best_model_explanation(
        self,
        best_model: dict[str, Any],
        all_models: list[dict[str, Any]]
    ) -> str:
        """Fallback explanation for best model"""
        model_name = best_model.get('name', 'Unknown')
        cv_score = best_model.get('cv_score', 0)

        explanation = (
            f"{model_name} was selected as the best model because it achieved "
            f"the highest cross-validation score ({cv_score:.4f}). "
        )

        if len(all_models) > 1:
            second_best = all_models[1]
            second_score = second_best.get('cv_score', 0)
            if cv_score - second_score < 0.02:
                explanation += (
                    f"Note that {second_best.get('name', 'the second-best model')} "
                    f"performed similarly ({second_score:.4f}), so you might consider "
                    "comparing other factors like interpretability or training time."
                )

        return explanation

    def _fallback_tradeoff_explanation(
        self,
        model_a: dict[str, Any],
        model_b: dict[str, Any]
    ) -> str:
        """Fallback explanation for model tradeoffs"""
        name_a = model_a.get('name', 'Model A')
        name_b = model_b.get('name', 'Model B')
        score_a = model_a.get('cv_score', 0)
        score_b = model_b.get('cv_score', 0)

        if score_a > score_b:
            better, worse = name_a, name_b
            better_score, worse_score = score_a, score_b
        else:
            better, worse = name_b, name_a
            better_score, worse_score = score_b, score_a

        explanation = (
            f"{better} achieves higher accuracy ({better_score:.4f} vs {worse_score:.4f}). "
            f"However, {worse} may offer advantages in interpretability or training speed. "
            "Consider your priorities: accuracy vs. interpretability vs. computational efficiency."
        )

        return explanation
