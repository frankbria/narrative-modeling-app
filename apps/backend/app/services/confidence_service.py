"""Confidence scoring and probability calibration (issue #83).

This service holds the *pure* confidence/uncertainty helpers shared by the
single, production, and batch prediction pathways, plus the training-time
calibration step:

* ``confidence_from_proba`` / ``is_low_confidence`` — derive a 0-1 confidence
  score from a ``predict_proba`` row and flag low-confidence predictions.
* ``calibrate_classifier`` — wrap an already-fitted classifier in
  ``CalibratedClassifierCV(FrozenEstimator(...))`` (the forward-compatible
  replacement for the removed ``cv="prefit"``) using a held-out split, so the
  persisted model yields *calibrated* probabilities (AC1).
* ``regression_interval`` / ``residual_std`` — express regression uncertainty
  as a symmetric prediction interval derived from held-out residuals (AC2).

The helpers never raise on bad input; calibration degrades to
``(None, None, None)`` so training never fails because of it.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, log_loss

logger = logging.getLogger(__name__)

# Predictions whose confidence falls *below* this are flagged low-confidence.
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.7

# Isotonic calibration needs enough samples to avoid over-fitting the
# calibration curve; below this we use Platt scaling (sigmoid).
ISOTONIC_MIN_SAMPLES = 1000

# z-score for a ~95% Gaussian prediction interval.
_Z_95 = 1.96


class ConfidenceService:
    """Stateless helpers for confidence scoring and calibration."""

    def confidence_from_proba(
        self, proba_row: Sequence[float] | None
    ) -> float | None:
        """Confidence (0-1) for a single prediction = max class probability.

        Returns ``None`` when no probabilities are available (e.g. regression
        or an estimator without ``predict_proba``).
        """
        if proba_row is None:
            return None
        row = list(proba_row)
        if not row:
            return None
        try:
            return float(max(row))
        except (TypeError, ValueError):
            return None

    def is_low_confidence(
        self,
        confidence_score: float | None,
        threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    ) -> bool:
        """True when ``confidence_score`` is below ``threshold``.

        A missing score is *not* flagged (there is nothing to warn about).
        """
        if confidence_score is None:
            return False
        return float(confidence_score) < threshold

    def calibrate_classifier(
        self,
        estimator: Any,
        X_cal: Any,
        y_cal: Any,
        method: str | None = None,
    ) -> tuple[CalibratedClassifierCV | None, str | None, float | None]:
        """Calibrate a fitted classifier on a held-out split.

        Wraps ``estimator`` (already fitted) in
        ``CalibratedClassifierCV(FrozenEstimator(estimator))`` so its
        probabilities are calibrated without refitting the base model.
        ``method`` defaults to ``"isotonic"`` for large calibration sets and
        ``"sigmoid"`` (Platt scaling) otherwise.

        Returns ``(calibrated_estimator, method, brier_score)``. **The Brier /
        log-loss score is an in-sample diagnostic** — it is measured on the
        same ``X_cal`` the calibrator was fit on, so it is optimistic and is
        only meant for rough relative comparison, not as an unbiased estimate.
        On any failure (e.g. a degenerate single-class calibration set) returns
        ``(None, None, None)`` and never raises — calibration is best-effort.
        """
        try:
            y_arr = np.asarray(y_cal)
            n_samples = len(y_arr)
            if n_samples == 0 or len(np.unique(y_arr)) < 2:
                logger.warning(
                    "Skipping calibration: need >=2 classes and samples, got "
                    "%d samples / %d classes",
                    n_samples,
                    len(np.unique(y_arr)),
                )
                return None, None, None

            chosen = method or (
                "isotonic" if n_samples >= ISOTONIC_MIN_SAMPLES else "sigmoid"
            )
            # ``FrozenEstimator`` replaces the deprecated ``cv="prefit"``
            # (removed in sklearn 1.8): calibrate without refitting the model.
            calibrated = CalibratedClassifierCV(
                FrozenEstimator(estimator), method=chosen
            )
            calibrated.fit(X_cal, y_cal)
            brier = self._calibration_brier(calibrated, X_cal, y_arr)
            return calibrated, chosen, brier
        except Exception as exc:  # noqa: BLE001 - calibration must never break training
            logger.warning("Calibration failed, falling back to raw model: %s", exc)
            return None, None, None

    def _calibration_brier(
        self, calibrated: CalibratedClassifierCV, X_cal: Any, y_arr: np.ndarray
    ) -> float | None:
        """Calibration quality: Brier score (binary) or log loss (multiclass).

        Measured in-sample on ``X_cal`` (the calibration-fit data), so it is an
        optimistic diagnostic — see ``calibrate_classifier``.
        """
        try:
            proba = calibrated.predict_proba(X_cal)
            classes = list(calibrated.classes_)
            if len(classes) == 2:
                positive = classes[1]
                y_binary = (y_arr == positive).astype(int)
                return float(brier_score_loss(y_binary, proba[:, 1]))
            return float(log_loss(y_arr, proba, labels=classes))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not compute calibration score: %s", exc)
            return None

    def residual_std(self, y_test: Any, y_pred: Any) -> float | None:
        """Standard deviation of held-out regression residuals, or ``None``."""
        try:
            residuals = np.asarray(y_test, dtype=float) - np.asarray(
                y_pred, dtype=float
            )
            if residuals.size == 0:
                return None
            return float(np.std(residuals))
        except (TypeError, ValueError):
            return None

    def regression_interval(
        self,
        prediction: float,
        residual_std: float | None,
        z: float = _Z_95,
    ) -> list[float] | None:
        """Symmetric ~95% prediction interval ``[low, high]`` around a value.

        Returns ``None`` when no residual spread is known (the model predates
        this feature or residuals were unavailable).
        """
        if residual_std is None:
            return None
        try:
            margin = z * float(residual_std)
            value = float(prediction)
            return [value - margin, value + margin]
        except (TypeError, ValueError):
            return None
