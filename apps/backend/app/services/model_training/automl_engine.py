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
    AdaBoostClassifier,
    AdaBoostRegressor,
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import (
    ElasticNet,
    Lasso,
    LinearRegression,
    LogisticRegression,
    Ridge,
)
from sklearn.metrics import accuracy_score, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.services.confidence_service import ConfidenceService
from app.services.interpretability_service import (
    GlobalShapResult,
    InterpretabilityService,
)
from app.services.training_admission import bounded_n_jobs

from .feature_engineer import (
    FeatureEngineer,
    FeatureEngineeringConfig,
    FeatureEngineeringResult,
)
from .hyperparameter_tuner import HyperparameterTuner, TuningConfig, TuningResult
from .problem_detector import ProblemDetector, ProblemType

logger = logging.getLogger(__name__)

# Fraction of the TRAINING set reserved as a disjoint calibration slice so the
# test split stays a clean holdout for honest #79 metrics + an out-of-sample
# calibration score (issue #201). Classification only; skipped when the data is
# too small to carve the slice without degenerate (single-class/tiny) splits.
CALIBRATION_HOLDOUT_FRACTION = 0.2

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
    # Honesty of the calibration/eval split (issue #201). With the default
    # three-way classification split, the calibrator is fit on a slice carved
    # from the TRAINING set and scored on the clean held-out test set, so
    # ``calibration_score_is_insample`` is False and the #79 dashboard arrays
    # (captured on that same clean test set) are honest
    # (``evaluation_on_calibration_set`` False). When the data is too small to
    # carve a calibration slice we fall back to the old behaviour (calibrate on
    # the test split) and both flags become True to surface the optimistic bias.
    calibration_score_is_insample: bool = True
    evaluation_on_calibration_set: bool = False
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
    # Training-mode outcome (issue #101). ``early_stopped`` is True when the run
    # ended before exhausting the candidate set; ``stop_reason`` is
    # ``"time_budget_reached"`` or ``"target_score_reached"`` in that case (else
    # ``None``). ``algorithms_evaluated`` is the count of candidates that
    # *successfully* trained (failed fits are skipped and not counted), which can
    # be fewer than ``max_models`` under a budget/early stop or a candidate error.
    early_stopped: bool = False
    stop_reason: str | None = None
    algorithms_evaluated: int | None = None


def _applied_improvement(payload: dict[str, Any] | None) -> float | None:
    """The tuning gain the deployed model kept (see ``improvement_from_tuning``)."""
    if not payload:
        return None
    if payload.get("applied"):
        return payload.get("improvement_over_default")
    return 0.0


ProgressCallback = Callable[[int, int, str | None], Awaitable[None]]
EventCallback = Callable[["TrainingEvent"], Awaitable[None]]
CancelCheck = Callable[[], Awaitable[bool]]


@dataclass
class _RunHooks:
    """The three optional callbacks a run reports through."""

    progress: ProgressCallback | None
    event: EventCallback | None
    cancel_check: CancelCheck | None


@dataclass
class _TrainingData:
    """The frame as the candidates see it: split, then engineered on the training rows.

    ``X_train``/``y_fit`` is what base models fit on, ``X_test``/``y_test`` the clean
    held-out set, and ``X_cal``/``y_cal`` the calibration slice when one was carved.
    """

    X_train: pd.DataFrame
    y_fit: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    X_cal: pd.DataFrame | None
    y_cal: pd.Series | None
    feature_result: FeatureEngineeringResult
    is_classification: bool
    class_balance_ratio: float | None
    class_weight: str | None
    n_features_original: int


@dataclass
class _Deployed:
    """What was measured on the winner in the form it is deployed in."""

    feature_importance: dict[str, float] | None
    shap_global: GlobalShapResult | None
    is_calibrated: bool
    calibration_method: str | None
    calibration_score: float | None
    calibration_score_is_insample: bool
    y_pred: np.ndarray
    y_proba: np.ndarray | None
    class_labels: list[str] | None
    residual_std: float | None


