"""Tests for evaluation-artifact capture in the AutoML engine (issue #79).

The engine must carry the BEST model's held-out test arrays (y_test, y_pred,
y_proba) and human-readable class labels on the AutoMLResult so the training
task can persist them for the evaluation dashboard.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.services.model_training.automl_engine import AutoMLEngine, AutoMLResult
from app.services.model_training.problem_detector import (
    ProblemDetectionResult,
    ProblemType,
)


def _engine(**kwargs) -> AutoMLEngine:
    defaults = dict(max_models=2, cv_folds=3, test_size=0.2, random_state=42)
    defaults.update(kwargs)
    return AutoMLEngine(**defaults)


def _detection(problem_type: ProblemType, target: str) -> ProblemDetectionResult:
    return ProblemDetectionResult(
        problem_type=problem_type,
        target_column=target,
        confidence=0.95,
        reasoning="test",
        metadata={},
    )


async def _run(engine: AutoMLEngine, df: pd.DataFrame, target: str, problem_type):
    async def mock_detect(df, target_column):
        return _detection(problem_type, target)

    with patch.object(
        engine.problem_detector, "detect_problem_type", side_effect=mock_detect
    ):
        return await engine.run(df, target)


@pytest.fixture
def binary_df():
    rng = np.random.RandomState(42)
    n = 120
    return pd.DataFrame(
        {
            "f1": rng.randn(n),
            "f2": rng.randn(n),
            "target": rng.choice(["yes", "no"], n, p=[0.6, 0.4]),
        }
    )


@pytest.fixture
def multiclass_df():
    rng = np.random.RandomState(42)
    n = 150
    return pd.DataFrame(
        {
            "f1": rng.randn(n),
            "f2": rng.randn(n),
            "target": rng.choice(["A", "B", "C"], n),
        }
    )


@pytest.fixture
def regression_df():
    rng = np.random.RandomState(42)
    n = 120
    f1 = rng.randn(n)
    f2 = rng.randn(n)
    return pd.DataFrame(
        {"f1": f1, "f2": f2, "target": 5 + 2 * f1 - f2 + rng.randn(n) * 0.1}
    )


class TestEvaluationArtifactCapture:
    """AutoMLResult carries held-out arrays for the best model."""

    @pytest.mark.asyncio
    async def test_binary_classification_arrays(self, binary_df):
        engine = _engine()
        result = await _run(
            engine, binary_df, "target", ProblemType.BINARY_CLASSIFICATION
        )

        assert isinstance(result, AutoMLResult)
        expected_test_size = int(round(len(binary_df) * 0.2))
        assert result.y_test is not None
        assert result.y_pred is not None
        assert len(result.y_test) == expected_test_size
        assert len(result.y_pred) == len(result.y_test)

        # Labels in original (string) space, sorted like estimator.classes_
        assert result.class_labels == ["no", "yes"]
        assert set(result.y_test).issubset({"yes", "no"})
        assert set(result.y_pred).issubset({"yes", "no"})

        # Both default candidates (LogReg, RF) support predict_proba
        assert result.y_proba is not None
        proba = np.asarray(result.y_proba)
        assert proba.shape == (expected_test_size, 2)
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-6)

    @pytest.mark.asyncio
    async def test_multiclass_classification_arrays(self, multiclass_df):
        engine = _engine()
        result = await _run(
            engine, multiclass_df, "target", ProblemType.MULTICLASS_CLASSIFICATION
        )

        assert result.class_labels == ["A", "B", "C"]
        assert len(result.y_pred) == len(result.y_test)
        proba = np.asarray(result.y_proba)
        assert proba.shape == (len(result.y_test), 3)

    @pytest.mark.asyncio
    async def test_regression_arrays(self, regression_df):
        engine = _engine()
        result = await _run(engine, regression_df, "target", ProblemType.REGRESSION)

        assert result.y_test is not None
        assert result.y_pred is not None
        assert len(result.y_pred) == len(result.y_test)
        # No probabilities or class labels for regressors
        assert result.y_proba is None
        assert result.class_labels is None

    @pytest.mark.asyncio
    async def test_predictions_match_best_model(self, binary_df):
        """y_pred must be the BEST model's predictions on the held-out set."""
        engine = _engine()
        result = await _run(
            engine, binary_df, "target", ProblemType.BINARY_CLASSIFICATION
        )

        # Rebuild the same split/transform and verify against the best estimator
        from sklearn.model_selection import train_test_split

        X = binary_df.drop(columns=["target"])
        y = binary_df["target"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        X_test_transformed = await engine.feature_engineer.transform(X_test)
        expected = result.best_model.estimator.predict(X_test_transformed)

        assert list(result.y_pred) == list(expected)
        assert list(result.y_test) == list(y_test)

    @pytest.mark.asyncio
    async def test_calibrated_test_score_matches_deployed_model(self, binary_df):
        """When calibration runs, test_score reflects the deployed model (#83).

        Calibration can shift held-out predictions, so the persisted
        ``test_score`` must be recomputed from the calibrated model's actual
        predictions rather than the pre-calibration estimator's.
        """
        from sklearn.metrics import accuracy_score

        engine = _engine()
        result = await _run(
            engine, binary_df, "target", ProblemType.BINARY_CLASSIFICATION
        )

        # The fixed binary fixture reliably triggers calibration; assert it
        # directly rather than skipping, so a calibration regression fails loudly.
        assert result.is_calibrated is True
        assert result.calibration_method in {"sigmoid", "isotonic"}

        expected_score = accuracy_score(result.y_test, result.y_pred)
        assert result.best_model.test_score == pytest.approx(expected_score)
        # The model-comparison row for the best model agrees too.
        comparison = result.metadata["model_comparison"]
        best_row = next(
            r for r in comparison if r["algorithm"] == result.best_model.name
        )
        assert best_row["test_score"] == pytest.approx(expected_score)


class TestGlobalShapCapture:
    """AutoMLResult carries the best model's global SHAP summary (issue #80)."""

    @pytest.mark.asyncio
    async def test_classification_shap_summary(self, binary_df):
        engine = _engine()
        result = await _run(
            engine, binary_df, "target", ProblemType.BINARY_CLASSIFICATION
        )

        # Default candidates (LogReg/RF) are SHAP-supported, so the best model
        # always yields a summary over the engineered feature space.
        assert result.shap_global is not None
        assert result.shap_explainer_type in {"tree", "linear"}
        assert set(result.shap_global.shap_importance) == set(result.feature_names)
        assert all(v >= 0 for v in result.shap_global.shap_importance.values())

    @pytest.mark.asyncio
    async def test_regression_shap_summary(self, regression_df):
        engine = _engine()
        result = await _run(engine, regression_df, "target", ProblemType.REGRESSION)

        assert result.shap_global is not None
        assert result.shap_explainer_type in {"tree", "linear"}
        assert set(result.shap_global.shap_importance) == set(result.feature_names)
