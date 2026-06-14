"""Tests for MetricsService (issue #79).

Pure-function metric computations are asserted against direct
sklearn.metrics results for binary, multiclass, and regression cases,
plus degenerate edge cases (no probabilities, single-class y_test,
curve downsampling).
"""

import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from sklearn.datasets import make_classification, make_regression
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
    roc_auc_score,
)

from app.schemas.evaluation import (
    ClassificationMetrics,
    ConfusionMatrixData,
    PRCurveData,
    RegressionMetrics,
    ROCCurveData,
)
from app.services.metrics_service import MetricsService

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def binary_case():
    X, y = make_classification(n_samples=200, n_features=8, random_state=42)
    clf = LogisticRegression(max_iter=1000).fit(X[:150], y[:150])
    y_test = y[150:].tolist()
    y_pred = clf.predict(X[150:]).tolist()
    y_proba = clf.predict_proba(X[150:]).tolist()
    return y_test, y_pred, y_proba, ["0", "1"]


@pytest.fixture(scope="module")
def multiclass_case():
    X, y = make_classification(
        n_samples=300,
        n_features=10,
        n_informative=6,
        n_classes=3,
        random_state=42,
    )
    clf = LogisticRegression(max_iter=1000).fit(X[:240], y[:240])
    y_test = y[240:].tolist()
    y_pred = clf.predict(X[240:]).tolist()
    y_proba = clf.predict_proba(X[240:]).tolist()
    return y_test, y_pred, y_proba, ["0", "1", "2"]


@pytest.fixture(scope="module")
def regression_case():
    X, y = make_regression(n_samples=200, n_features=5, noise=10.0, random_state=42)
    y = y + 500.0  # keep y_test away from zero so mape is defined
    reg = LinearRegression().fit(X[:150], y[:150])
    return y[150:].tolist(), reg.predict(X[150:]).tolist()


class TestClassificationMetrics:
    def test_binary_matches_sklearn(self, binary_case):
        y_test, y_pred, y_proba, labels = binary_case
        result = MetricsService.compute_classification_metrics(
            y_test, y_pred, y_proba, labels
        )

        assert isinstance(result, ClassificationMetrics)
        yt = [str(v) for v in y_test]
        yp = [str(v) for v in y_pred]
        assert result.accuracy == pytest.approx(accuracy_score(yt, yp))

        p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(
            yt, yp, labels=labels, average="macro", zero_division=0
        )
        p_w, r_w, f_w, _ = precision_recall_fscore_support(
            yt, yp, labels=labels, average="weighted", zero_division=0
        )
        assert result.precision_macro == pytest.approx(p_macro)
        assert result.recall_macro == pytest.approx(r_macro)
        assert result.f1_macro == pytest.approx(f_macro)
        assert result.precision_weighted == pytest.approx(p_w)
        assert result.recall_weighted == pytest.approx(r_w)
        assert result.f1_weighted == pytest.approx(f_w)

        proba = np.asarray(y_proba)
        assert result.roc_auc == pytest.approx(
            roc_auc_score(np.asarray(y_test), proba[:, 1])
        )
        assert result.log_loss == pytest.approx(log_loss(yt, proba, labels=labels))

    def test_per_class_metrics(self, binary_case):
        y_test, y_pred, y_proba, labels = binary_case
        result = MetricsService.compute_classification_metrics(
            y_test, y_pred, y_proba, labels
        )

        yt = [str(v) for v in y_test]
        yp = [str(v) for v in y_pred]
        p, r, f, s = precision_recall_fscore_support(
            yt, yp, labels=labels, average=None, zero_division=0
        )
        assert set(result.per_class_metrics) == set(labels)
        for i, label in enumerate(labels):
            per_class = result.per_class_metrics[label]
            assert per_class.precision == pytest.approx(p[i])
            assert per_class.recall == pytest.approx(r[i])
            assert per_class.f1 == pytest.approx(f[i])
            assert per_class.support == int(s[i])

    def test_multiclass_matches_sklearn(self, multiclass_case):
        y_test, y_pred, y_proba, labels = multiclass_case
        result = MetricsService.compute_classification_metrics(
            y_test, y_pred, y_proba, labels
        )

        yt = [str(v) for v in y_test]
        yp = [str(v) for v in y_pred]
        assert result.accuracy == pytest.approx(accuracy_score(yt, yp))
        assert len(result.per_class_metrics) == 3
        assert result.roc_auc == pytest.approx(
            roc_auc_score(
                np.asarray(y_test),
                np.asarray(y_proba),
                multi_class="ovr",
                average="macro",
            )
        )
        assert result.log_loss == pytest.approx(
            log_loss(yt, np.asarray(y_proba), labels=labels)
        )

    def test_no_probabilities_gives_none_auc_and_log_loss(self, binary_case):
        y_test, y_pred, _, labels = binary_case
        result = MetricsService.compute_classification_metrics(
            y_test, y_pred, None, labels
        )
        assert result.roc_auc is None
        assert result.log_loss is None
        assert result.accuracy >= 0.0

    def test_single_class_y_test_does_not_crash(self):
        """Degenerate held-out set: only one true class present."""
        y_test = ["A"] * 10
        y_pred = ["A"] * 7 + ["B"] * 3
        y_proba = [[0.7, 0.3]] * 10
        result = MetricsService.compute_classification_metrics(
            y_test, y_pred, y_proba, ["A", "B"]
        )
        assert result.accuracy == pytest.approx(0.7)
        assert result.roc_auc is None  # undefined with a single true class


