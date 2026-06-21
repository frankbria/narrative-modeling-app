"""
Hyperparameter tuning for the AutoML engine (issue #77).

A single stateless :class:`HyperparameterTuner` supports three strategies — grid
search and random search (scikit-learn) and Bayesian optimization (optuna) — over
algorithm-specific, data-driven search spaces. It is an *optional* stage of the
AutoML pipeline: when enabled, the best parameters found are applied to the
candidate estimator before final training.

Design notes:
- ``tune()`` is synchronous and CPU-bound; the engine runs it in a worker thread
  (``asyncio.to_thread``) so it never blocks the event loop.
- It **never raises** on a tuning failure — it returns ``None`` so the pipeline
  falls back to the algorithm's default hyperparameters (same resilience contract
  as the SHAP / calibration stages). An invalid *config* (unknown strategy) is a
  programming error and does raise ``ValueError``.
- ``optuna`` is imported lazily inside the Bayesian path so the package can be a
  removable optional dependency (mirrors the shap lever from #204); when it is
  absent the Bayesian strategy degrades to random search.

Visualization data (parameter importance, optimization history, improvement over
default) is carried *inline* on :class:`TuningResult` rather than in a separate
module — it is data, not plots, and the frontend renders it from the API.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.metrics import get_scorer
from sklearn.model_selection import (
    GridSearchCV,
    KFold,
    RandomizedSearchCV,
    StratifiedKFold,
    cross_val_score,
)

logger = logging.getLogger(__name__)

VALID_STRATEGIES = ("grid", "random", "bayesian")


@dataclass
class ParamSpec:
    """One tunable hyperparameter's search range.

    ``kind`` is ``"categorical"`` (use ``choices``), ``"int"`` or ``"float"``
    (use ``low``/``high``). ``log`` samples on a log scale for int/float.
    """

    kind: str
    low: float | None = None
    high: float | None = None
    log: bool = False
    choices: list[Any] | None = None


@dataclass
class TuningConfig:
    """Configuration for a tuning run.

    ``scoring`` defaults to ``None`` and is filled in by the engine with the
    problem-type metric (e.g. ``"roc_auc"``). ``time_budget`` (seconds) is hard-
    enforced only for the Bayesian strategy (optuna ``timeout``); grid/random
    honour ``n_trials`` + ``n_jobs`` but treat the budget as best-effort.
    """

    strategy: str = "bayesian"
    time_budget: int = 600
    n_trials: int = 30
    cv_folds: int = 3
    scoring: str | None = None
    n_jobs: int = -1
    random_state: int = 42

    def __post_init__(self) -> None:
        if self.strategy not in VALID_STRATEGIES:
            raise ValueError(
                f"Unknown tuning strategy {self.strategy!r}; "
                f"expected one of {VALID_STRATEGIES}"
            )


@dataclass
class TrialResult:
    """One evaluated parameter set."""

    trial_number: int
    params: dict[str, Any]
    score: float


@dataclass
class TuningResult:
    """Outcome of tuning one algorithm, including inline visualization data."""

    algorithm: str
    strategy: str  # the strategy actually used (may differ if bayesian degraded)
    best_params: dict[str, Any]
    best_score: float
    default_score: float
    improvement_over_default: float
    n_trials_completed: int
    total_time: float
    # Visualization payloads (AC: "parameter importance, optimization history,
    # improvement vs default"). ``parameter_importance`` is only populated for
    # the Bayesian strategy (optuna); ``None`` for grid/random.
    parameter_importance: dict[str, float] | None = None
    optimization_history: list[dict[str, Any]] = field(default_factory=list)
    all_trials: list[TrialResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-/Mongo-safe serialization (no numpy scalars)."""
        return {
            "algorithm": self.algorithm,
            "strategy": self.strategy,
            "best_params": _py(self.best_params),
            "best_score": float(self.best_score),
            "default_score": float(self.default_score),
            "improvement_over_default": float(self.improvement_over_default),
            "n_trials_completed": int(self.n_trials_completed),
            "total_time": float(self.total_time),
            "parameter_importance": (
                {k: float(v) for k, v in self.parameter_importance.items()}
                if self.parameter_importance is not None
                else None
            ),
            "optimization_history": [_py(h) for h in self.optimization_history],
            "all_trials": [
                {"trial_number": int(t.trial_number), "params": _py(t.params), "score": float(t.score)}
                for t in self.all_trials
            ],
        }


