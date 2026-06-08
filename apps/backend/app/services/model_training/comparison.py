"""
Helpers for summarising AutoML results: a model comparison table, a deterministic
(no-LLM) best-model explanation, and a ``DataProfile`` builder for the algorithm
recommender.

These are pure functions so they can be unit-tested without a database, S3, or an
OpenAI key. The plain-language explanation here is rule-based on purpose: it gives
the user a "why this model" narrative without any runtime LLM call or cost.
"""

from typing import List, Optional
import pandas as pd

from .automl_engine import ModelCandidate
from .algorithm_selector import DataProfile
from .problem_detector import ProblemType


def build_model_comparison(all_models: List[ModelCandidate]) -> List[dict]:
    """Build a side-by-side comparison table from trained candidates.

    Returns a list of dicts (algorithm, cv_score, test_score, training_time)
    ordered by CV score descending — ready to persist on a ``TrainingJob``.
    """
    ordered = sorted(
        all_models,
        key=lambda m: (m.cv_score if m.cv_score is not None else float("-inf")),
        reverse=True,
    )
    return [
        {
            "algorithm": m.name,
            "cv_score": m.cv_score,
            "test_score": m.test_score,
            "training_time": m.training_time,
        }
        for m in ordered
    ]


def _score_label(problem_type: ProblemType) -> str:
    """Human-readable name of the primary CV scoring metric."""
    if problem_type == ProblemType.BINARY_CLASSIFICATION:
        return "ROC AUC"
    if problem_type == ProblemType.MULTICLASS_CLASSIFICATION:
        return "weighted F1"
    if problem_type == ProblemType.REGRESSION:
        return "cross-validated error"
    return "cross-validated score"


def build_best_model_explanation(
    best_model: ModelCandidate,
    all_models: List[ModelCandidate],
    problem_type: ProblemType,
) -> str:
    """Produce a plain-language explanation of why ``best_model`` was chosen.

    Deterministic and LLM-free: compares the best model's cross-validated score
    against the runner-up and notes the candidate pool size.
    """
    metric = _score_label(problem_type)
    n = len(all_models)

    if best_model.cv_score is None:
        return (
            f"{best_model.name} was selected as the best model from "
            f"{n} trained candidate{'s' if n != 1 else ''}."
        )

    parts = [
        f"{best_model.name} was selected as the best model, with a {metric} of "
        f"{best_model.cv_score:.3f} across cross-validation"
    ]
    if best_model.test_score is not None:
        parts.append(f" and a hold-out test score of {best_model.test_score:.3f}")
    parts.append(f". It was compared against {n} candidate{'s' if n != 1 else ''}")

    runner_up = next(
        (m for m in all_models if m.name != best_model.name and m.cv_score is not None),
        None,
    )
    if runner_up is not None and runner_up.cv_score is not None:
        margin = best_model.cv_score - runner_up.cv_score
        parts.append(
            f", outperforming the next-best model ({runner_up.name}, "
            f"{runner_up.cv_score:.3f}) by {abs(margin):.3f}"
        )
    parts.append(".")
    return "".join(parts)


def build_data_profile(
    df: pd.DataFrame,
    target_column: str,
    problem_type: ProblemType,
    high_cardinality_threshold: int = 100,
) -> DataProfile:
    """Build a ``DataProfile`` of the feature columns for the algorithm recommender.

    The target column is excluded from the feature counts. ``class_balance_ratio``
    is the majority/minority class ratio for classification, ``None`` for regression.
    """
    features = df.drop(columns=[target_column], errors="ignore")
    n_samples = len(df)
    n_features = features.shape[1]

    numeric_cols = features.select_dtypes(include=["number"]).columns
    n_numeric = len(numeric_cols)
    n_categorical = n_features - n_numeric

    total_cells = n_samples * n_features
    missing_pct = (
        float(features.isnull().sum().sum()) / total_cells * 100 if total_cells else 0.0
    )

    high_cardinality = sum(
        1
        for col in features.columns
        if features[col].nunique(dropna=True) > high_cardinality_threshold
    )

    class_balance_ratio: Optional[float] = None
    if problem_type in (
        ProblemType.BINARY_CLASSIFICATION,
        ProblemType.MULTICLASS_CLASSIFICATION,
    ):
        counts = df[target_column].value_counts()
        if len(counts) > 1 and counts.min() > 0:
            class_balance_ratio = float(counts.max() / counts.min())

    if n_samples < 5000:
        size_category = "small"
    elif n_samples < 50000:
        size_category = "medium"
    else:
        size_category = "large"

    return DataProfile(
        n_samples=n_samples,
        n_features=n_features,
        n_numeric_features=n_numeric,
        n_categorical_features=n_categorical,
        class_balance_ratio=class_balance_ratio,
        missing_value_percentage=missing_pct,
        high_cardinality_features=high_cardinality,
        dataset_size_category=size_category,
    )
