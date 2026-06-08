"""
Tests for AutoML result-summary helpers (comparison table, best-model
explanation, data profile). All pure functions — no DB/S3/LLM required.
"""

import pandas as pd
import numpy as np

from app.services.model_training.automl_engine import ModelCandidate
from app.services.model_training.problem_detector import ProblemType
from app.services.model_training.comparison import (
    build_model_comparison,
    build_best_model_explanation,
    build_data_profile,
)


def _candidate(name, cv, test=None, t=1.0):
    return ModelCandidate(
        name=name,
        estimator=object(),
        hyperparameters={},
        training_time=t,
        cv_score=cv,
        test_score=test,
    )


class TestBuildModelComparison:
    def test_orders_by_cv_score_descending(self):
        models = [
            _candidate("A", 0.80),
            _candidate("B", 0.92),
            _candidate("C", 0.88),
        ]
        table = build_model_comparison(models)

        assert [row["algorithm"] for row in table] == ["B", "C", "A"]
        assert table[0]["cv_score"] == 0.92

    def test_includes_all_metric_fields(self):
        table = build_model_comparison([_candidate("A", 0.9, 0.85, 2.5)])
        row = table[0]
        assert set(row) == {"algorithm", "cv_score", "test_score", "training_time"}
        assert row["test_score"] == 0.85
        assert row["training_time"] == 2.5

    def test_handles_missing_cv_score(self):
        models = [_candidate("A", None), _candidate("B", 0.7)]
        table = build_model_comparison(models)
        # The scored model ranks first; the unscored one sinks to the bottom.
        assert table[0]["algorithm"] == "B"


class TestBuildBestModelExplanation:
    def test_mentions_best_model_and_runner_up(self):
        best = _candidate("XGBoost", 0.93, 0.90)
        models = [best, _candidate("Random Forest", 0.88)]
        text = build_best_model_explanation(
            best, models, ProblemType.BINARY_CLASSIFICATION
        )
        assert "XGBoost" in text
        assert "Random Forest" in text
        assert "0.93" in text
        assert "ROC AUC" in text

    def test_single_candidate_has_no_runner_up(self):
        best = _candidate("Linear Regression", 0.75)
        text = build_best_model_explanation(
            best, [best], ProblemType.REGRESSION
        )
        assert "Linear Regression" in text
        assert "1 candidate" in text

    def test_handles_missing_score(self):
        best = _candidate("KNN", None)
        text = build_best_model_explanation(
            best, [best], ProblemType.BINARY_CLASSIFICATION
        )
        assert "KNN" in text


class TestBuildDataProfile:
    def test_counts_feature_types_excluding_target(self):
        df = pd.DataFrame(
            {
                "num1": np.arange(100),
                "num2": np.random.randn(100),
                "cat1": ["a", "b"] * 50,
                "target": np.random.choice([0, 1], 100),
            }
        )
        profile = build_data_profile(
            df, "target", ProblemType.BINARY_CLASSIFICATION
        )
        assert profile.n_samples == 100
        assert profile.n_features == 3  # target excluded
        assert profile.n_numeric_features == 2
        assert profile.n_categorical_features == 1
        assert profile.dataset_size_category == "small"

    def test_class_balance_ratio_for_classification(self):
        df = pd.DataFrame(
            {
                "f": np.arange(100),
                "target": [0] * 80 + [1] * 20,  # 4:1 imbalance
            }
        )
        profile = build_data_profile(
            df, "target", ProblemType.BINARY_CLASSIFICATION
        )
        assert profile.class_balance_ratio == 4.0

    def test_class_balance_ratio_none_for_regression(self):
        df = pd.DataFrame(
            {"f": np.arange(50), "target": np.random.randn(50)}
        )
        profile = build_data_profile(df, "target", ProblemType.REGRESSION)
        assert profile.class_balance_ratio is None
