"""Shared prediction-enrichment helpers (issue #83).

Single, production, and batch prediction pathways all need the same
confidence/uncertainty/explanation enrichment on top of raw predictions. This
module centralises that so the three endpoints stay consistent:

* ``per_record_confidence`` — calibrated confidence score + low-confidence flag
  for each classification record.
* ``prediction_intervals`` — symmetric regression prediction intervals from the
  model's stored ``residual_std``.
* ``explanations`` — per-record, model-native feature-contribution breakdowns
  with a plain-language summary.

Everything degrades gracefully: missing probabilities → no confidence, a
pre-#83 model → ``is_calibrated=False`` / no intervals, an unexplainable model
→ no explanations. Nothing here raises on the happy path of the callers.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np

from app.schemas.model import FeatureContribution, PredictionExplanation
from app.services.confidence_service import (
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    ConfidenceService,
)
from app.services.interpretability_service import InterpretabilityService
from app.services.prediction_explainer_service import PredictionExplainerService

logger = logging.getLogger(__name__)


class PredictionEnricher:
    """Confidence, uncertainty, and explanation enrichment for predictions."""

    def __init__(
        self, low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD
    ) -> None:
        self.threshold = low_confidence_threshold
        self.confidence = ConfidenceService()
        # Share one InterpretabilityService so the explainer and the batch
        # SHAP path below don't construct duplicate instances.
        self.interpretability = InterpretabilityService()
        self.explainer = PredictionExplainerService(self.interpretability)

    def per_record_confidence(
        self, probabilities: Optional[Sequence[Sequence[float]]]
    ) -> Tuple[Optional[List[float]], Optional[List[bool]]]:
        """Return ``(confidence_scores, low_confidence_flags)`` for each record.

        ``(None, None)`` when no probabilities are available (regression or an
        estimator without ``predict_proba``).
        """
        if not probabilities:
            return None, None
        scores: List[float] = []
        flags: List[bool] = []
        for row in probabilities:
            score = self.confidence.confidence_from_proba(row)
            if score is None:
                # An un-computable row (empty/malformed proba) is treated as
                # 0 confidence AND flagged low-confidence, so clients never see
                # the impossible "0% but not flagged" combination.
                scores.append(0.0)
                flags.append(True)
            else:
                scores.append(score)
                flags.append(self.confidence.is_low_confidence(score, self.threshold))
        return scores, flags

    def prediction_intervals(
        self, predictions: Sequence[Any], residual_std: Optional[float]
    ) -> Optional[List[Optional[List[float]]]]:
        """Symmetric regression intervals, or ``None`` when unavailable."""
        if residual_std is None:
            return None
        intervals: List[Optional[List[float]]] = []
        for pred in predictions:
            intervals.append(self.confidence.regression_interval(pred, residual_std))
        return intervals

    def explanations(
        self,
        estimator: Any,
        transformed_rows: Any,
        feature_names: Sequence[str],
        predictions: Sequence[Any],
        problem_type: str,
        feature_importance: Optional[dict] = None,
        top_n: int = 5,
    ) -> Optional[List[Optional[PredictionExplanation]]]:
        """Per-record explanations as API schema objects, or ``None``.

        ``transformed_rows`` is the engineered feature matrix the estimator
        consumes (DataFrame or ndarray). Returns one entry per prediction;
        individual entries may be ``None`` if a row can't be explained.
        """
        try:
            matrix = np.asarray(transformed_rows)
        except Exception:  # noqa: BLE001
            return None
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)

        # For tree models, compute SHAP for every row with a single explainer
        # build (issue #80) instead of rebuilding TreeExplainer per row inside
        # this loop — important for multi-row / batch prediction. ``None`` for
        # non-tree models (handled per-row below) or on any failure.
        shap_rows = self.interpretability.compute_instance_shap_batch(
            estimator, matrix, feature_names, predictions, problem_type
        )

        results: List[Optional[PredictionExplanation]] = []
        any_explained = False
        for i, pred in enumerate(predictions):
            row = matrix[i] if i < len(matrix) else None
            if row is None:
                results.append(None)
                continue
            result = None
            if shap_rows is not None and i < len(shap_rows) and shap_rows[i] is not None:
                result = self.explainer.assemble(
                    shap_rows[i],
                    feature_names,
                    row,
                    prediction=pred,
                    problem_type=problem_type,
                    method="shap_tree",
                    top_n=top_n,
                )
            if result is None:
                # Non-tree models (cheap, no explainer rebuild) or a SHAP-batch
                # failure fall back to the model-native per-row explanation.
                result = self.explainer.explain(
                    estimator,
                    row,
                    feature_names,
                    prediction=pred,
                    problem_type=problem_type,
                    feature_importance=feature_importance,
                    top_n=top_n,
                )
            if result is None:
                results.append(None)
                continue
            any_explained = True
            results.append(
                PredictionExplanation(
                    top_features=[
                        FeatureContribution(
                            feature_name=f.feature_name,
                            contribution=f.contribution,
                            feature_value=f.feature_value,
                        )
                        for f in result.top_features
                    ],
                    explanation_text=result.explanation_text,
                    method=result.method,
                )
            )
        return results if any_explained else None