def _cv_or_worst(model: "ModelCandidate") -> float:
    # cv_score is Optional; treat a missing score as worst so ordering is total.
    return model.cv_score if model.cv_score is not None else float("-inf")


def _best_and_ranked(
    trained_models: list["ModelCandidate"],
) -> tuple["ModelCandidate", list["ModelCandidate"]]:
    """The winner by CV score, and every trained candidate ranked by it."""
    if not trained_models:
        raise ValueError("No models were successfully trained")
    best_model = max(trained_models, key=_cv_or_worst)
    return best_model, sorted(trained_models, key=_cv_or_worst, reverse=True)


def _explainer_type(shap_global: GlobalShapResult | None) -> str | None:
    return shap_global.explainer_type if shap_global else None


async def _residual_std(data: _TrainingData, y_pred: np.ndarray) -> float | None:
    """Regression uncertainty: held-out residual std powers prediction intervals
    (issue #83). ``None`` for classification."""
    if data.is_classification:
        return None
    return await asyncio.to_thread(_confidence_service.residual_std, data.y_test, y_pred)


def _run_metadata(
    df: pd.DataFrame,
    data: _TrainingData,
    ranked_models: list["ModelCandidate"],
    detection_result: Any,
) -> dict[str, Any]:
    """The result's ``metadata``: sizes, the engineer's report and the comparison."""
    feature_result = data.feature_result
    return {
        "n_samples": len(df),
        "n_features_original": data.n_features_original,
        "n_features_engineered": len(feature_result.feature_names),
        "feature_engineering": feature_result.metadata,
        # Side-by-side comparison of every trained candidate, ranked by CV score.
        "model_comparison": [
            {
                "algorithm": m.name,
                "cv_score": m.cv_score,
                "test_score": m.test_score,
                "training_time": m.training_time,
            }
            for m in ranked_models
        ],
        "class_balance": {
            "ratio": data.class_balance_ratio,
            "balancing_applied": data.class_weight is not None,
        },
        "detection_result": {
            "confidence": detection_result.confidence,
            "reasoning": detection_result.reasoning,
        },
    }


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
        early_stop_score: float | None = None,
        n_jobs: int | None = None,
    ):
        self.max_models = max_models
        self.time_limit = time_limit
        self.cv_folds = cv_folds
        self.test_size = test_size
        self.random_state = random_state
        # Bound estimator parallelism so one training cannot claim the whole
        # shared VPS (#498); None/-1 resolve to the configured host cap.
        self.n_jobs = bounded_n_jobs(n_jobs)
        # Training-mode controls (issue #101). ``time_limit`` (a wall-clock cap in
        # seconds) and ``early_stop_score`` (stop once a candidate's CV score
        # clears this bar) are enforced in the candidate loop. Both default to
        # ``None`` so pre-#101 callers train the full candidate set as before.
        self.early_stop_score = early_stop_score
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
        progress_callback: ProgressCallback | None = None,
        event_callback: EventCallback | None = None,
        cancel_check: CancelCheck | None = None,
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
        hooks = _RunHooks(progress_callback, event_callback, cancel_check)

        await self._say(hooks, "Preparing data and engineering features", "preprocessing")
        detection_result = await self.problem_detector.detect_problem_type(
            df, target_column
        )
        problem_type = detection_result.problem_type
        logger.info(f"Detected problem type: {problem_type.value}")

        data = await self._prepare_data(df, target_column, problem_type, feature_config, hooks)
        candidates = self._get_candidate_models(
            problem_type, data.X_train.shape, class_weight=data.class_weight
        )
        selected_candidates = candidates[: self.max_models]
        total_candidates = len(selected_candidates)

        tuning_results = await self._tuning_results(selected_candidates, data, problem_type, hooks)
        await self._say(hooks, f"Training {total_candidates} candidate models", "training")
        trained_models, stop_reason = await self._train_candidates(
            selected_candidates, data, problem_type, start_time, hooks
        )

        # Final cancellation check: a cancel that arrived while the last
        # candidate was fitting would otherwise be acknowledged by the API
        # but silently ignored, completing the job anyway.
        if await self._is_cancelled(hooks.cancel_check):
            raise TrainingCancelledError("Training cancelled before finalization")

        # Final progress tick: all candidates processed.
        await self._report_progress(
            hooks.progress, total_candidates, total_candidates, None
        )
        await self._say(hooks, "Selecting the best model", "finalizing")
        best_model, ranked_models = _best_and_ranked(trained_models)
        deployed = await self._deploy_best(best_model, data, problem_type, hooks)

        total_time = (datetime.now(UTC) - start_time).total_seconds()
        await self._say(
            hooks,
            (
                f"Training complete: best model is {best_model.name} "
                f"(cv_score={best_model.cv_score:.4f}, "
                f"test_score={best_model.test_score:.4f}) "
                f"after {total_time:.2f}s"
            ),
            "finalizing",
        )

        return AutoMLResult(
            best_model=best_model,
            all_models=ranked_models,
            problem_type=problem_type,
            feature_names=data.feature_result.feature_names,
            feature_importance=deployed.feature_importance,
            training_time=total_time,
            y_test=np.asarray(data.y_test),
            y_pred=deployed.y_pred,
            y_proba=deployed.y_proba,
            class_labels=deployed.class_labels,
            x_test=np.asarray(data.X_test),
            is_calibrated=deployed.is_calibrated,
            calibration_method=deployed.calibration_method,
            calibration_score=deployed.calibration_score,
            calibration_score_is_insample=deployed.calibration_score_is_insample,
            # The #79 dashboard arrays are honest unless we fell back to fitting the
            # calibrator on the test set (then they describe the calibrator's own
            # fit data and are optimistic — issue #201).
            evaluation_on_calibration_set=(
                deployed.is_calibrated and deployed.calibration_score_is_insample
            ),
            residual_std=deployed.residual_std,
            shap_global=deployed.shap_global,
            shap_explainer_type=_explainer_type(deployed.shap_global),
            early_stopped=stop_reason is not None,
            stop_reason=stop_reason,
            algorithms_evaluated=len(trained_models),
            metadata=_run_metadata(df, data, ranked_models, detection_result),
            **self._tuning_summary(tuning_results, best_model.name),
        )

    async def _say(self, hooks: "_RunHooks", message: str, stage: str) -> None:
        """Emit one info-level pipeline event."""
        await self._emit_event(
            hooks.event, TrainingEvent(level="info", message=message, stage=stage)
        )

    async def _prepare_data(
        self,
        df: pd.DataFrame,
        target_column: str,
        problem_type: ProblemType,
        feature_config: FeatureEngineeringConfig | None,
        hooks: "_RunHooks",
    ) -> "_TrainingData":
        """Split the frame and engineer its features, fitted on the training rows only."""
        X = df.drop(columns=[target_column])
        y = df[target_column]

        is_classification = problem_type in [
            ProblemType.BINARY_CLASSIFICATION,
            ProblemType.MULTICLASS_CLASSIFICATION,
        ]

        # Split data. ``X_test``/``y_test`` is the clean held-out set used for
        # candidate test scores, the #79 dashboard arrays, and the out-of-sample
        # calibration score (issue #201) — nothing is ever fit on it.
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=y if is_classification else None,
        )
        X_fit, X_cal, y_fit, y_cal = self._calibration_carve(
            X_train, y_train, is_classification
        )

        # Detect class imbalance and enable basic handling (class weighting).
        # This is the lightweight "basic class-imbalance handling" of the beta
        # scope: no resampling (SMOTE etc.), just class_weight="balanced" on the
        # estimators that support it.
        class_balance_ratio, class_weight = self._assess_class_balance(
            y_fit, is_classification
        )

        # Feature engineering — fit on the base-model training data only.
        if feature_config:
            self.feature_engineer.config = feature_config

        feature_result = await self.feature_engineer.fit_transform(
            X_fit, y_fit, problem_type.value
        )
        # Identifiers (#806) and dates (#840) the engineer left out of the features.
        for note in self.feature_engineer.exclusion_notes():
            await self._say(hooks, note, "preprocessing")

        # Transform the clean test set and (when carved) the calibration slice.
        X_test_transformed = await self.feature_engineer.transform(X_test)
        X_cal_transformed = await self._calibration_slice_transformed(X_cal)

        return _TrainingData(
            X_train=feature_result.X_transformed,
            y_fit=y_fit,
            X_test=X_test_transformed,
            y_test=y_test,
            X_cal=X_cal_transformed,
            y_cal=y_cal,
            feature_result=feature_result,
            is_classification=is_classification,
            class_balance_ratio=class_balance_ratio,
            class_weight=class_weight,
            n_features_original=len(X.columns),
        )

    def _calibration_carve(
        self, X_train: pd.DataFrame, y_train: pd.Series, is_classification: bool
    ) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.Series, pd.Series | None]:
        """``(X_fit, X_cal, y_fit, y_cal)``: the honest calibration split (issue #201).

        For classification, carve a disjoint calibration slice from the TRAINING
        set so the calibrator is never fit on the test set. Base models train on
        ``X_fit`` only; ``X_cal`` calibrates the best model later. When the data is
        too small to carve cleanly we fall back to fitting on the full training set
        and calibrating on the test split (the pre-#201 in-sample behaviour).
        """
        if not (is_classification and self._can_carve_calibration(y_train)):
            return X_train, None, y_train, None
        X_fit, X_cal, y_fit, y_cal = train_test_split(
            X_train,
            y_train,
            test_size=CALIBRATION_HOLDOUT_FRACTION,
            random_state=self.random_state,
            stratify=y_train,
        )
        return X_fit, X_cal, y_fit, y_cal

    async def _calibration_slice_transformed(
        self, X_cal: pd.DataFrame | None
    ) -> pd.DataFrame | None:
        """The calibration slice through the fitted engineer, best-effort.

        If X_cal trips the feature engineer (e.g. a categorical value unseen in
        X_fit), drop the carve and let calibration fall back to the test set rather
        than failing the whole run (issue #201). Base models stay trained on X_fit.
        """
        if X_cal is None:
            return None
        try:
            return await self.feature_engineer.transform(X_cal)
        except Exception as exc:  # noqa: BLE001 - never fail training on the carve
            logger.warning(
                "Calibration-slice transform failed, skipping carve: %s", exc
            )
            return None

    async def _tuning_results(
        self,
        candidates: list[ModelCandidate],
        data: "_TrainingData",
        problem_type: ProblemType,
        hooks: "_RunHooks",
    ) -> dict[str, dict[str, Any]]:
        """Optional hyperparameter tuning (issue #77); empty when tuning is off.

        Runs before the training loop so the best params are applied to each
        candidate's estimator and then fitted/CV'd normally. Best-effort: a
        candidate that can't be tuned simply keeps its default hyperparameters.
        """
        if not self.enable_tuning:
            return {}
        return await self._tune_candidates(
            candidates,
            data.X_train,
            data.y_fit,
            problem_type,
            data.is_classification,
            hooks.event,
            hooks.cancel_check,
        )

    def _tuning_summary(
        self, tuning_results: dict[str, dict[str, Any]], best_name: str
    ) -> dict[str, Any]:
        """The result's three tuning fields. All ``None`` when tuning was off."""
        strategy = None
        if self.enable_tuning:
            strategy = (self.tuning_config or TuningConfig()).strategy
        return {
            "tuning_results": tuning_results or None,
            "tuning_strategy": strategy,
            # Gain the deployed best model actually got from tuning: its recorded
            # improvement when the tuned params were applied, 0.0 when tuning ran
            # but didn't beat the defaults, None when tuning was off.
            "improvement_from_tuning": _applied_improvement(tuning_results.get(best_name)),
        }

    async def _train_candidates(
        self,
        candidates: list[ModelCandidate],
        data: "_TrainingData",
        problem_type: ProblemType,
        start_time: datetime,
        hooks: "_RunHooks",
    ) -> tuple[list[ModelCandidate], str | None]:
        """Fit and score each candidate in turn: ``(trained, stop_reason)``.

        ``stop_reason`` (issue #101) is set when the time budget is exhausted or a
        candidate clears ``early_stop_score``; surfaced on the result so the
        UI/audit can explain why fewer than all candidates ran.
        """
        trained_models: list[ModelCandidate] = []
        stop_reason: str | None = None

        for index, candidate in enumerate(candidates):
            if await self._is_cancelled(hooks.cancel_check):
                raise TrainingCancelledError(
                    f"Training cancelled before {candidate.name}"
                )
            stop_reason = await self._time_budget_stop(start_time, trained_models, hooks)
            if stop_reason:
                break

            logger.info(f"Training {candidate.name}...")
            await self._report_progress(
                hooks.progress, index, len(candidates), candidate.name
            )
            stop_reason = await self._train_one(
                candidate, trained_models, data, problem_type, hooks
            )
            if stop_reason:
                break

        return trained_models, stop_reason

    async def _time_budget_stop(
        self,
        start_time: datetime,
        trained_models: list[ModelCandidate],
        hooks: "_RunHooks",
    ) -> str | None:
        """Time-budget enforcement (issue #101, AC4): the stop reason, or None.

        Checked between candidates so we never interrupt an in-progress fit; we
        only stop once at least one model has trained so a too-tight budget still
        yields a usable result.
        """
        if not (self.time_limit and trained_models):
            return None
        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        if elapsed < self.time_limit:
            return None
        await self._say(
            hooks,
            (
                f"Time budget ({self.time_limit}s) reached after "
                f"{len(trained_models)} models — stopping early"
            ),
            "training",
        )
        return "time_budget_reached"

    async def _train_one(
        self,
        candidate: ModelCandidate,
        trained_models: list[ModelCandidate],
        data: "_TrainingData",
        problem_type: ProblemType,
        hooks: "_RunHooks",
    ) -> str | None:
        """Train one candidate and add it to ``trained_models``.

        Returns the stop reason when it cleared the target score. A candidate that
        fails to train is reported and skipped, never fatal.
        """
        try:
            await self._fit_and_score(candidate, data, problem_type)
            trained_models.append(candidate)
            logger.info(
                f"{candidate.name} - CV Score: {candidate.cv_score:.4f}, Test Score: {candidate.test_score:.4f}"
            )
            await self._emit_event(
                hooks.event,
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
            return await self._target_score_stop(candidate, hooks)
        except Exception as e:
            logger.error(f"Error training {candidate.name}: {str(e)}")
            await self._emit_event(
                hooks.event,
                TrainingEvent(
                    level="warning",
                    message=f"{candidate.name} failed to train: {e}",
                    stage="training",
                ),
            )
            return None

    async def _fit_and_score(
        self, candidate: ModelCandidate, data: "_TrainingData", problem_type: ProblemType
    ) -> None:
        """Fit the candidate, then record its training time, CV score and test score.

        The fit/CV/predict calls are CPU-bound and run in a worker thread: executed
        inline they block the event loop for the whole fit, freezing every API
        request — including the status polls and the cancel endpoint this feature
        depends on.
        """
        model_start = datetime.now(UTC)
        await asyncio.to_thread(candidate.estimator.fit, data.X_train, data.y_fit)
        candidate.training_time = (datetime.now(UTC) - model_start).total_seconds()

        cv_scores = await asyncio.to_thread(
            cross_val_score,
            candidate.estimator,
            data.X_train,
            data.y_fit,
            cv=self.cv_folds,
            scoring=self._get_scoring_metric(problem_type),
        )
        candidate.cv_score = np.mean(cv_scores)

        y_pred = await asyncio.to_thread(candidate.estimator.predict, data.X_test)
        candidate.test_score = self._calculate_test_score(
            data.y_test, y_pred, problem_type
        )

    def _cleared_target_score(self, candidate: ModelCandidate) -> bool:
        if self.early_stop_score is None or candidate.cv_score is None:
            return False
        return candidate.cv_score >= self.early_stop_score

    async def _target_score_stop(
        self, candidate: ModelCandidate, hooks: "_RunHooks"
    ) -> str | None:
        """Early stopping on a good result (issue #101, AC4): the stop reason, or None.

        Quick mode sets ``early_stop_score`` so a clearly-good candidate ends the
        search; Comprehensive leaves it ``None`` to stay thorough.
        """
        if not self._cleared_target_score(candidate):
            return None
        await self._say(
            hooks,
            (
                f"{candidate.name} reached the target score "
                f"({candidate.cv_score:.4f} >= "
                f"{self.early_stop_score:.2f}) — stopping early"
            ),
            "training",
        )
        return "target_score_reached"

    async def _deploy_best(
        self,
        best_model: ModelCandidate,
        data: "_TrainingData",
        problem_type: ProblemType,
        hooks: "_RunHooks",
    ) -> "_Deployed":
        """Explain, calibrate and evaluate the winner as it will be deployed."""
        feature_names = data.feature_result.feature_names
        # Get feature importance if available. Extracted from the RAW estimator
        # *before* calibration, because the calibrated wrapper hides
        # ``feature_importances_`` / ``coef_``.
        feature_importance = self._get_feature_importance(
            best_model.estimator, feature_names
        )

        # SHAP global summary (issue #80). Computed on the held-out set from the
        # RAW estimator *before* calibration, for the same reason as
        # feature_importance: the calibrated wrapper hides the tree/linear
        # internals SHAP introspects. Best-effort — unsupported models and any
        # SHAP failure simply leave ``shap_global`` as ``None`` and the system
        # falls back to model-native importance.
        shap_global = await self._compute_global_shap(
            best_model.estimator, data.X_test, feature_names, problem_type, hooks.event
        )

        # SHAP can take noticeable time on tree/linear models, so honour a
        # cancellation requested while it ran before doing the remaining
        # finalization work (calibration + persistence).
        if await self._is_cancelled(hooks.cancel_check):
            raise TrainingCancelledError("Training cancelled during finalization")

        # Confidence calibration for issue #83 — classification only. The best
        # estimator is swapped in place for its calibrated wrapper so the
        # *deployed* model yields calibrated probabilities. Best-effort: a
        # failure leaves the raw model untouched. Issue #201: when a calibration
        # slice was carved (``data.X_cal`` present), calibrate on it and
        # score out-of-sample on the clean test set; otherwise calibrate on the
        # test set and report the score as in-sample.
        (
            is_calibrated,
            calibration_method,
            calibration_score,
            calibration_score_is_insample,
        ) = await self._calibrate_best_model(
            best_model,
            data.X_cal,
            data.y_cal,
            data.X_test,
            data.y_test,
            data.is_classification,
        )

        # Capture the (now possibly calibrated) best model's held-out evaluation
        # artifacts (issue #79) AFTER calibration so the dashboard metrics
        # describe exactly the model that gets deployed. With the #201 honest
        # split this test set was seen by neither the base model nor the
        # calibrator, so the metrics are unbiased.
        y_pred, y_proba, class_labels = await self._capture_evaluation_arrays(
            best_model.estimator, data.X_test, data.is_classification
        )

        # Calibration can shift held-out predictions, so recompute the best
        # model's test score from the deployed model's predictions — otherwise
        # the persisted `test_score` / model-comparison row would describe the
        # pre-calibration estimator (issue #83 review fix).
        if is_calibrated:
            best_model.test_score = self._calculate_test_score(
                data.y_test, y_pred, problem_type
            )

        return _Deployed(
            feature_importance=feature_importance,
            shap_global=shap_global,
            is_calibrated=is_calibrated,
            calibration_method=calibration_method,
            calibration_score=calibration_score,
            calibration_score_is_insample=calibration_score_is_insample,
            y_pred=y_pred,
            y_proba=y_proba,
            class_labels=class_labels,
            residual_std=await _residual_std(data, y_pred),
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

    def _can_carve_calibration(self, y_train: pd.Series) -> bool:
        """Whether a disjoint calibration slice can be carved from the train set.

        Stratified ``train_test_split`` needs >=2 members of every class on both
        sides, so we require the calibration slice to hold at least 2 rows per
        class. The carve must also leave enough of every class in the fit set
        for ``cv_folds``-fold cross-validation — otherwise a fold can end up
        with no members of a class and ``cross_val_score`` returns NaN (codex
        review). Too-small/too-imbalanced data returns False and we keep the
        pre-#201 single-split behaviour (issue #201).
        """
        counts = y_train.value_counts()
        n_classes = len(counts)
        n_cal = int(len(y_train) * CALIBRATION_HOLDOUT_FRACTION)
        # Conservative lower bound on each class's count remaining in the fit set
        # after a stratified carve (the split keeps at least this many).
        min_fit_per_class = int(counts.min() * (1 - CALIBRATION_HOLDOUT_FRACTION))
        return (
            n_classes >= 2
            and counts.min() >= 2
            and n_cal >= 2 * n_classes
            and min_fit_per_class >= self.cv_folds
            and (len(y_train) - n_cal) >= n_classes
        )

    async def _calibrate_best_model(
        self,
        best_model: ModelCandidate,
        X_cal_transformed: pd.DataFrame | None,
        y_cal: Any,
        X_test_transformed: pd.DataFrame,
        y_test: Any,
        is_classification: bool,
    ) -> tuple[bool, str | None, float | None, bool]:
        """Calibrate the best classifier and swap it in place (issue #83/#201).

        Wraps ``best_model.estimator`` in a calibrated model and mutates
        ``best_model.estimator`` to the wrapper so the persisted model yields
        calibrated probabilities. Returns ``(is_calibrated,
        calibration_method, calibration_score, score_is_insample)``.

        When a disjoint calibration slice is available (``X_cal_transformed``),
        the calibrator is fit on it and scored on the clean test set —
        ``score_is_insample`` is False (issue #201). Otherwise it falls back to
        fitting on the test set (pre-#201 behaviour) and the score is in-sample.
        No-op for regression or estimators without ``predict_proba``;
        best-effort — any failure leaves the raw model untouched.
        """
        if not is_classification or not hasattr(best_model.estimator, "predict_proba"):
            return False, None, None, True

        # Honest path: fit on the carved slice, score out-of-sample on the clean
        # test set. The carved slice can still be degenerate for very imbalanced
        # data (a stratified 20% split of e.g. 18/2 can land all-majority in the
        # slice), so a None result here falls through to the test-set fallback
        # below rather than dropping calibration the deployed model had pre-#201.
        if X_cal_transformed is not None:
            calibrated, method, score = await asyncio.to_thread(
                _confidence_service.calibrate_classifier,
                best_model.estimator,
                X_cal_transformed,
                y_cal,
                X_score=X_test_transformed,
                y_score=y_test,
            )
            if calibrated is not None:
                best_model.estimator = calibrated
                return True, method, score, False

        # Fallback (no slice carved, or the carved slice was degenerate): fit +
        # score on the test split. The score is in-sample (optimistic).
        calibrated, method, score = await asyncio.to_thread(
            _confidence_service.calibrate_classifier,
            best_model.estimator,
            X_test_transformed,
            y_test,
        )
        if calibrated is None:
            return False, None, None, True

        best_model.estimator = calibrated
        return True, method, score, True

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
                        n_jobs=self.n_jobs,
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
                        n_jobs=self.n_jobs,
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
                        n_jobs=self.n_jobs,
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

            # Extra Trees, AdaBoost, Decision Tree, Naive Bayes (issue #101).
            # Always-on, fast classifiers that broaden Comprehensive mode to 10+
            # algorithms. Appended after the top candidates so Quick mode (which
            # takes the first ``max_models``) is unaffected.
            candidates.append(
                ModelCandidate(
                    name="Extra Trees",
                    estimator=ExtraTreesClassifier(
                        n_estimators=100,
                        random_state=self.random_state,
                        n_jobs=self.n_jobs,
                        class_weight=class_weight,
                    ),
                    hyperparameters={"n_estimators": 100, "class_weight": class_weight},
                )
            )
            candidates.append(
                ModelCandidate(
                    name="AdaBoost",
                    estimator=AdaBoostClassifier(
                        n_estimators=100, random_state=self.random_state
                    ),
                    hyperparameters={"n_estimators": 100, "learning_rate": 1.0},
                )
            )
            candidates.append(
                ModelCandidate(
                    name="Decision Tree",
                    estimator=DecisionTreeClassifier(
                        random_state=self.random_state, class_weight=class_weight
                    ),
                    hyperparameters={"max_depth": None, "class_weight": class_weight},
                )
            )
            candidates.append(
                ModelCandidate(
                    name="Naive Bayes",
                    estimator=GaussianNB(),
                    hyperparameters={},
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
                        estimator=KNeighborsClassifier(n_neighbors=5, n_jobs=self.n_jobs),
                        hyperparameters={"n_neighbors": 5},
                    )
                )

        elif problem_type == ProblemType.REGRESSION:
            # Linear Regression
            candidates.append(
                ModelCandidate(
                    name="Linear Regression",
                    estimator=LinearRegression(n_jobs=self.n_jobs),
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
                        n_estimators=100, random_state=self.random_state, n_jobs=self.n_jobs
                    ),
                    hyperparameters={"n_estimators": 100},
                )
            )

            # XGBoost
            candidates.append(
                ModelCandidate(
                    name="XGBoost Regressor",
                    estimator=xgb.XGBRegressor(
                        n_estimators=100, random_state=self.random_state, n_jobs=self.n_jobs
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
                        n_jobs=self.n_jobs,
                        verbosity=-1,
                    ),
                    hyperparameters={"n_estimators": 100, "learning_rate": 0.1},
                )
            )

            # Extra Trees, AdaBoost, Decision Tree, Lasso, ElasticNet (issue #101).
            # Always-on regressors that broaden Comprehensive mode to 10+
            # algorithms. Appended after the top candidates so Quick mode is
            # unaffected.
            candidates.append(
                ModelCandidate(
                    name="Extra Trees Regressor",
                    estimator=ExtraTreesRegressor(
                        n_estimators=100, random_state=self.random_state, n_jobs=self.n_jobs
                    ),
                    hyperparameters={"n_estimators": 100},
                )
            )
            candidates.append(
                ModelCandidate(
                    name="AdaBoost Regressor",
                    estimator=AdaBoostRegressor(
                        n_estimators=100, random_state=self.random_state
                    ),
                    hyperparameters={"n_estimators": 100, "learning_rate": 1.0},
                )
            )
            candidates.append(
                ModelCandidate(
                    name="Decision Tree Regressor",
                    estimator=DecisionTreeRegressor(random_state=self.random_state),
                    hyperparameters={"max_depth": None},
                )
            )
            candidates.append(
                ModelCandidate(
                    name="Lasso Regression",
                    estimator=Lasso(random_state=self.random_state),
                    hyperparameters={"alpha": 1.0},
                )
            )
            candidates.append(
                ModelCandidate(
                    name="ElasticNet Regression",
                    estimator=ElasticNet(random_state=self.random_state),
                    hyperparameters={"alpha": 1.0, "l1_ratio": 0.5},
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