class TestRegressionMetrics:
    def test_matches_sklearn(self, regression_case):
        y_test, y_pred = regression_case
        result = MetricsService.compute_regression_metrics(y_test, y_pred)

        assert isinstance(result, RegressionMetrics)
        mse = mean_squared_error(y_test, y_pred)
        assert result.mae == pytest.approx(mean_absolute_error(y_test, y_pred))
        assert result.mse == pytest.approx(mse)
        assert result.rmse == pytest.approx(np.sqrt(mse))
        assert result.r2 == pytest.approx(r2_score(y_test, y_pred))

        yt = np.asarray(y_test)
        yp = np.asarray(y_pred)
        expected_mape = float(np.mean(np.abs((yt - yp) / yt)) * 100)
        assert result.mape == pytest.approx(expected_mape)

    def test_mape_none_when_y_test_contains_zero(self):
        result = MetricsService.compute_regression_metrics(
            [0.0, 1.0, 2.0], [0.1, 1.1, 1.9]
        )
        assert result.mape is None
        assert result.mae > 0


class TestConfusionMatrix:
    def test_matches_sklearn(self, multiclass_case):
        y_test, y_pred, _, labels = multiclass_case
        result = MetricsService.compute_confusion_matrix(y_test, y_pred, labels)

        assert isinstance(result, ConfusionMatrixData)
        assert result.labels == labels
        yt = [str(v) for v in y_test]
        yp = [str(v) for v in y_pred]
        expected = confusion_matrix(yt, yp, labels=labels)
        assert result.matrix == expected.tolist()
        assert all(isinstance(cell, int) for row in result.matrix for cell in row)


