"""
Core AutoML engine for automated model selection and training
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import Event
from typing import Any, Optional

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC, SVR

from app.services.confidence_service import ConfidenceService
from app.services.interpretability_service import (
    GlobalShapResult,
    InterpretabilityService,
)

from .feature_engineer import FeatureEngineer, FeatureEngineeringConfig
from .hyperparameter_tuner import HyperparameterTuner, TuningConfig, TuningResult
from .problem_detector import ProblemDetector, ProblemType

logger = logging.getLogger(__name__)

# Stateless — one shared instance avoids reconstructing it during training (#83).
_confidence_service = ConfidenceService()
# SHAP interpretability (issue #80). Stateless; shap is imported lazily inside it.
_interpretability_service = InterpretabilityService()


class TrainingCancelledError(Exception):
    """Raised when a training run is cancelled via the ``cancel_check`` hook."""


@dataclass
class TrainingEvent:
    """A monitoring event emitted while the AutoML pipeline runs.

    Carries a log line (``level`` + ``message``), the pipeline ``stage`` it was
    emitted from (``preprocessing`` | ``training`` | ``finalizing``), and — for
    per-candidate completion events — the candidate's results in ``candidate``
    (keys: ``algorithm``, ``cv_score``, ``test_score``, ``training_time``).
    """

    level: str
    message: str
    stage: str | None = None
    candidate: dict[str, Any] | None = None


@dataclass
class ModelCandidate:
    """A candidate model for training"""

    name: str
    estimator: Any
    hyperparameters: dict[str, Any]
    training_time: float | None = None
    cv_score: float | None = None
    test_score: float | None = None


@dataclass
class AutoMLResult:
    """Result of AutoML process.

    ``y_test``/``y_pred``/``y_proba``/``class_labels`` are the BEST model's
    held-out evaluation artifacts (issue #79). The FeatureEngineer never
    transforms the target, so labels are in the original label space and
    ``class_labels`` follows the estimator's ``classes_`` ordering — the same
    ordering as the columns of ``y_proba``. ``y_proba`` and ``class_labels``
    are ``None`` for regression (and ``y_proba`` also when the best estimator
    has no ``predict_proba``).
    """

    best_model: ModelCandidate
    all_models: list[ModelCandidate]
    problem_type: ProblemType
    feature_names: list[str]
    feature_importance: dict[str, float] | None
    training_time: float
    metadata: dict[str, Any]
    y_test: np.ndarray | None = None
    y_pred: np.ndarray | None = None
    y_proba: np.ndarray | None = None
    class_labels: list[str] | None = None
    # Held-out transformed feature matrix for error analysis (issue #81), aligned
    # row-for-row with ``y_test``/``y_pred``. ``None`` when unavailable; columns
    # follow ``feature_names``.
    x_test: np.ndarray | None = None
    # Confidence/uncertainty metadata (issue #83). ``best_model.estimator`` is
    # swapped for its calibrated wrapper when ``is_calibrated`` is True, so the
    # persisted model yields calibrated probabilities. ``residual_std`` powers
    # regression prediction intervals; both are ``None`` when unavailable.
    is_calibrated: bool = False
    calibration_method: str | None = None
    calibration_score: float | None = None
    residual_std: float | None = None
    # SHAP global interpretability summary (issue #80). ``shap_global`` is a
    # ``GlobalShapResult`` for the best model, computed on the held-out set from
    # the RAW estimator *before* calibration (the calibrated wrapper hides the
    # tree/linear internals SHAP needs). ``None`` for unsupported model types
    # (KNN, kernel SVM), which fall back to model-native importance.
    shap_global: Optional["GlobalShapResult"] = None
    shap_explainer_type: str | None = None
    # Hyperparameter tuning summary (issue #77). Populated only when tuning was
    # enabled. ``tuning_results`` maps each tuned algorithm name to its serialized
    # ``TuningResult`` (best params + inline visualization data);
    # ``improvement_from_tuning`` is the best model's CV-score gain over its
    # default hyperparameters. All ``None`` when tuning was off.
    tuning_results: dict[str, dict[str, Any]] | None = None
    tuning_strategy: str | None = None
    improvement_from_tuning: float | None = None


def _applied_improvement(payload: dict[str, Any] | None) -> float | None:
    """The tuning gain the deployed model kept (see ``improvement_from_tuning``)."""
    if not payload:
        return None
    if payload.get("applied"):
        return payload.get("improvement_over_default")
    return 0.0


class AutoMLEngine:
    """Main AutoML engine for automated machine learning"""

    def __init__(
        self,
        max_models: int = 10,
        time_limit: int | None = None,
        cv_folds: int = 5,
        test_size: float = 0.2,
        random_state: int = 42,
        enable_tuning: bool = False,
        tuning_config: TuningConfig | None = None,
    ):
        self.max_models = max_models
        self.time_limit = time_limit
        self.cv_folds = cv_folds
        self.test_size = test_size
        self.random_state = random_state
        # Hyperparameter tuning (issue #77) is opt-in. When enabled, each
        # candidate is tuned before training and the best params are applied.
        self.enable_tuning = enable_tuning
        self.tuning_config = tuning_config

        self.problem_detector = ProblemDetector()
        self.feature_engineer = FeatureEngineer()
        self._tuner = HyperparameterTuner()

    async def run(
        self,
        df: pd.DataFrame,
        target_column: str,
        feature_config: FeatureEngineeringConfig | None = None,
        progress_callback: Callable[[int, int, str | None], Awaitable[None]] | None = None,
        event_callback: Callable[[TrainingEvent], Awaitable[None]] | None = None,
        cancel_check: Callable[[], Awaitable[bool]] | None = None,
    ) -> AutoMLResult:
        """
        Run the AutoML pipeline

        Args:
            df: Input dataframe
            target_column: Name of target column
            feature_config: Feature engineering configuration
            progress_callback: Optional async callback invoked as
                ``await progress_callback(completed, total, current_algorithm)``
                before each candidate is trained and once more when all
                candidates finish. Callback errors are swallowed so progress
                reporting never breaks training.
            event_callback: Optional async callback receiving ``TrainingEvent``
                log/stage/candidate events as the pipeline runs. Callback
                errors are swallowed so event reporting never breaks training.
            cancel_check: Optional async callable awaited before each candidate
                is trained and once more before finalization; returning True
                aborts the run by raising ``TrainingCancelledError``. Errors
                raised by the check itself are swallowed and treated as "not
                cancelled".

        Returns:
            AutoMLResult with best model and metadata

        Raises:
            TrainingCancelledError: When ``cancel_check`` returns True.
        """
        start_time = datetime.now(UTC)

        await self._emit_event(
            event_callback,
            TrainingEvent(
                level="info",
                message="Preparing data and engineering features",
                stage="preprocessing",
            ),
        )

        # Detect problem type
        detection_result = await self.problem_detector.detect_problem_type(
            df, target_column
        )
        problem_type = detection_result.problem_type

        logger.info(f"Detected problem type: {problem_type.value}")

        # Prepare data
        X = df.drop(columns=[target_column])
        y = df[target_column]

        is_classification = problem_type in [
            ProblemType.BINARY_CLASSIFICATION,
            ProblemType.MULTICLASS_CLASSIFICATION,
        ]

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=y if is_classification else None,
        )

        # Detect class imbalance and enable basic handling (class weighting).
        # This is the lightweight "basic class-imbalance handling" of the beta
        # scope: no resampling (SMOTE etc.), just class_weight="balanced" on the
        # estimators that support it.
        class_balance_ratio, class_weight = self._assess_class_balance(
            y_train, is_classification
        )

        # Feature engineering
        if feature_config:
            self.feature_engineer.config = feature_config

        feature_result = await self.feature_engineer.fit_transform(
            X_train, y_train, problem_type.value
        )
        X_train_transformed = feature_result.X_transformed

        # Transform test data
        X_test_transformed = await self.feature_engineer.transform(X_test)

        # Get candidate models
        candidates = self._get_candidate_models(
            problem_type, X_train_transformed.shape, class_weight=class_weight
        )

        # Train and evaluate models
        selected_candidates = candidates[: self.max_models]
        total_candidates = len(selected_candidates)
        trained_models = []

        # Optional hyperparameter tuning (issue #77). Runs before the training
        # loop so the best params are applied to each candidate's estimator and
        # then fitted/CV'd normally below. Best-effort: a candidate that can't be
        # tuned simply keeps its default hyperparameters.
        tuning_results: dict[str, dict[str, Any]] = {}
        if self.enable_tuning:
            tuning_results = await self._tune_candidates(
                selected_candidates,
                X_train_transformed,
                y_train,
                problem_type,
                is_classification,
                event_callback,
                cancel_check,
            )

        await self._emit_event(
            event_callback,
            TrainingEvent(
                level="info",
                message=f"Training {total_candidates} candidate models",
                stage="training",
            ),
        )

        for index, candidate in enumerate(selected_candidates):
            if await self._is_cancelled(cancel_check):
                raise TrainingCancelledError(
                    f"Training cancelled before {candidate.name}"
                )

            logger.info(f"Training {candidate.name}...")
            await self._report_progress(
                progress_callback, index, total_candidates, candidate.name
            )

            try:
                # Train model. The fit/CV/predict calls are CPU-bound and run
                # in a worker thread: executed inline they block the event
                # loop for the whole fit, freezing every API request —
                # including the status polls and the cancel endpoint this
                # feature depends on.
                model_start = datetime.now(UTC)
                await asyncio.to_thread(
                    candidate.estimator.fit, X_train_transformed, y_train
                )
                candidate.training_time = (
                    datetime.now(UTC) - model_start
                ).total_seconds()

                # Cross-validation score
                cv_scores = await asyncio.to_thread(
                    cross_val_score,
                    candidate.estimator,
                    X_train_transformed,
                    y_train,
                    cv=self.cv_folds,
                    scoring=self._get_scoring_metric(problem_type),
                )
                candidate.cv_score = np.mean(cv_scores)

                # Test score
                y_pred = await asyncio.to_thread(
                    candidate.estimator.predict, X_test_transformed
                )
                candidate.test_score = self._calculate_test_score(
                    y_test, y_pred, problem_type
                )

                trained_models.append(candidate)
                logger.info(
                    f"{candidate.name} - CV Score: {candidate.cv_score:.4f}, Test Score: {candidate.test_score:.4f}"
                )
                await self._emit_event(
                    event_callback,
                    TrainingEvent(
                        level="info",
                        message=(
                            f"{candidate.name} trained: "
                            f"cv_score={candidate.cv_score:.4f}, "
                            f"test_score={candidate.test_score:.4f}, "
                            f"training_time={candidate.training_time:.2f}s"
                        ),
                        stage="training",
                        candidate={
                            "algorithm": candidate.name,
                            "cv_score": candidate.cv_score,
                            "test_score": candidate.test_score,
                            "training_time": candidate.training_time,
                        },
                    ),
                )

            except Exception as e:
                logger.error(f"Error training {candidate.name}: {str(e)}")
                await self._emit_event(
                    event_callback,
                    TrainingEvent(
                        level="warning",
                        message=f"{candidate.name} failed to train: {e}",
                        stage="training",
                    ),
                )
                continue

        # Final cancellation check: a cancel that arrived while the last
        # candidate was fitting would otherwise be acknowledged by the API
        # but silently ignored, completing the job anyway.
        if await self._is_cancelled(cancel_check):
            raise TrainingCancelledError("Training cancelled before finalization")

        # Final progress tick: all candidates processed.
        await self._report_progress(
            progress_callback, total_candidates, total_candidates, None
        )

        await self._emit_event(
            event_callback,
            TrainingEvent(
                level="info",
                message="Selecting the best model",
                stage="finalizing",
            ),
        )

        # Select best model
        if not trained_models:
            raise ValueError("No models were successfully trained")
        # cv_score is Optional; treat a missing score as worst so ordering is total.
        best_model = max(
            trained_models,
            key=lambda m: m.cv_score if m.cv_score is not None else float("-inf"),
        )
        ranked_models = sorted(
            trained_models,
            key=lambda m: m.cv_score if m.cv_score is not None else float("-inf"),
            reverse=True,
        )

        # Get feature importance if available. Extracted from the RAW estimator
        # *before* calibration, because the calibrated wrapper hides
        # ``feature_importances_`` / ``coef_``.
        feature_importance = self._get_feature_importance(
            best_model.estimator, feature_result.feature_names
        )

        # SHAP global summary (issue #80). Computed on the held-out set from the
        # RAW estimator *before* calibration, for the same reason as
        # feature_importance: the calibrated wrapper hides the tree/linear
        # internals SHAP introspects. Best-effort — unsupported models and any
        # SHAP failure simply leave ``shap_global`` as ``None`` and the system
        # falls back to model-native importance.
        shap_global = await self._compute_global_shap(
            best_model.estimator,
            X_test_transformed,
            feature_result.feature_names,
            problem_type,
            event_callback,
        )

        # SHAP can take noticeable time on tree/linear models, so honour a
        # cancellation requested while it ran before doing the remaining
        # finalization work (calibration + persistence).
        if await self._is_cancelled(cancel_check):
            raise TrainingCancelledError("Training cancelled during finalization")

        # Confidence calibration for issue #83 — classification only. The best
        # estimator is swapped in place for its calibrated wrapper so the
        # *deployed* model yields calibrated probabilities. Best-effort: a
        # failure leaves the raw model untouched.
        (
            is_calibrated,
            calibration_method,
            calibration_score,
        ) = await self._calibrate_best_model(
            best_model, X_test_transformed, y_test, is_classification
        )

        # Capture the (now possibly calibrated) best model's held-out
        # evaluation artifacts (issue #79) AFTER calibration so the dashboard
        # metrics describe exactly the model that gets deployed. Calibration is
        # fit on this same held-out split (a documented beta limitation).
        y_pred_best, y_proba_best, class_labels = await self._capture_evaluation_arrays(
            best_model.estimator, X_test_transformed, is_classification
        )

        # Calibration can shift held-out predictions, so recompute the best
        # model's test score from the deployed model's predictions — otherwise
        # the persisted `test_score` / model-comparison row would describe the
        # pre-calibration estimator (issue #83 review fix).
        if is_calibrated:
            best_model.test_score = self._calculate_test_score(
                y_test, y_pred_best, problem_type
            )

        # Regression uncertainty: held-out residual std powers prediction
        # intervals (issue #83). ``None`` for classification.
        residual_std = (
            None
            if is_classification
            else await asyncio.to_thread(
                _confidence_service.residual_std, y_test, y_pred_best
            )
        )

        total_time = (datetime.now(UTC) - start_time).total_seconds()

        await self._emit_event(
            event_callback,
            TrainingEvent(
                level="info",
                message=(
                    f"Training complete: best model is {best_model.name} "
                    f"(cv_score={best_model.cv_score:.4f}, "
                    f"test_score={best_model.test_score:.4f}) "
                    f"after {total_time:.2f}s"
                ),
                stage="finalizing",
            ),
        )

        # Side-by-side comparison of every trained candidate, ranked by CV score.
        model_comparison = [
            {
                "algorithm": m.name,
                "cv_score": m.cv_score,
                "test_score": m.test_score,
                "training_time": m.training_time,
            }
            for m in ranked_models
        ]

        return AutoMLResult(
            best_model=best_model,
            all_models=ranked_models,
            problem_type=problem_type,
            feature_names=feature_result.feature_names,
            feature_importance=feature_importance,
            training_time=total_time,
            y_test=np.asarray(y_test),
            y_pred=y_pred_best,
            y_proba=y_proba_best,
            class_labels=class_labels,
            x_test=np.asarray(X_test_transformed),
            is_calibrated=is_calibrated,
            calibration_method=calibration_method,
            calibration_score=calibration_score,
            residual_std=residual_std,
            shap_global=shap_global,
            shap_explainer_type=shap_global.explainer_type if shap_global else None,
            tuning_results=tuning_results or None,
            tuning_strategy=(
                (self.tuning_config or TuningConfig()).strategy
                if self.enable_tuning
                else None
            ),
            # Gain the deployed best model actually got from tuning: its recorded
            # improvement when the tuned params were applied, 0.0 when tuning ran
            # but didn't beat the defaults, None when tuning was off.
            improvement_from_tuning=_applied_improvement(
                tuning_results.get(best_model.name) if tuning_results else None
            ),
            metadata={
                "n_samples": len(df),
                "n_features_original": len(X.columns),
                "n_features_engineered": len(feature_result.feature_names),
                "feature_engineering": feature_result.metadata,
                "model_comparison": model_comparison,
                "class_balance": {
                    "ratio": class_balance_ratio,
                    "balancing_applied": class_weight is not None,
                },
                "detection_result": {
                    "confidence": detection_result.confidence,
                    "reasoning": detection_result.reasoning,
                },
            },
        )

    @staticmethod
    async def _report_progress(
        progress_callback: Callable[[int, int, str | None], Awaitable[None]] | None,
        completed: int,
        total: int,
        current_algorithm: str | None,
    ) -> None:
        """Invoke the progress callback, swallowing any error it raises."""
        if progress_callback is None:
            return
        try:
            await progress_callback(completed, total, current_algorithm)
        except Exception as exc:  # progress reporting must never break training
            logger.warning(f"Progress callback failed: {exc}")

    @staticmethod
    async def _emit_event(
        event_callback: Callable[["TrainingEvent"], Awaitable[None]] | None,
        event: "TrainingEvent",
    ) -> None:
        """Invoke the event callback, swallowing any error it raises."""
        if event_callback is None:
            return
        try:
            await event_callback(event)
        except Exception as exc:  # event reporting must never break training
            logger.warning(f"Event callback failed: {exc}")

    @staticmethod
    async def _is_cancelled(
        cancel_check: Callable[[], Awaitable[bool]] | None,
    ) -> bool:
        """Await the cancellation check; errors are treated as 'not cancelled'."""
        if cancel_check is None:
            return False
        try:
            return bool(await cancel_check())
        except Exception as exc:  # a broken check must never break training
            logger.warning(f"Cancellation check failed: {exc}")
            return False

    @staticmethod
    async def _capture_evaluation_arrays(
        estimator: Any,
        X_test_transformed: pd.DataFrame,
        is_classification: bool,
    ) -> tuple[np.ndarray, np.ndarray | None, list[str] | None]:
        """Predict on the held-out set for evaluation-artifact capture.

        Returns ``(y_pred, y_proba, class_labels)``. ``class_labels`` are the
        estimator's ``classes_`` rendered as strings (original label space —
        the target is never transformed by the FeatureEngineer), in the same
        order as the columns of ``y_proba``. Probability capture is
        best-effort: ``None`` when the estimator has no ``predict_proba`` or
        the call fails.
        """
        y_pred = await asyncio.to_thread(estimator.predict, X_test_transformed)

        y_proba: np.ndarray | None = None
        class_labels: list[str] | None = None
        if is_classification:
            classes = getattr(estimator, "classes_", None)
            if classes is not None:
                class_labels = [str(c) for c in classes]
            if hasattr(estimator, "predict_proba"):
                try:
                    y_proba = await asyncio.to_thread(
                        estimator.predict_proba, X_test_transformed
                    )
                except Exception as exc:  # probabilities are optional
                    logger.warning(f"predict_proba failed during capture: {exc}")
                    y_proba = None
        return np.asarray(y_pred), y_proba, class_labels

    async def _calibrate_best_model(
        self,
        best_model: ModelCandidate,
        X_test_transformed: pd.DataFrame,
        y_test: Any,
        is_classification: bool,
    ) -> tuple[bool, str | None, float | None]:
        """Calibrate the best classifier and swap it in place (issue #83).

        Wraps ``best_model.estimator`` in a calibrated model fit on the
        held-out split so the persisted model yields calibrated probabilities,
        then mutates ``best_model.estimator`` to the wrapper. Returns
        ``(is_calibrated, calibration_method, calibration_score)``. No-op for
        regression or estimators without ``predict_proba``; best-effort — any
        failure leaves the raw model untouched.
        """
        if not is_classification or not hasattr(best_model.estimator, "predict_proba"):
            return False, None, None

        calibrated, method, score = await asyncio.to_thread(
            _confidence_service.calibrate_classifier,
            best_model.estimator,
            X_test_transformed,
            y_test,
        )
        if calibrated is None:
            return False, None, None

        best_model.estimator = calibrated
        return True, method, score

    async def _compute_global_shap(
        self,
        estimator: Any,
        X_test_transformed: pd.DataFrame,
        feature_names: list[str],
        problem_type: ProblemType,
        event_callback: Callable[["TrainingEvent"], Awaitable[None]] | None = None,
    ) -> GlobalShapResult | None:
        """Compute the best model's global SHAP summary off the event loop (#80).

        SHAP is CPU-bound, so it runs in a worker thread. Best-effort: the
        service swallows its own errors and returns ``None``; we additionally
        emit an informational event when a model type isn't SHAP-supported so
        the fallback to native importance is visible in the training logs.
        """
        result = await asyncio.to_thread(
            _interpretability_service.compute_global_shap,
            estimator,
            X_test_transformed,
            feature_names,
            problem_type.value,
        )
        if result is None:
            await self._emit_event(
                event_callback,
                TrainingEvent(
                    level="info",
                    message=(
                        "SHAP interpretability was not computed for this model "
                        "(unsupported algorithm or computation skipped); falling "
                        "back to model-native feature importance."
                    ),
                    stage="finalizing",
                ),
            )
        return result

    async def _tune_candidates(
        self,
        candidates: list[ModelCandidate],
        X_train_transformed: pd.DataFrame,
        y_train: pd.Series,
        problem_type: ProblemType,
        is_classification: bool,
        event_callback: Callable[["TrainingEvent"], Awaitable[None]] | None,
        cancel_check: Callable[[], Awaitable[bool]] | None,
    ) -> dict[str, dict[str, Any]]:
        """Tune each candidate's hyperparameters (issue #77).

        For every candidate with a tunable search space, runs the configured
        strategy on the training split (off the event loop) and records the
        serialized ``TuningResult`` (so the visualization endpoint shows every
        search). The tuned params are only *applied* to the estimator when they
        actually beat the defaults (``improvement_over_default > 0``) — tuning is
        a safety-netted improvement, never a regression. Tuning errors are
        swallowed (the candidate keeps its default hyperparameters).

        Cancellation is honoured between candidates and, for the Bayesian
        strategy, between trials via a ``cancel_event`` updated by a background
        poller (grid/random are single sklearn calls and can't be interrupted
        mid-search).
        """
        config = self.tuning_config or TuningConfig()
        # The engine owns the scoring metric for the problem type; the tuner must
        # optimize the same objective the model is later selected on.
        config = replace(config, scoring=self._get_scoring_metric(problem_type))

        results: dict[str, dict[str, Any]] = {}
        await self._emit_event(
            event_callback,
            TrainingEvent(
                level="info",
                message=f"Tuning hyperparameters ({config.strategy}) for {len(candidates)} candidates",
                stage="tuning",
            ),
        )

        # Bridge the async cancellation check to the sync tuner thread: a poller
        # task refreshes a threading.Event the optuna study stops on.
        cancel_event = Event()
        poller = (
            asyncio.create_task(self._poll_cancellation(cancel_check, cancel_event))
            if cancel_check is not None
            else None
        )
        try:
            for candidate in candidates:
                if cancel_event.is_set() or await self._is_cancelled(cancel_check):
                    raise TrainingCancelledError(
                        f"Training cancelled during tuning of {candidate.name}"
                    )
                try:
                    result: TuningResult | None = await asyncio.to_thread(
                        self._tuner.tune,
                        candidate.name,
                        candidate.estimator,
                        X_train_transformed,
                        y_train,
                        config,
                        is_classification,
                        cancel_event,
                    )
                except Exception as exc:  # tuning must never break training
                    logger.warning(f"Tuning {candidate.name} failed: {exc}")
                    result = None

                if result is None or not result.best_params:
                    continue

                applied = result.improvement_over_default > 0
                if applied:
                    try:
                        candidate.estimator.set_params(**result.best_params)
                        candidate.hyperparameters = {
                            **candidate.hyperparameters,
                            **result.best_params,
                        }
                    except Exception as exc:  # invalid params for this estimator
                        logger.warning(
                            f"Applying tuned params to {candidate.name} failed: {exc}"
                        )
                        applied = False

                payload = result.to_dict()
                payload["applied"] = applied
                results[candidate.name] = payload
                await self._emit_event(
                    event_callback,
                    TrainingEvent(
                        level="info",
                        message=(
                            f"{candidate.name} tuned ({result.strategy}): "
                            f"score {result.default_score:.4f} -> {result.best_score:.4f} "
                            f"(+{result.improvement_over_default:.4f}) over "
                            f"{result.n_trials_completed} trials"
                            f"{'' if applied else ' (kept defaults — no improvement)'}"
                        ),
                        stage="tuning",
                        candidate={
                            "algorithm": candidate.name,
                            "best_score": result.best_score,
                            "default_score": result.default_score,
                            "improvement_over_default": result.improvement_over_default,
                        },
                    ),
                )
        finally:
            if poller is not None:
                poller.cancel()
        return results

    @staticmethod
    async def _poll_cancellation(
        cancel_check: Callable[[], Awaitable[bool]] | None,
        cancel_event: Event,
        interval_seconds: float = 2.0,
    ) -> None:
        """Set ``cancel_event`` when the async cancel check first returns True.

        Runs as a background task while a tuning thread is busy so a cancellation
        can stop the Bayesian study between trials instead of waiting out the
        whole time budget. Exits once the flag is set (or on task cancel).
        """
        if cancel_check is None:
            return
        try:
            while not cancel_event.is_set():
                if await AutoMLEngine._is_cancelled(cancel_check):
                    cancel_event.set()
                    return
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _assess_class_balance(
        y_train: pd.Series, is_classification: bool
    ) -> tuple[float | None, str | None]:
        """Return (majority/minority ratio, class_weight) for the training labels.

        ``class_weight`` is ``"balanced"`` when the ratio exceeds 2:1, otherwise
        ``None``. For regression both values are ``None``.
        """
        if not is_classification:
            return None, None
        counts = y_train.value_counts()
        if len(counts) < 2 or counts.min() == 0:
            return None, None
        ratio = float(counts.max() / counts.min())
        class_weight = "balanced" if ratio > 2.0 else None
        return ratio, class_weight

    def _get_candidate_models(
        self,
        problem_type: ProblemType,
        data_shape: tuple[int, int],
        class_weight: str | None = None,
    ) -> list[ModelCandidate]:
        """Get candidate models based on problem type and data characteristics.

        ``class_weight`` (e.g. ``"balanced"``) is applied to the classifiers that
        support it — Logistic Regression, Random Forest, SVM and LightGBM — to
        provide basic class-imbalance handling. XGBoost, Gradient Boosting and KNN
        do not take a ``class_weight`` and are left unchanged.
        """
        n_samples, n_features = data_shape
        candidates = []

        if problem_type in [
            ProblemType.BINARY_CLASSIFICATION,
            ProblemType.MULTICLASS_CLASSIFICATION,
        ]:
            # Logistic Regression
            candidates.append(
                ModelCandidate(
                    name="Logistic Regression",
                    estimator=LogisticRegression(
                        random_state=self.random_state,
                        max_iter=1000,
                        class_weight=class_weight,
                    ),
                    hyperparameters={
                        "C": 1.0,
                        "penalty": "l2",
                        "class_weight": class_weight,
                    },
                )
            )

            # Random Forest
            candidates.append(
                ModelCandidate(
                    name="Random Forest",
                    estimator=RandomForestClassifier(
                        n_estimators=100,
                        random_state=self.random_state,
                        n_jobs=-1,
                        class_weight=class_weight,
                    ),
                    hyperparameters={
                        "n_estimators": 100,
                        "max_depth": None,
                        "class_weight": class_weight,
                    },
                )
            )

            # XGBoost
            candidates.append(
                ModelCandidate(
                    name="XGBoost",
                    estimator=xgb.XGBClassifier(
                        n_estimators=100,
                        random_state=self.random_state,
                        n_jobs=-1,
                        eval_metric=(
                            "logloss"
                            if problem_type == ProblemType.BINARY_CLASSIFICATION
                            else "mlogloss"
                        ),
                    ),
                    hyperparameters={"n_estimators": 100, "learning_rate": 0.1},
                )
            )

            # LightGBM
            candidates.append(
                ModelCandidate(
                    name="LightGBM",
                    estimator=lgb.LGBMClassifier(
                        n_estimators=100,
                        random_state=self.random_state,
                        n_jobs=-1,
                        verbosity=-1,
                        class_weight=class_weight,
                    ),
                    hyperparameters={
                        "n_estimators": 100,
                        "learning_rate": 0.1,
                        "class_weight": class_weight,
                    },
                )
            )

            # Gradient Boosting
            if n_samples < 10000:  # Slower for large datasets
                candidates.append(
                    ModelCandidate(
                        name="Gradient Boosting",
                        estimator=GradientBoostingClassifier(
                            n_estimators=100, random_state=self.random_state
                        ),
                        hyperparameters={"n_estimators": 100, "learning_rate": 0.1},
                    )
                )

            # SVM (for smaller datasets)
            if n_samples < 5000:
                candidates.append(
                    ModelCandidate(
                        name="SVM",
                        estimator=SVC(
                            kernel="rbf",
                            random_state=self.random_state,
                            probability=True,
                            class_weight=class_weight,
                        ),
                        hyperparameters={
                            "C": 1.0,
                            "kernel": "rbf",
                            "class_weight": class_weight,
                        },
                    )
                )

            # KNN (for smaller datasets)
            if n_samples < 10000:
                candidates.append(
                    ModelCandidate(
                        name="K-Nearest Neighbors",
                        estimator=KNeighborsClassifier(n_neighbors=5, n_jobs=-1),
                        hyperparameters={"n_neighbors": 5},
                    )
                )

        elif problem_type == ProblemType.REGRESSION:
            # Linear Regression
            candidates.append(
                ModelCandidate(
                    name="Linear Regression",
                    estimator=LinearRegression(n_jobs=-1),
                    hyperparameters={},
                )
            )

            # Ridge Regression
            candidates.append(
                ModelCandidate(
                    name="Ridge Regression",
                    estimator=Ridge(random_state=self.random_state),
                    hyperparameters={"alpha": 1.0},
                )
            )

            # Random Forest
            candidates.append(
                ModelCandidate(
                    name="Random Forest Regressor",
                    estimator=RandomForestRegressor(
                        n_estimators=100, random_state=self.random_state, n_jobs=-1
                    ),
                    hyperparameters={"n_estimators": 100},
                )
            )

            # XGBoost
            candidates.append(
                ModelCandidate(
                    name="XGBoost Regressor",
                    estimator=xgb.XGBRegressor(
                        n_estimators=100, random_state=self.random_state, n_jobs=-1
                    ),
                    hyperparameters={"n_estimators": 100, "learning_rate": 0.1},
                )
            )

            # LightGBM
            candidates.append(
                ModelCandidate(
                    name="LightGBM Regressor",
                    estimator=lgb.LGBMRegressor(
                        n_estimators=100,
                        random_state=self.random_state,
                        n_jobs=-1,
                        verbosity=-1,
                    ),
                    hyperparameters={"n_estimators": 100, "learning_rate": 0.1},
                )
            )

            # Gradient Boosting
            if n_samples < 10000:
                candidates.append(
                    ModelCandidate(
                        name="Gradient Boosting Regressor",
                        estimator=GradientBoostingRegressor(
                            n_estimators=100, random_state=self.random_state
                        ),
                        hyperparameters={"n_estimators": 100, "learning_rate": 0.1},
                    )
                )

            # SVR (for smaller datasets)
            if n_samples < 5000:
                candidates.append(
                    ModelCandidate(
                        name="Support Vector Regressor",
                        estimator=SVR(kernel="rbf"),
                        hyperparameters={"C": 1.0, "kernel": "rbf"},
                    )
                )

        return candidates

    def _get_scoring_metric(self, problem_type: ProblemType) -> str:
        """Get appropriate scoring metric for problem type"""
        if problem_type == ProblemType.BINARY_CLASSIFICATION:
            return "roc_auc"
        elif problem_type == ProblemType.MULTICLASS_CLASSIFICATION:
            return "f1_weighted"
        elif problem_type == ProblemType.REGRESSION:
            return "neg_mean_squared_error"
        else:
            return "accuracy"

    def _calculate_test_score(
        self, y_true: pd.Series, y_pred: np.ndarray, problem_type: ProblemType
    ) -> float:
        """Calculate test score based on problem type"""
        if problem_type in [
            ProblemType.BINARY_CLASSIFICATION,
            ProblemType.MULTICLASS_CLASSIFICATION,
        ]:
            return accuracy_score(y_true, y_pred)
        elif problem_type == ProblemType.REGRESSION:
            return r2_score(y_true, y_pred)
        else:
            return 0.0

    def _get_feature_importance(
        self, model: Any, feature_names: list[str]
    ) -> dict[str, float] | None:
        """Extract feature importance from model if available"""
        importance = None

        # Tree-based models
        if hasattr(model, "feature_importances_"):
            importance = model.feature_importances_
        # Linear models
        elif hasattr(model, "coef_"):
            importance = np.abs(model.coef_).flatten()
        else:
            return None

        # Create importance dictionary
        if importance is not None:
            feature_importance = {
                name: float(imp) for name, imp in zip(feature_names, importance)
            }
            # Sort by importance
            feature_importance = dict(
                sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            )
            return feature_importance

        return None
