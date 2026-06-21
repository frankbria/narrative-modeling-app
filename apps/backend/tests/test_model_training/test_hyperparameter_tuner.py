"""
Tests for hyperparameter tuning (issue #77): the standalone HyperparameterTuner
service and its integration into the AutoML engine.
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression

from app.services.model_training.hyperparameter_tuner import (
    HyperparameterTuner,
    TuningConfig,
    TuningResult,
    _canonical_algorithm,
)


@pytest.fixture
def tuner():
    return HyperparameterTuner()


@pytest.fixture
def classification_xy():
    from sklearn.datasets import make_classification

    X, y = make_classification(
        n_samples=150, n_features=6, n_informative=4, random_state=0
    )
    return pd.DataFrame(X, columns=[f"f{i}" for i in range(6)]), pd.Series(y)


class TestSearchSpace:
    def test_random_forest_space_has_expected_params(self, tuner):
        space = tuner.get_search_space("Random Forest")
        assert {"n_estimators", "max_depth", "min_samples_split", "max_features"} <= set(
            space
        )
        assert space["n_estimators"].kind == "int"
        assert space["max_features"].kind == "categorical"

    def test_xgboost_space(self, tuner):
        space = tuner.get_search_space("XGBoost Regressor")  # regressor name maps too
        assert "learning_rate" in space and space["learning_rate"].log is True

    def test_unknown_algorithm_returns_empty(self, tuner):
        assert tuner.get_search_space("Mystery Model") == {}

    def test_linear_regression_has_no_tunable_space(self, tuner):
        # No meaningful hyperparameters -> empty space -> tuning is skipped.
        assert tuner.get_search_space("Linear Regression") == {}

    def test_data_driven_adaptation_shrinks_large_data(self, tuner):
        normal = tuner.get_search_space("Random Forest", n_samples=2000, n_features=5)
        large = tuner.get_search_space("Random Forest", n_samples=50000, n_features=5)
        assert large["n_estimators"].high < normal["n_estimators"].high
        assert large["max_depth"].high <= 15

    def test_adaptation_does_not_mutate_base_space(self, tuner):
        tuner.get_search_space("Random Forest", n_samples=50000, n_features=200)
        # A fresh default-shape call must still see the original wide range.
        fresh = tuner.get_search_space("Random Forest")
        assert fresh["n_estimators"].high == 300

    def test_canonical_mapping(self):
        assert _canonical_algorithm("Support Vector Regressor") == "svm"
        assert _canonical_algorithm("K-Nearest Neighbors") == "knn"
        assert _canonical_algorithm("Linear Regression") is None


class TestStrategies:
    @pytest.mark.parametrize("strategy", ["grid", "random", "bayesian"])
    def test_each_strategy_returns_result(self, tuner, classification_xy, strategy):
        X, y = classification_xy
        cfg = TuningConfig(
            strategy=strategy, n_trials=6, cv_folds=3, scoring="roc_auc", n_jobs=1
        )
        result = tuner.tune(
            "Random Forest", RandomForestClassifier(random_state=0), X, y, cfg, True
        )
        assert isinstance(result, TuningResult)
        assert result.best_params  # non-empty
        assert result.n_trials_completed > 0
        # Best score is at least the default (tuning selects the default if nothing beats it...
        # not guaranteed for tiny random runs, but it must be a real float).
        assert isinstance(result.best_score, float)
        assert result.optimization_history  # history populated for the chart

    def test_random_search_respects_n_trials(self, tuner, classification_xy):
        X, y = classification_xy
        cfg = TuningConfig(strategy="random", n_trials=5, cv_folds=3, scoring="roc_auc", n_jobs=1)
        result = tuner.tune(
            "Random Forest", RandomForestClassifier(random_state=0), X, y, cfg, True
        )
        assert result.n_trials_completed == 5

    def test_bayesian_has_parameter_importance(self, tuner, classification_xy):
        X, y = classification_xy
        cfg = TuningConfig(strategy="bayesian", n_trials=8, cv_folds=3, scoring="roc_auc", n_jobs=1)
        result = tuner.tune(
            "Random Forest", RandomForestClassifier(random_state=0), X, y, cfg, True
        )
        # optuna computes param importance; grid/random leave it None.
        assert result.parameter_importance is not None

    def test_improvement_is_best_minus_default(self, tuner, classification_xy):
        X, y = classification_xy
        cfg = TuningConfig(strategy="random", n_trials=5, cv_folds=3, scoring="roc_auc", n_jobs=1)
        result = tuner.tune(
            "Random Forest", RandomForestClassifier(random_state=0), X, y, cfg, True
        )
        assert result.improvement_over_default == pytest.approx(
            result.best_score - result.default_score
        )

    def test_to_dict_is_json_safe(self, tuner, classification_xy):
        X, y = classification_xy
        cfg = TuningConfig(strategy="bayesian", n_trials=6, cv_folds=3, scoring="roc_auc", n_jobs=1)
        d = tuner.tune(
            "Random Forest", RandomForestClassifier(random_state=0), X, y, cfg, True
        ).to_dict()
        import json

        json.dumps(d)  # must not raise on numpy scalars
        assert d["algorithm"] == "Random Forest"
        assert isinstance(d["best_params"], dict)


class TestResilience:
    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError):
            TuningConfig(strategy="genetic")

    def test_untunable_algorithm_returns_none(self, tuner, classification_xy):
        X, y = classification_xy
        cfg = TuningConfig(strategy="random", n_trials=3, cv_folds=3, scoring="r2", n_jobs=1)
        assert (
            tuner.tune("Linear Regression", LinearRegression(), X, y, cfg, False)
            is None
        )

    def test_tuning_failure_returns_none(self, tuner, classification_xy):
        X, y = classification_xy
        # scoring metric that's invalid for sklearn -> the baseline CV raises ->
        # tune() degrades to None instead of propagating.
        cfg = TuningConfig(strategy="random", n_trials=3, cv_folds=3, scoring="not_a_metric", n_jobs=1)
        assert (
            tuner.tune("Random Forest", RandomForestClassifier(), X, y, cfg, True)
            is None
        )

    def test_bayesian_degrades_to_random_without_optuna(
        self, tuner, classification_xy, monkeypatch
    ):
        X, y = classification_xy
        # Simulate optuna being absent: the import inside _tune_bayesian fails and
        # the strategy falls back to random search.
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "optuna" or name.startswith("optuna."):
                raise ImportError("optuna not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        cfg = TuningConfig(strategy="bayesian", n_trials=4, cv_folds=3, scoring="roc_auc", n_jobs=1)
        result = tuner.tune(
            "Random Forest", RandomForestClassifier(random_state=0), X, y, cfg, True
        )
        assert result is not None
        assert result.strategy == "random"  # degraded


class TestEngineIntegration:
    @pytest.mark.asyncio
    async def test_engine_with_tuning_populates_results(self):
        """AutoMLEngine(enable_tuning=True) tunes candidates and records results."""
        from app.services.model_training.automl_engine import AutoMLEngine

        np.random.seed(0)
        n = 160
        df = pd.DataFrame(
            {
                "a": np.random.randn(n),
                "b": np.random.randn(n),
                "c": np.random.randint(0, 5, n),
                "target": np.random.choice([0, 1], n, p=[0.45, 0.55]),
            }
        )
        engine = AutoMLEngine(
            max_models=2,  # keep the run fast: 2 candidates
            cv_folds=3,
            random_state=42,
            enable_tuning=True,
            tuning_config=TuningConfig(
                strategy="random", n_trials=4, cv_folds=3, n_jobs=1
            ),
        )
        result = await engine.run(df, "target")

        assert result.tuning_results is not None
        assert result.tuning_strategy == "random"
        # At least one of the (tunable) candidates produced a tuning payload.
        assert len(result.tuning_results) >= 1
        for payload in result.tuning_results.values():
            assert "best_params" in payload
            assert "optimization_history" in payload
            assert "improvement_over_default" in payload

    @pytest.mark.asyncio
    async def test_tuning_disabled_by_default(self):
        from app.services.model_training.automl_engine import AutoMLEngine

        np.random.seed(1)
        n = 120
        df = pd.DataFrame(
            {
                "a": np.random.randn(n),
                "b": np.random.randn(n),
                "target": np.random.choice([0, 1], n),
            }
        )
        result = await AutoMLEngine(max_models=2, cv_folds=3).run(df, "target")
        assert result.tuning_results is None
        assert result.tuning_strategy is None
        assert result.improvement_from_tuning is None