class TestROCCurves:
    def test_binary_curves(self, binary_case):
        y_test, _, y_proba, labels = binary_case
        result = MetricsService.compute_roc_curves(y_test, y_proba, labels)

        assert isinstance(result, ROCCurveData)
        assert set(result.curves) == set(labels)
        proba = np.asarray(y_proba)
        yt = np.asarray([str(v) for v in y_test])
        for i, label in enumerate(labels):
            y_bin = (yt == label).astype(int)
            assert result.auc_per_class[label] == pytest.approx(
                roc_auc_score(y_bin, proba[:, i])
            )
        assert result.macro_auc == pytest.approx(
            np.mean(list(result.auc_per_class.values()))
        )
        # Each curve spans FPR 0 -> 1
        for points in result.curves.values():
            assert points[0].x == pytest.approx(0.0)
            assert points[-1].x == pytest.approx(1.0)

    def test_none_when_proba_absent(self, binary_case):
        y_test, _, _, labels = binary_case
        assert MetricsService.compute_roc_curves(y_test, None, labels) is None

    def test_downsampling_caps_points(self):
        rng = np.random.RandomState(0)
        n = 5000
        y_test = rng.choice(["a", "b"], n).tolist()
        p = rng.rand(n)
        y_proba = np.column_stack([1 - p, p]).tolist()

        result = MetricsService.compute_roc_curves(y_test, y_proba, ["a", "b"])
        for points in result.curves.values():
            assert len(points) <= 200
            # Endpoints survive downsampling
            assert points[0].x == pytest.approx(0.0)
            assert points[-1].x == pytest.approx(1.0)

    def test_skips_classes_absent_from_y_test(self):
        y_test = ["A"] * 10
        y_proba = [[0.6, 0.4]] * 10
        result = MetricsService.compute_roc_curves(y_test, y_proba, ["A", "B"])
        # AUC undefined for every class (single true class) -> no curves
        assert result.curves == {}
        assert result.macro_auc is None


class TestPRCurves:
    def test_binary_curves(self, binary_case):
        y_test, _, y_proba, labels = binary_case
        result = MetricsService.compute_pr_curves(y_test, y_proba, labels)

        assert isinstance(result, PRCurveData)
        assert set(result.curves) == set(labels)
        yt = np.asarray([str(v) for v in y_test])
        for label in labels:
            prevalence = float((yt == label).mean())
            assert result.baseline_per_class[label] == pytest.approx(prevalence)
        for points in result.curves.values():
            assert all(0.0 <= pt.x <= 1.0 and 0.0 <= pt.y <= 1.0 for pt in points)

    def test_none_when_proba_absent(self, binary_case):
        y_test, _, _, labels = binary_case
        assert MetricsService.compute_pr_curves(y_test, None, labels) is None

    def test_downsampling_caps_points(self):
        rng = np.random.RandomState(0)
        n = 5000
        y_test = rng.choice(["a", "b"], n).tolist()
        p = rng.rand(n)
        y_proba = np.column_stack([1 - p, p]).tolist()

        result = MetricsService.compute_pr_curves(y_test, y_proba, ["a", "b"])
        for points in result.curves.values():
            assert len(points) <= 200


class TestLoadEvaluationArtifacts:
    @pytest.mark.asyncio
    async def test_returns_none_without_path(self):
        ml_model = MagicMock()
        ml_model.evaluation_data_path = None
        assert await MetricsService.load_evaluation_artifacts(ml_model) is None

    @pytest.mark.asyncio
    async def test_downloads_and_parses_payload(self, monkeypatch):
        payload = {
            "problem_type": "binary_classification",
            "y_test": [0, 1],
            "y_pred": [0, 0],
            "y_proba": [[0.8, 0.2], [0.6, 0.4]],
            "class_labels": ["0", "1"],
            "created_at": "2026-06-11T00:00:00+00:00",
        }
        mock_s3 = MagicMock()
        mock_s3.bucket_name = "test-bucket"
        mock_s3.download_file_obj = AsyncMock(
            return_value=json.dumps(payload).encode("utf-8")
        )
        monkeypatch.setattr("app.services.metrics_service.s3_service", mock_s3)

        ml_model = MagicMock()
        ml_model.evaluation_data_path = (
            "s3://test-bucket/models/u/m/evaluation_data.json"
        )
        result = await MetricsService.load_evaluation_artifacts(ml_model)

        assert result == payload
        mock_s3.download_file_obj.assert_awaited_once_with(
            "models/u/m/evaluation_data.json"
        )

    @pytest.mark.asyncio
    async def test_returns_none_on_bucket_mismatch(self, monkeypatch):
        """A path stored under a different bucket degrades cleanly, no S3 call."""
        mock_s3 = MagicMock()
        mock_s3.bucket_name = "configured-bucket"
        mock_s3.download_file_obj = AsyncMock()
        monkeypatch.setattr("app.services.metrics_service.s3_service", mock_s3)

        ml_model = MagicMock()
        ml_model.model_id = "m_other_bucket"
        ml_model.evaluation_data_path = (
            "s3://other-bucket/models/u/m/evaluation_data.json"
        )

        assert await MetricsService.load_evaluation_artifacts(ml_model) is None
        mock_s3.download_file_obj.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_none_on_download_failure(self, monkeypatch):
        mock_s3 = MagicMock()
        mock_s3.bucket_name = "test-bucket"
        mock_s3.download_file_obj = AsyncMock(side_effect=RuntimeError("S3 down"))
        monkeypatch.setattr("app.services.metrics_service.s3_service", mock_s3)

        ml_model = MagicMock()
        ml_model.evaluation_data_path = (
            "s3://test-bucket/models/u/m/evaluation_data.json"
        )
        assert await MetricsService.load_evaluation_artifacts(ml_model) is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self, monkeypatch):
        mock_s3 = MagicMock()
        mock_s3.bucket_name = "test-bucket"
        mock_s3.download_file_obj = AsyncMock(return_value=b"not-json")
        monkeypatch.setattr("app.services.metrics_service.s3_service", mock_s3)

        ml_model = MagicMock()
        ml_model.evaluation_data_path = (
            "s3://test-bucket/models/u/m/evaluation_data.json"
        )
        assert await MetricsService.load_evaluation_artifacts(ml_model) is None


