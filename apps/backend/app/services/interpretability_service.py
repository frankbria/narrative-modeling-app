"""Model interpretability via SHAP values (issue #80, P3.3).

Provides the SHAP layer that #83 deferred. Two explainer families per the
beta scope (SHAP + feature importance only; LIME/PDP/ICE are post-beta):

* **Tree / ensemble models** (``feature_importances_``): ``shap.TreeExplainer``
  — needs no background data and yields per-row contributions.
* **Linear models** (``coef_``): ``shap.LinearExplainer`` with a sampled
  background — used for the *global* summary computed at training time, where
  the held-out feature matrix is available as background.

Anything else (KNN, kernel SVM, ...) is unsupported and returns ``None`` — the
documented "fall back to model-native importance" path (the stored
``feature_importance`` dict and #83's ``PredictionExplainerService`` cover it).

``shap`` is imported lazily inside the compute methods so importing this module
is cheap and a missing/broken shap install degrades to ``None`` rather than
crashing. Nothing here ever raises — interpretability is best-effort enrichment.

Contributions and importances are expressed over the *engineered* feature space
(the vector the estimator actually consumes), aligned with ``feature_names``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

#: Cap on rows explained for the global summary so SHAP stays fast (<30s for
#: typical beta datasets — issue #80 AC). Also used as the linear background size.
DEFAULT_MAX_SAMPLES = 200


def unwrap_estimator(estimator: Any) -> Any:
    """Dig through Calibrated / Frozen / Pipeline wrappers to the base model.

    Returns the first object exposing ``coef_`` or ``feature_importances_``,
    or the innermost object reached within a bounded number of hops.
    """
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


@dataclass
class GlobalShapResult:
    """Global SHAP summary for a model (the 'SHAP summary plot' data)."""

    explainer_type: str  # "tree" | "linear"
    shap_importance: dict[str, float]  # mean |SHAP| per feature (>= 0)
    base_value: float | None
    n_samples: int  # rows actually explained (after sampling)


@dataclass
class InstanceShapResult:
    """Per-prediction SHAP contributions (waterfall-style data)."""

    contributions: np.ndarray  # signed per-feature contribution for one row
    base_value: float | None
    explainer_type: str  # "tree"


class InterpretabilityService:
    """Compute SHAP global summaries and per-instance contributions."""

    # -- explainer selection ------------------------------------------------

    def select_explainer_type(self, estimator: Any) -> str | None:
        """Return ``"tree"``, ``"linear"``, or ``None`` for the estimator."""
        base = unwrap_estimator(estimator)
        if hasattr(base, "feature_importances_"):
            return "tree"
        if hasattr(base, "coef_"):
            return "linear"
        return None

    # -- global summary -----------------------------------------------------

    def compute_global_shap(
        self,
        estimator: Any,
        X: Any,
        feature_names: Sequence[str],
        problem_type: str = "classification",
        max_samples: int = DEFAULT_MAX_SAMPLES,
    ) -> GlobalShapResult | None:
        """Mean |SHAP| per feature over a sample of ``X``; ``None`` if blocked.

        ``X`` is the engineered feature matrix (DataFrame or ndarray) aligned
        with ``feature_names``. Best-effort: any failure (unsupported model,
        shap import error, computation error) yields ``None``.
        """
        try:
            return self._compute_global_shap(
                estimator, X, feature_names, problem_type, max_samples
            )
        except Exception as exc:  # noqa: BLE001 - interpretability is best-effort
            logger.warning("Global SHAP computation failed: %s", exc)
            return None

    def _compute_global_shap(
        self,
        estimator: Any,
        X: Any,
        feature_names: Sequence[str],
        problem_type: str,
        max_samples: int,
    ) -> GlobalShapResult | None:
        explainer_type = self.select_explainer_type(estimator)
        if explainer_type is None:
            return None

        base = unwrap_estimator(estimator)
        sample = self._sample_matrix(X, max_samples)
        if sample is None or sample.shape[0] == 0:
            return None

        import shap  # lazy: keep module import cheap and shap optional

        if explainer_type == "tree":
            explainer = shap.TreeExplainer(base)
        else:
            explainer = shap.LinearExplainer(base, sample)

        explanation = explainer(sample)
        values = np.asarray(explanation.values, dtype=float)
        # Multiclass / multi-output gives (n, features, classes); collapse the
        # class axis with mean-abs so importance is a single ranking.
        if values.ndim == 3:
            importance = np.abs(values).mean(axis=(0, 2))
        else:
            importance = np.abs(values).mean(axis=0)

        names = list(feature_names)
        n = min(len(names), importance.shape[0])
        shap_importance = {names[i]: float(importance[i]) for i in range(n)}

        base_value = self._scalar_base_value(explanation)

        return GlobalShapResult(
            explainer_type=explainer_type,
            shap_importance=shap_importance,
            base_value=base_value,
            n_samples=int(sample.shape[0]),
        )

    # -- per-instance -------------------------------------------------------

    def compute_instance_shap(
        self,
        estimator: Any,
        x_row: Sequence[float] | np.ndarray,
        feature_names: Sequence[str],
        prediction: Any = None,
        problem_type: str = "classification",
    ) -> InstanceShapResult | None:
        """Per-row SHAP contributions for tree models; ``None`` otherwise.

        Only tree/ensemble models are explained per-instance: ``TreeExplainer``
        needs no background data, so it works at prediction time. Linear and
        other models are left to the native explainer (which already gives a
        per-row ``coef * value`` breakdown). Best-effort — never raises.
        """
        try:
            return self._compute_instance_shap(
                estimator, x_row, feature_names, prediction
            )
        except Exception as exc:  # noqa: BLE001 - interpretability is best-effort
            logger.warning("Instance SHAP computation failed: %s", exc)
            return None

    def _compute_instance_shap(
        self,
        estimator: Any,
        x_row: Sequence[float] | np.ndarray,
        feature_names: Sequence[str],
        prediction: Any,
    ) -> InstanceShapResult | None:
        base = unwrap_estimator(estimator)
        if not hasattr(base, "feature_importances_"):
            return None  # tree-only at prediction time (no background data)

        values = np.asarray(list(x_row), dtype=float).reshape(1, -1)

        import shap  # lazy

        explainer = shap.TreeExplainer(base)
        explanation = explainer(values)
        vals = np.asarray(explanation.values, dtype=float)

        if vals.ndim == 3:  # (1, features, classes)
            idx = self._class_index(base, prediction, vals.shape[2])
            contributions = vals[0, :, idx]
            base_value = self._base_value_for_class(explanation, idx)
        else:  # (1, features)
            contributions = vals[0]
            base_value = self._scalar_base_value(explanation)

        return InstanceShapResult(
            contributions=contributions,
            base_value=base_value,
            explainer_type="tree",
        )

    def compute_instance_shap_batch(
        self,
        estimator: Any,
        X: Any,
        feature_names: Sequence[str],
        predictions: Sequence[Any] | None = None,
        problem_type: str = "classification",
    ) -> list | None:
        """Per-row SHAP contributions for a whole matrix, building once.

        Tree-only (like ``compute_instance_shap``). Builds a single
        ``TreeExplainer`` and computes SHAP for every row in one call — far
        cheaper than rebuilding the explainer per row when explaining many
        predictions. Returns a list (length == n_rows) of per-row contribution
        arrays, or ``None`` if the model isn't tree-supported or on any failure.
        """
        try:
            return self._compute_instance_shap_batch(
                estimator, X, feature_names, predictions
            )
        except Exception as exc:  # noqa: BLE001 - interpretability is best-effort
            logger.warning("Batch instance SHAP computation failed: %s", exc)
            return None

    def _compute_instance_shap_batch(
        self,
        estimator: Any,
        X: Any,
        feature_names: Sequence[str],
        predictions: Sequence[Any] | None,
    ) -> list | None:
        base = unwrap_estimator(estimator)
        if not hasattr(base, "feature_importances_"):
            return None

        arr = np.asarray(X.to_numpy() if hasattr(X, "to_numpy") else X, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        import shap  # lazy

        explainer = shap.TreeExplainer(base)  # built once for the whole matrix
        explanation = explainer(arr)
        vals = np.asarray(explanation.values, dtype=float)

        rows: list = []
        for i in range(arr.shape[0]):
            if vals.ndim == 3:  # (n, features, classes)
                prediction = (
                    predictions[i]
                    if predictions is not None and i < len(predictions)
                    else None
                )
                idx = self._class_index(base, prediction, vals.shape[2])
                rows.append(vals[i, :, idx])
            else:  # (n, features)
                rows.append(vals[i])
        return rows

    # -- plain language -----------------------------------------------------

    def top_drivers_text(
        self, shap_importance: dict[str, float], top_n: int = 3
    ) -> str:
        """Plain-language summary of the most influential features."""
        if not isinstance(shap_importance, dict) or not shap_importance:
            return "No SHAP-based feature drivers are available for this model."
        ranked = sorted(shap_importance.items(), key=lambda kv: kv[1], reverse=True)
        top = [name for name, _ in ranked[: max(top_n, 1)]]
        if len(top) == 1:
            drivers, verb = top[0], "accounts"
        else:
            drivers, verb = ", ".join(top[:-1]) + f" and {top[-1]}", "account"
        return (
            f"{drivers} {verb} for most of this model's decisions, ranked by "
            f"their average impact on the model's output."
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _sample_matrix(X: Any, max_samples: int) -> np.ndarray | None:
        """Down-sample ``X`` to at most ``max_samples`` rows as a float ndarray."""
        if X is None:
            return None
        arr = np.asarray(X.to_numpy() if hasattr(X, "to_numpy") else X, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[0] > max_samples:
            rng = np.random.RandomState(42)
            idx = rng.choice(arr.shape[0], size=max_samples, replace=False)
            arr = arr[idx]
        return arr

    @staticmethod
    def _scalar_base_value(explanation: Any) -> float | None:
        """Best-effort single scalar base value from a SHAP Explanation."""
        try:
            base = np.asarray(explanation.base_values, dtype=float)
            return float(np.mean(base)) if base.size else None
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _base_value_for_class(explanation: Any, idx: int) -> float | None:
        try:
            base = np.asarray(explanation.base_values, dtype=float)
            flat = base.reshape(-1) if base.ndim <= 1 else base[0]
            if idx < flat.shape[0]:
                return float(flat[idx])
            return float(np.mean(base))
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _class_index(base: Any, prediction: Any, n_classes: int) -> int:
        """Resolve the class axis index for the predicted class.

        Falls back to the positive class (index 1) for binary, else 0.
        """
        classes_attr = getattr(base, "classes_", None)
        classes = list(classes_attr) if classes_attr is not None else []
        if prediction is not None and prediction in classes:
            return classes.index(prediction)
        # Default to the positive class for binary; index 0 only if somehow
        # called with a single column.
        return 1 if n_classes >= 2 else 0