def _py(value: Any) -> Any:
    """Recursively convert numpy scalars/containers to native Python types."""
    if isinstance(value, dict):
        return {k: _py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_py(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _canonical_algorithm(name: str) -> str | None:
    """Map an engine candidate name (e.g. "XGBoost Regressor") to a space key."""
    n = name.lower()
    if "logistic" in n:
        return "logistic_regression"
    if "ridge" in n:
        return "ridge"
    if "linear regression" in n:
        return None  # no meaningful hyperparameters to tune
    if "random forest" in n:
        return "random_forest"
    if "xgboost" in n:
        return "xgboost"
    if "lightgbm" in n:
        return "lightgbm"
    if "gradient boosting" in n:
        return "gradient_boosting"
    if "vector" in n or n == "svm":  # SVM / Support Vector Regressor
        return "svm"
    if "neighbor" in n:
        return "knn"
    return None


# Base (un-adapted) search spaces. Penalty/solver coupling for logistic regression
# and kernel choice for SVM are deliberately NOT tuned — invalid combinations are a
# common source of fit errors; tuning the continuous knobs (C, gamma) is the high-
# value, low-risk subset. ponytail: coarse-but-correct beats exhaustive-but-fragile.
_BASE_SPACES: dict[str, dict[str, ParamSpec]] = {
    "logistic_regression": {
        "C": ParamSpec("float", 0.01, 100.0, log=True),
    },
    "ridge": {
        "alpha": ParamSpec("float", 0.01, 100.0, log=True),
    },
    "random_forest": {
        "n_estimators": ParamSpec("int", 50, 300),
        "max_depth": ParamSpec("int", 3, 30),
        "min_samples_split": ParamSpec("int", 2, 20),
        "max_features": ParamSpec("categorical", choices=["sqrt", "log2", None]),
    },
    "gradient_boosting": {
        "n_estimators": ParamSpec("int", 50, 300),
        "learning_rate": ParamSpec("float", 0.01, 0.3, log=True),
        "max_depth": ParamSpec("int", 2, 8),
    },
    "xgboost": {
        "n_estimators": ParamSpec("int", 50, 400),
        "learning_rate": ParamSpec("float", 0.01, 0.3, log=True),
        "max_depth": ParamSpec("int", 3, 10),
        "subsample": ParamSpec("float", 0.6, 1.0),
        "colsample_bytree": ParamSpec("float", 0.6, 1.0),
    },
    "lightgbm": {
        "n_estimators": ParamSpec("int", 50, 400),
        "learning_rate": ParamSpec("float", 0.01, 0.3, log=True),
        "num_leaves": ParamSpec("int", 20, 150),
        "max_depth": ParamSpec("int", 3, 12),
    },
    "svm": {
        "C": ParamSpec("float", 0.1, 100.0, log=True),
        "gamma": ParamSpec("categorical", choices=["scale", "auto"]),
    },
    "knn": {
        "n_neighbors": ParamSpec("int", 3, 25),
        "weights": ParamSpec("categorical", choices=["uniform", "distance"]),
        "p": ParamSpec("categorical", choices=[1, 2]),
    },
}


class HyperparameterTuner:
    """Stateless tuner. One instance can tune any number of candidates."""

    def get_search_space(
        self,
        algorithm: str,
        n_samples: int | None = None,
        n_features: int | None = None,
    ) -> dict[str, ParamSpec]:
        """Return the data-driven search space for ``algorithm`` (``{}`` if none).

        Ranges are adapted to the data shape: large datasets get smaller tree
        sizes/depths (speed + diminishing returns) and high-dimensional data gets
        shallower trees (overfitting control).
        """
        key = _canonical_algorithm(algorithm)
        if key is None or key not in _BASE_SPACES:
            return {}
        # Copy so adaptation never mutates the module-level base spaces.
        space = {name: ParamSpec(**asdict(spec)) for name, spec in _BASE_SPACES[key].items()}
        self._adapt(space, n_samples, n_features)
        return space

    @staticmethod
    def _adapt(
        space: dict[str, ParamSpec], n_samples: int | None, n_features: int | None
    ) -> None:
        """Shrink tree-size/depth ranges in place for large / wide datasets."""
        if n_samples is not None and n_samples > 10000:
            if "n_estimators" in space and space["n_estimators"].high:
                space["n_estimators"].high = min(space["n_estimators"].high, 200)
            if "max_depth" in space and space["max_depth"].high:
                space["max_depth"].high = min(space["max_depth"].high, 15)
        if n_samples is not None and n_samples < 200:
            # Tiny data: keep ensembles small to fit fast and avoid overfitting.
            if "n_estimators" in space and space["n_estimators"].high:
                space["n_estimators"].high = min(space["n_estimators"].high, 150)
        if n_features is not None and n_features > 100:
            if "max_depth" in space and space["max_depth"].high:
                space["max_depth"].high = min(space["max_depth"].high, 12)

    def tune(
        self,
        algorithm: str,
        estimator: Any,
        X: Any,
        y: Any,
        config: TuningConfig,
        is_classification: bool,
    ) -> TuningResult | None:
        """Tune ``estimator`` for ``algorithm`` and return the best params + viz.

        Returns ``None`` when the algorithm has no search space or tuning fails —
        the caller keeps the estimator's default hyperparameters.
        """
        space = self.get_search_space(
            algorithm,
            n_samples=_n_rows(X),
            n_features=_n_cols(X),
        )
        if not space:
            return None

        scoring = config.scoring or ("roc_auc" if is_classification else "r2")
        start = _now()
        try:
            default_score = float(
                np.mean(
                    cross_val_score(
                        clone(estimator), X, y, cv=config.cv_folds, scoring=scoring
                    )
                )
            )
        except Exception as exc:  # a broken baseline must not break the pipeline
            logger.warning(f"Default-score CV failed for {algorithm}: {exc}")
            return None

        try:
            strategy = config.strategy
            if strategy == "grid":
                best_params, best_score, trials, importance = self._tune_grid(
                    estimator, X, y, space, config, scoring
                )
            elif strategy == "random":
                best_params, best_score, trials, importance = self._tune_random(
                    estimator, X, y, space, config, scoring
                )
            else:  # bayesian (may degrade to random if optuna is missing)
                result = self._tune_bayesian(
                    estimator, X, y, space, config, scoring, is_classification
                )
                if result is None:
                    strategy = "random"
                    best_params, best_score, trials, importance = self._tune_random(
                        estimator, X, y, space, config, scoring
                    )
                else:
                    best_params, best_score, trials, importance = result
        except Exception as exc:  # never raise into the training pipeline
            logger.warning(f"Hyperparameter tuning failed for {algorithm}: {exc}")
            return None

        return TuningResult(
            algorithm=algorithm,
            strategy=strategy,
            best_params=_py(best_params),
            best_score=best_score,
            default_score=default_score,
            improvement_over_default=best_score - default_score,
            n_trials_completed=len(trials),
            total_time=_now() - start,
            parameter_importance=importance,
            optimization_history=_history(trials),
            all_trials=trials,
        )

    # -- strategy implementations ------------------------------------------------

    def _tune_grid(
        self, estimator, X, y, space, config, scoring
    ) -> tuple[dict, float, list[TrialResult], None]:
        param_grid = {name: _grid_values(spec) for name, spec in space.items()}
        search = GridSearchCV(
            clone(estimator),
            param_grid,
            cv=config.cv_folds,
            scoring=scoring,
            n_jobs=config.n_jobs,
            error_score=np.nan,
        )
        search.fit(X, y)
        return (
            dict(search.best_params_),
            float(search.best_score_),
            _trials_from_cv_results(search.cv_results_),
            None,  # sklearn search gives no parameter importance
        )

    def _tune_random(
        self, estimator, X, y, space, config, scoring
    ) -> tuple[dict, float, list[TrialResult], None]:
        param_dist = {name: _random_values(spec) for name, spec in space.items()}
        search = RandomizedSearchCV(
            clone(estimator),
            param_dist,
            n_iter=config.n_trials,
            cv=config.cv_folds,
            scoring=scoring,
            n_jobs=config.n_jobs,
            random_state=config.random_state,
            error_score=np.nan,
        )
        search.fit(X, y)
        return (
            dict(search.best_params_),
            float(search.best_score_),
            _trials_from_cv_results(search.cv_results_),
            None,
        )

    def _tune_bayesian(
        self, estimator, X, y, space, config, scoring, is_classification
    ) -> tuple[dict, float, list[TrialResult], dict[str, float] | None] | None:
        """Optuna TPE search with median pruning. ``None`` if optuna is absent."""
        try:
            import optuna
            from optuna.pruners import MedianPruner
            from optuna.samplers import TPESampler
        except ImportError:
            logger.info("optuna not installed; Bayesian tuning degrades to random search")
            return None

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        scorer = get_scorer(scoring)
        splitter = (
            StratifiedKFold(n_splits=config.cv_folds, shuffle=True, random_state=config.random_state)
            if is_classification
            else KFold(n_splits=config.cv_folds, shuffle=True, random_state=config.random_state)
        )

        def objective(trial: optuna.Trial) -> float:
            params = {name: _optuna_suggest(trial, name, spec) for name, spec in space.items()}
            model = clone(estimator).set_params(**params)
            fold_scores: list[float] = []
            for step, (tr, va) in enumerate(splitter.split(X, y)):
                X_tr, X_va = _take(X, tr), _take(X, va)
                y_tr, y_va = _take(y, tr), _take(y, va)
                model.fit(X_tr, y_tr)
                fold_scores.append(float(scorer(model, X_va, y_va)))
                # Report the running mean so MedianPruner can stop poor trials
                # early (genuine early stopping, AC #4).
                trial.report(float(np.mean(fold_scores)), step)
                if trial.should_prune():
                    raise optuna.TrialPruned()
            return float(np.mean(fold_scores))

        study = optuna.create_study(
            direction="maximize",
            sampler=TPESampler(seed=config.random_state),
            pruner=MedianPruner(),
        )
        study.optimize(
            objective,
            n_trials=config.n_trials,
            timeout=config.time_budget,
            n_jobs=config.n_jobs,
            catch=(Exception,),
        )

        completed = [t for t in study.trials if t.value is not None]
        if not completed:
            return None
        trials = [
            TrialResult(
                trial_number=t.number,
                params=dict(t.params),
                score=float(t.value),  # type: ignore[arg-type]  # filtered non-None above
            )
            for t in completed
        ]
        importance: dict[str, float] | None = None
        try:
            importance = {
                k: float(v) for k, v in optuna.importance.get_param_importances(study).items()
            }
        except Exception as exc:  # needs >=2 completed trials with variation
            logger.debug(f"Parameter-importance computation skipped: {exc}")
        # ``completed`` is non-empty, so the study has a best value.
        best_value = study.best_value
        assert best_value is not None
        return dict(study.best_params), float(best_value), trials, importance


# -- helpers ---------------------------------------------------------------------


def _now() -> float:
    import time

    return time.monotonic()


def _n_rows(X: Any) -> int | None:
    try:
        return int(X.shape[0])
    except Exception:
        return None


def _n_cols(X: Any) -> int | None:
    try:
        return int(X.shape[1])
    except Exception:
        return None


def _take(data: Any, idx: np.ndarray) -> Any:
    """Index rows of a DataFrame/ndarray/Series by positional indices."""
    if hasattr(data, "iloc"):
        return data.iloc[idx]
    return data[idx]


def _grid_values(spec: ParamSpec) -> list[Any]:
    """Coarse discretization (<=3 points/param) so the grid stays small."""
    if spec.kind == "categorical":
        return list(spec.choices or [])
    low, high = spec.low, spec.high
    assert low is not None and high is not None
    if spec.kind == "int":
        return sorted({int(low), int(round((low + high) / 2)), int(high)})
    fmid = math.sqrt(low * high) if spec.log else (low + high) / 2
    return [round(low, 6), round(fmid, 6), round(high, 6)]


def _random_values(spec: ParamSpec) -> Any:
    """A scipy distribution / list for RandomizedSearchCV."""
    from scipy.stats import loguniform, randint, uniform

    if spec.kind == "categorical":
        return list(spec.choices or [])
    low, high = spec.low, spec.high
    assert low is not None and high is not None
    if spec.kind == "int":
        return randint(int(low), int(high) + 1)
    if spec.log:
        return loguniform(low, high)
    return uniform(low, high - low)


def _optuna_suggest(trial: Any, name: str, spec: ParamSpec) -> Any:
    if spec.kind == "categorical":
        return trial.suggest_categorical(name, spec.choices or [])
    low, high = spec.low, spec.high
    assert low is not None and high is not None
    if spec.kind == "int":
        return trial.suggest_int(name, int(low), int(high), log=spec.log)
    return trial.suggest_float(name, float(low), float(high), log=spec.log)


def _trials_from_cv_results(cv_results: dict) -> list[TrialResult]:
    """Build TrialResult list from a scikit-learn search's ``cv_results_``."""
    params = cv_results.get("params", [])
    scores = cv_results.get("mean_test_score", [])
    trials: list[TrialResult] = []
    for i, (p, s) in enumerate(zip(params, scores)):
        if s is None or (isinstance(s, float) and math.isnan(s)):
            continue
        trials.append(TrialResult(trial_number=i, params=dict(p), score=float(s)))
    return trials


def _history(trials: list[TrialResult]) -> list[dict[str, Any]]:
    """Per-trial score + running best, for the optimization-history chart."""
    history: list[dict[str, Any]] = []
    best = -math.inf
    for t in trials:
        best = max(best, t.score)
        history.append({"trial": int(t.trial_number), "score": float(t.score), "best_so_far": float(best)})
    return history
