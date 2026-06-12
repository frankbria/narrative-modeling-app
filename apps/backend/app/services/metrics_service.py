"""Evaluation metric computations for the model evaluation dashboard (issue #79).

Pure functions over the held-out arrays persisted at training time
(``evaluation_data.json`` — see ``app.services.model_storage``). All label
comparisons happen in string space: the persisted ``class_labels`` are the
estimator's ``classes_`` rendered as strings (the same order as the columns
of ``y_proba``), and JSON round-trips int/float labels, so ``str()`` is the
one consistent mapping between them.
"""

import json
import logging
import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_curve,
    precision_recall_fscore_support,
    r2_score,
    roc_auc_score,
    roc_curve,
)

from app.models.ml_model import MLModel
from app.schemas.evaluation import (
    ClassificationMetrics,
    ConfusionMatrixData,
    CurvePoint,
    PerClassMetrics,
    PRCurveData,
    RegressionMetrics,
    ROCCurveData,
)
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)

# Maximum number of points per ROC/PR curve sent to the frontend
MAX_CURVE_POINTS = 200


def _as_str_array(values: Sequence[Any]) -> np.ndarray:
    """Render labels as strings (the persisted class_labels space)."""
    return np.asarray([str(v) for v in values])


def _safe_float(value: Any) -> Optional[float]:
    """Return a finite float, or None for NaN/inf (JSON-safe)."""
    as_float = float(value)
    return as_float if math.isfinite(as_float) else None


def _downsample_indices(n_points: int) -> np.ndarray:
    """Uniform-stride indices capping a curve at MAX_CURVE_POINTS.

    Always includes the first and last points so the curve endpoints
    (FPR 0 and 1 for ROC) survive downsampling.
    """
    if n_points <= MAX_CURVE_POINTS:
        return np.arange(n_points)
    return np.unique(np.linspace(0, n_points - 1, MAX_CURVE_POINTS).astype(int))