class TestLoadShapArtifacts:
    """MetricsService.load_shap_artifacts mirrors the evaluation loader (#80)."""

    @pytest.mark.asyncio
    async def test_returns_none_without_path(self):
        ml_model = MagicMock()
        ml_model.shap_values_path = None
        assert await MetricsService.load_shap_artifacts(ml_model) is None

    @pytest.mark.asyncio
    async def test_downloads_and_parses_payload(self, monkeypatch):
        payload = {
            "explainer_type": "tree",
            "shap_importance": {"f1": 0.6, "f2": 0.4},
            "base_value": 0.5,
            "n_samples": 120,
            "created_at": "2026-06-14T00:00:00+00:00",
        }
        mock_s3 = MagicMock()
        mock_s3.bucket_name = "test-bucket"
        mock_s3.download_file_obj = AsyncMock(
            return_value=json.dumps(payload).encode("utf-8")
        )
        monkeypatch.setattr("app.services.metrics_service.s3_service", mock_s3)

        ml_model = MagicMock()
        ml_model.shap_values_path = "s3://test-bucket/models/u/m/shap_data.json"
        result = await MetricsService.load_shap_artifacts(ml_model)

        assert result == payload
        mock_s3.download_file_obj.assert_awaited_once_with("models/u/m/shap_data.json")

    @pytest.mark.asyncio
    async def test_returns_none_on_bucket_mismatch(self, monkeypatch):
        mock_s3 = MagicMock()
        mock_s3.bucket_name = "configured-bucket"
        mock_s3.download_file_obj = AsyncMock()
        monkeypatch.setattr("app.services.metrics_service.s3_service", mock_s3)

        ml_model = MagicMock()
        ml_model.model_id = "m_other_bucket"
        ml_model.shap_values_path = "s3://other-bucket/models/u/m/shap_data.json"

        assert await MetricsService.load_shap_artifacts(ml_model) is None
        mock_s3.download_file_obj.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_none_on_download_failure(self, monkeypatch):
        mock_s3 = MagicMock()
        mock_s3.bucket_name = "test-bucket"
        mock_s3.download_file_obj = AsyncMock(side_effect=RuntimeError("S3 down"))
        monkeypatch.setattr("app.services.metrics_service.s3_service", mock_s3)

        ml_model = MagicMock()
        ml_model.shap_values_path = "s3://test-bucket/models/u/m/shap_data.json"
        assert await MetricsService.load_shap_artifacts(ml_model) is None
