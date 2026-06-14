"""Per-prediction explainability (issues #83 + #80).

Produces a per-prediction feature-contribution breakdown, preferring SHAP
(issue #80) and falling back to model-native importance (issue #83):

* **Tree / ensemble models** (``feature_importances_``): per-row SHAP
  contributions via ``TreeExplainer`` (issue #80, method ``"shap_tree"``) —
  genuinely per-prediction, waterfall-style. If SHAP is unavailable, falls back
  to *global* ``feature_importances_`` (method ``"tree_importance"``, the same
  for every row — the documented #83 fallback).
* **Linear models** (``coef_``): the contribution of feature *i* is
  ``coef_i * value_i`` — already a genuinely per-row breakdown (method
  ``"linear_coefficients"``). ``LinearExplainer`` SHAP needs background data
  not available at prediction time, so the equivalent coef·value form is kept.
* **Otherwise**: an optionally-supplied stored ``feature_importance`` dict
  (persisted on ``MLModel`` at training time) is used; if none is available
  the model is simply not explainable and ``explain`` returns ``None``.

Contributions are expressed over the *engineered* feature space (the vector
the estimator actually consumes), so ``feature_value`` is the transformed
value. Calibrated and pipeline wrappers are unwrapped to find the underlying
estimator. Nothing here ever raises — explanations are best-effort enrichment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.services.interpretability_service import InterpretabilityService

logger = logging.getLogger(__name__)

DEFAULT_TOP_N = 5


@dataclass
class FeatureContributionResult:
    feature_name: str
    contribution: float
    feature_value: Optional[float]


@dataclass
class ExplanationResult:
    top_features: List[FeatureContributionResult]
    explanation_text: str
    method: str  # linear_coefficients | tree_importance | stored_importance


class PredictionExplainerService:
    """Generate per-prediction feature-contribution breakdowns (SHAP + native)."""

    def __init__(
        self, interpretability: Optional[InterpretabilityService] = None
    ) -> None:
        # Stateless collaborator; shap is imported lazily inside it.
        self._interpretability = interpretability or InterpretabilityService()

    def assemble(
        self,
        contributions: Sequence[float],
        feature_names: Sequence[str],
        x_row: Optional[Sequence[float]],
        prediction: Any = None,
        problem_type: str = "classification",
        method: str = "shap_tree",
        top_n: int = DEFAULT_TOP_N,
    ) -> Optional[ExplanationResult]:
        """Build an ``ExplanationResult`` from precomputed per-feature contributions.

        Used by callers (e.g. ``PredictionEnricher``) that compute SHAP
        contributions for many rows in one batch and then need the same
        top-N ranking + plain-language text as ``explain``. Best-effort.
        """
        try:
            contrib = np.asarray(contributions, dtype=float)
            values = (
                np.asarray(list(x_row), dtype=float).ravel()
                if x_row is not None
                else None
            )
            top = self._top_features(contrib, feature_names, values, top_n)
            if not top:
                return None
            text = self._explanation_text(top, prediction, problem_type)
            return ExplanationResult(
                top_features=top, explanation_text=text, method=method
            )
        except Exception as exc:  # noqa: BLE001 - explanations are best-effort
            logger.warning("Explanation assembly failed: %s", exc)
            return None

    def explain(
        self,
        estimator: Any,
        x_row: Sequence[float],
        feature_names: Sequence[str],
        prediction: Any = None,
        problem_type: str = "classification",
        feature_importance: Optional[Dict[str, float]] = None,
        top_n: int = DEFAULT_TOP_N,
    ) -> Optional[ExplanationResult]:
        """Explain a single prediction; ``None`` if the model isn't explainable.

        ``x_row`` is the *engineered* feature vector aligned with
        ``feature_names`` (the estimator's input space). Best-effort: any
        unexpected error yields ``None`` rather than failing the prediction.
        """
        try:
            return self._explain(
                estimator,
                x_row,
                feature_names,
                prediction,
                problem_type,
                feature_importance,
                top_n,
            )
        except Exception as exc:  # noqa: BLE001 - explanations are best-effort
            logger.warning("Explanation generation failed: %s", exc)
            return None

    def _explain(
        self,
        estimator: Any,
        x_row: Sequence[float],
        feature_names: Sequence[str],
        prediction: Any,
        problem_type: str,
        feature_importance: Optional[Dict[str, float]],
        top_n: int,
    ) -> Optional[ExplanationResult]:
        try:
            values = np.asarray(list(x_row), dtype=float).ravel()
        except (TypeError, ValueError):
            values = None

        base = self._unwrap_estimator(estimator)

        # Prefer per-row SHAP (issue #80) — for tree/ensemble models this gives
        # a genuine per-prediction breakdown instead of the global importance
        # fallback. Returns None for linear/unsupported models (and on any SHAP
        # failure), so the native path below still applies.
        contributions, method = self._instance_shap(
            estimator, values, feature_names, prediction, problem_type
        )

        if contributions is None:
            contributions, method = self._native_contributions(base, values, prediction)

        if contributions is None and feature_importance:
            contributions = self._from_importance_dict(
                feature_importance, feature_names
            )
            method = "stored_importance"

        if contributions is None:
            return None

        top = self._top_features(contributions, feature_names, values, top_n)
        if not top:
            return None

        text = self._explanation_text(top, prediction, problem_type)
        return ExplanationResult(top_features=top, explanation_text=text, method=method)

    # -- estimator introspection -------------------------------------------

    def _unwrap_estimator(self, estimator: Any) -> Any:
        """Dig through Calibrated / Frozen / Pipeline wrappers to the model."""
        obj = estimator
        for _ in range(5):  # bounded: avoid pathological nesting loops
            if hasattr(obj, "coef_") or hasattr(obj, "feature_importances_"):
                return obj
            calibrated = getattr(obj, "calibrated_classifiers_", None)
            if calibrated:
                obj = getattr(calibrated[0], "estimator", obj)
                continue
            inner = getattr(obj, "estimator", None)  # FrozenEstimator, wrappers
            if inner is not None and inner is not obj:
                obj = inner
                continue
            steps = getattr(obj, "steps", None)  # sklearn Pipeline
            if steps:
                obj = steps[-1][1]
                continue
            break
        return obj

    def _instance_shap(
        self,
        estimator: Any,
        values: Optional[np.ndarray],
        feature_names: Sequence[str],
        prediction: Any,
        problem_type: str,
    ):
        """Return ``(shap_contributions, "shap_tree")`` or ``(None, "")``.

        Per-row SHAP is only computed for tree/ensemble models (TreeExplainer
        needs no background data); everything else falls through to the native
        path. Best-effort: the service swallows its own errors and returns None.
        """
        if values is None:
            return None, ""
        instance = self._interpretability.compute_instance_shap(
            estimator, values, feature_names, prediction, problem_type
        )
        if instance is None:
            return None, ""
        return np.asarray(instance.contributions, dtype=float), "shap_tree"

    def _native_contributions(
        self, base: Any, values: Optional[np.ndarray], prediction: Any
    ):
        """Return ``(contribution_array, method)`` or ``(None, "")``."""
        if hasattr(base, "coef_") and values is not None:
            coef = np.asarray(base.coef_, dtype=float)
            row = self._coef_for_prediction(base, coef, prediction)
            if row is not None and row.shape[0] == values.shape[0]:
                return row * values, "linear_coefficients"
        if hasattr(base, "feature_importances_"):
            return np.asarray(base.feature_importances_, dtype=float), "tree_importance"
        return None, ""

    def _coef_for_prediction(
        self, base: Any, coef: np.ndarray, prediction: Any
    ) -> Optional[np.ndarray]:
        """Pick the coefficient row matching the predicted class."""
        if coef.ndim == 1:
            return coef
        if coef.shape[0] == 1:  # binary logistic / linear regression
            return coef[0]
        # multiclass: use the row for the predicted class when resolvable
        classes = list(getattr(base, "classes_", []))
        if prediction is not None and prediction in classes:
            return coef[classes.index(prediction)]
        # Unresolvable predicted class: signed mean across classes keeps a
        # direction (so the "increased/decreased" wording stays consistent)
        # while abs() ranking still surfaces the most influential features.
        return np.mean(coef, axis=0)

    def _from_importance_dict(
        self, importance: Dict[str, float], feature_names: Sequence[str]
    ) -> Optional[np.ndarray]:
        if not importance:
            return None
        return np.asarray(
            [float(importance.get(name, 0.0)) for name in feature_names], dtype=float
        )

    # -- assembly -----------------------------------------------------------

    def _top_features(
        self,
        contributions: np.ndarray,
        feature_names: Sequence[str],
        values: Optional[np.ndarray],
        top_n: int,
    ) -> List[FeatureContributionResult]:
        names = list(feature_names)
        n = min(len(names), len(contributions))
        order = sorted(range(n), key=lambda i: abs(contributions[i]), reverse=True)
        results: List[FeatureContributionResult] = []
        for i in order[: max(top_n, 0)]:
            value = float(values[i]) if values is not None and i < len(values) else None
            results.append(
                FeatureContributionResult(
                    feature_name=names[i],
                    contribution=float(contributions[i]),
                    feature_value=value,
                )
            )
        return results

    def _explanation_text(
        self,
        top: List[FeatureContributionResult],
        prediction: Any,
        problem_type: str,
    ) -> str:
        """Deterministic, rule-based plain-language summary (no LLM cost)."""
        if not top:
            return "No feature-level explanation is available for this prediction."

        subject = (
            f"The predicted value ({prediction})"
            if str(problem_type).endswith("regression")
            else f"The prediction ({prediction})"
        )
        parts = []
        for f in top[:3]:
            direction = "increased" if f.contribution >= 0 else "decreased"
            parts.append(f"{f.feature_name} ({direction} the result)")
        drivers = ", ".join(parts)
        return (
            f"{subject} was driven primarily by {drivers}. "
            f"Features are listed in order of their influence on this prediction."
        )