class MetricsService:
    """Compute dashboard metrics from persisted held-out evaluation arrays."""

    @staticmethod
    def _per_class_auc(
        yt: np.ndarray, proba: np.ndarray, labels: Sequence[str]
    ) -> Dict[str, float]:
        """One-vs-rest AUC per class, skipping classes with a degenerate split."""
        per_class_auc: Dict[str, float] = {}
        for i, label in enumerate(labels):
            if i >= proba.shape[1]:
                break  # probability columns must align with class_labels
            y_bin = (yt == label).astype(int)
            if len(np.unique(y_bin)) < 2:
                continue  # AUC undefined when a class is absent or fills y_test
            per_class_auc[label] = float(roc_auc_score(y_bin, proba[:, i]))
        return per_class_auc

    @staticmethod
    def compute_classification_metrics(
        y_test: Sequence[Any],
        y_pred: Sequence[Any],
        y_proba: Optional[Sequence[Sequence[float]]],
        class_labels: Optional[List[str]],
    ) -> ClassificationMetrics:
        """Aggregate + per-class classification metrics.

        ``roc_auc`` (macro one-vs-rest) and ``log_loss`` are ``None`` when
        ``y_proba`` is absent or the metric is undefined (e.g. a single true
        class in ``y_test``). Handles binary and multiclass; ``zero_division=0``
        throughout.
        """
        yt = _as_str_array(y_test)
        yp = _as_str_array(y_pred)
        labels = class_labels or sorted(set(yt) | set(yp))

        accuracy = float(accuracy_score(yt, yp))
        p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(
            yt, yp, labels=labels, average="macro", zero_division=0
        )
        p_weighted, r_weighted, f_weighted, _ = precision_recall_fscore_support(
            yt, yp, labels=labels, average="weighted", zero_division=0
        )
        per_p, per_r, per_f, per_s = precision_recall_fscore_support(
            yt, yp, labels=labels, average=None, zero_division=0
        )
        per_class_metrics = {
            label: PerClassMetrics(
                precision=float(per_p[i]),
                recall=float(per_r[i]),
                f1=float(per_f[i]),
                support=int(per_s[i]),
            )
            for i, label in enumerate(labels)
        }

        roc_auc_value: Optional[float] = None
        log_loss_value: Optional[float] = None
        if y_proba is not None:
            proba = np.asarray(y_proba, dtype=float)
            per_class_auc = MetricsService._per_class_auc(yt, proba, labels)
            if per_class_auc:
                roc_auc_value = _safe_float(np.mean(list(per_class_auc.values())))
            try:
                log_loss_value = _safe_float(log_loss(yt, proba, labels=labels))
            except ValueError as exc:
                logger.warning(f"log_loss undefined: {exc}")

        return ClassificationMetrics(
            accuracy=accuracy,
            precision_macro=float(p_macro),
            precision_weighted=float(p_weighted),
            recall_macro=float(r_macro),
            recall_weighted=float(r_weighted),
            f1_macro=float(f_macro),
            f1_weighted=float(f_weighted),
            roc_auc=roc_auc_value,
            log_loss=log_loss_value,
            per_class_metrics=per_class_metrics,
        )

    @staticmethod
    def compute_regression_metrics(
        y_test: Sequence[float], y_pred: Sequence[float]
    ) -> RegressionMetrics:
        """MAE/MSE/RMSE/R2 plus MAPE (as a percentage).

        ``mape`` is ``None`` when any ``y_test`` value is zero (undefined).
        """
        yt = np.asarray(y_test, dtype=float)
        yp = np.asarray(y_pred, dtype=float)

        mse = float(mean_squared_error(yt, yp))
        mape: Optional[float] = None
        if not np.any(yt == 0):
            mape = _safe_float(np.mean(np.abs((yt - yp) / yt)) * 100)

        return RegressionMetrics(
            mae=float(mean_absolute_error(yt, yp)),
            mse=mse,
            rmse=float(np.sqrt(mse)),
            r2=float(r2_score(yt, yp)),
            mape=mape,
        )

    @staticmethod
    def compute_confusion_matrix(
        y_test: Sequence[Any],
        y_pred: Sequence[Any],
        class_labels: Optional[List[str]],
    ) -> ConfusionMatrixData:
        """Confusion matrix in class_labels order (matrix[i][j] = actual i, predicted j)."""
        yt = _as_str_array(y_test)
        yp = _as_str_array(y_pred)
        labels = class_labels or sorted(set(yt) | set(yp))
        matrix = confusion_matrix(yt, yp, labels=labels)
        return ConfusionMatrixData(
            labels=list(labels),
            matrix=[[int(cell) for cell in row] for row in matrix],
        )

    @staticmethod
    def compute_roc_curves(
        y_test: Sequence[Any],
        y_proba: Optional[Sequence[Sequence[float]]],
        class_labels: List[str],
    ) -> Optional[ROCCurveData]:
        """One-vs-rest ROC curves per class, downsampled to <=200 points.

        Classes with a degenerate one-vs-rest split (absent from, or filling
        all of, ``y_test``) are skipped — their AUC is undefined. Returns
        ``None`` when probabilities are unavailable.
        """
        if y_proba is None:
            return None
        yt = _as_str_array(y_test)
        proba = np.asarray(y_proba, dtype=float)

        curves: Dict[str, List[CurvePoint]] = {}
        auc_per_class: Dict[str, float] = {}
        for i, label in enumerate(class_labels):
            y_bin = (yt == label).astype(int)
            if len(np.unique(y_bin)) < 2:
                continue  # one-vs-rest AUC undefined for this class
            fpr, tpr, thresholds = roc_curve(y_bin, proba[:, i])
            auc_per_class[label] = float(auc(fpr, tpr))
            indices = _downsample_indices(len(fpr))
            curves[label] = [
                CurvePoint(
                    x=float(fpr[idx]),
                    y=float(tpr[idx]),
                    threshold=_safe_float(thresholds[idx]),
                )
                for idx in indices
            ]

        macro_auc = (
            _safe_float(np.mean(list(auc_per_class.values())))
            if auc_per_class
            else None
        )
        return ROCCurveData(
            curves=curves, auc_per_class=auc_per_class, macro_auc=macro_auc
        )

    @staticmethod
    def compute_pr_curves(
        y_test: Sequence[Any],
        y_proba: Optional[Sequence[Sequence[float]]],
        class_labels: List[str],
    ) -> Optional[PRCurveData]:
        """One-vs-rest precision-recall curves per class (<=200 points each).

        ``baseline_per_class`` is each class's prevalence in ``y_test`` (the
        precision of a random classifier). Classes absent from ``y_test`` are
        skipped. Returns ``None`` when probabilities are unavailable.
        """
        if y_proba is None:
            return None
        yt = _as_str_array(y_test)
        proba = np.asarray(y_proba, dtype=float)

        curves: Dict[str, List[CurvePoint]] = {}
        baseline_per_class: Dict[str, float] = {}
        for i, label in enumerate(class_labels):
            y_bin = (yt == label).astype(int)
            if y_bin.sum() == 0:
                continue  # no positives: precision/recall undefined
            precision, recall, thresholds = precision_recall_curve(y_bin, proba[:, i])
            baseline_per_class[label] = float(y_bin.mean())
            indices = _downsample_indices(len(precision))
            curves[label] = [
                CurvePoint(
                    x=float(recall[idx]),
                    y=float(precision[idx]),
                    # precision/recall arrays have one more entry than thresholds
                    threshold=(
                        _safe_float(thresholds[idx]) if idx < len(thresholds) else None
                    ),
                )
                for idx in indices
            ]

        return PRCurveData(curves=curves, baseline_per_class=baseline_per_class)

    @staticmethod
    async def load_evaluation_artifacts(ml_model: MLModel) -> Optional[Dict[str, Any]]:
        """Download and parse the model's evaluation_data.json from S3.

        Returns ``None`` when the model has no ``evaluation_data_path`` (models
        trained before issue #79) or when the download/parse fails — callers
        degrade to partial (stored-scalar) results rather than erroring.
        """
        path = getattr(ml_model, "evaluation_data_path", None)
        if not path:
            return None
        key = path.replace(f"s3://{s3_service.bucket_name}/", "")
        if key.startswith("s3://"):
            # Stored under a different bucket (environment mismatch) — degrade
            # with a clear reason instead of a confusing S3 NoSuchKey error
            logger.warning(
                f"Evaluation artifact path for {ml_model.model_id} points at a "
                f"different bucket than the configured one: {path}"
            )
            return None
        try:
            raw = await s3_service.download_file_obj(key)
            payload = json.loads(raw)
        except Exception as exc:
            logger.warning(
                f"Could not load evaluation artifacts for {ml_model.model_id}: {exc}"
            )
            return None
        if not isinstance(payload, dict):
            logger.warning(
                f"Evaluation artifacts for {ml_model.model_id} are not a JSON object"
            )
            return None
        return payload
