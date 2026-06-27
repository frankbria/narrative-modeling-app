"""Unit tests for ConfidenceService (issue #83).

Exercises the pure confidence/calibration helpers with real scikit-learn
estimators (no mocking, per project convention). Calibration is fit on a
held-out split exactly as the training pipeline does.
"""

import numpy as np
import pytest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from app.services.confidence_service import (
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    ConfidenceService,
)


@pytest.fixture
def service() -> ConfidenceService:
    return ConfidenceService()


class TestConfidenceFromProba:
    def test_binary_returns_max_class_probability(self, service):
        assert service.confidence_from_proba([0.2, 0.8]) == pytest.approx(0.8)
        assert service.confidence_from_proba([0.7, 0.3]) == pytest.approx(0.7)

    def test_multiclass_returns_max(self, service):
        assert service.confidence_from_proba([0.1, 0.6, 0.3]) == pytest.approx(0.6)

    def test_perfect_and_chance(self, service):
        assert service.confidence_from_proba([1.0, 0.0]) == pytest.approx(1.0)
        assert service.confidence_from_proba([0.5, 0.5]) == pytest.approx(0.5)

    def test_accepts_numpy_array(self, service):
        assert service.confidence_from_proba(np.array([0.25, 0.75])) == pytest.approx(
            0.75
        )

    def test_empty_returns_none(self, service):
        assert service.confidence_from_proba([]) is None


class TestIsLowConfidence:
    def test_below_threshold_is_low(self, service):
        assert service.is_low_confidence(0.55) is True

    def test_at_or_above_threshold_is_not_low(self, service):
        assert service.is_low_confidence(DEFAULT_LOW_CONFIDENCE_THRESHOLD) is False
        assert service.is_low_confidence(0.95) is False

    def test_custom_threshold(self, service):
        assert service.is_low_confidence(0.85, threshold=0.9) is True

    def test_none_score_is_not_flagged(self, service):
        assert service.is_low_confidence(None) is False


class TestCalibrateClassifier:
    @pytest.fixture
    def fitted_split(self):
        X, y = make_classification(
            n_samples=400, n_features=8, n_informative=5, random_state=42
        )
        X_train, X_cal, y_train, y_cal = train_test_split(
            X, y, test_size=0.3, random_state=42
        )
        model = RandomForestClassifier(n_estimators=25, random_state=42)
        model.fit(X_train, y_train)
        return model, X_cal, y_cal

    def test_returns_calibrated_wrapper(self, service, fitted_split):
        model, X_cal, y_cal = fitted_split
        calibrated, method, brier = service.calibrate_classifier(model, X_cal, y_cal)
        assert isinstance(calibrated, CalibratedClassifierCV)
        assert method in {"sigmoid", "isotonic"}
        assert 0.0 <= brier <= 1.0
        # Calibrated model still predicts and produces probabilities
        proba = calibrated.predict_proba(X_cal)
        assert proba.shape == (len(X_cal), 2)

    def test_small_data_uses_sigmoid(self, service, fitted_split):
        model, X_cal, y_cal = fitted_split
        _, method, _ = service.calibrate_classifier(model, X_cal, y_cal)
        assert method == "sigmoid"  # 120 cal samples < isotonic threshold

    def test_explicit_method_respected(self, service, fitted_split):
        model, X_cal, y_cal = fitted_split
        _, method, _ = service.calibrate_classifier(
            model, X_cal, y_cal, method="isotonic"
        )
        assert method == "isotonic"

    def test_returns_none_on_single_class(self, service, fitted_split):
        """A degenerate calibration set (one class) must not raise."""
        model, X_cal, _ = fitted_split
        y_single = np.zeros(len(X_cal), dtype=int)
        result = service.calibrate_classifier(model, X_cal, y_single)
        assert result == (None, None, None)

    def test_out_of_sample_score_uses_score_set(self, service):
        """When X_score/y_score are passed, the brier is measured on them, not
        on the calibration-fit data (issue #201 — out-of-sample score)."""
        X, y = make_classification(
            n_samples=600, n_features=8, n_informative=5, random_state=7
        )
        X_fit, X_rest, y_fit, y_rest = train_test_split(
            X, y, test_size=0.4, random_state=7
        )
        X_cal, X_score, y_cal, y_score = train_test_split(
            X_rest, y_rest, test_size=0.5, random_state=7
        )
        model = RandomForestClassifier(n_estimators=25, random_state=7)
        model.fit(X_fit, y_fit)

        _, _, in_sample = service.calibrate_classifier(model, X_cal, y_cal)
        _, _, out_sample = service.calibrate_classifier(
            model, X_cal, y_cal, X_score=X_score, y_score=y_score
        )
        assert in_sample is not None and out_sample is not None
        # Different sets -> different scores (out-of-sample isn't the fit-set score).
        assert out_sample != pytest.approx(in_sample)


class TestRegressionInterval:
    def test_symmetric_interval(self, service):
        low, high = service.regression_interval(10.0, residual_std=2.0)
        assert low == pytest.approx(10.0 - 1.96 * 2.0)
        assert high == pytest.approx(10.0 + 1.96 * 2.0)

    def test_zero_std_collapses(self, service):
        low, high = service.regression_interval(5.0, residual_std=0.0)
        assert low == pytest.approx(5.0)
        assert high == pytest.approx(5.0)

    def test_none_std_returns_none(self, service):
        assert service.regression_interval(5.0, residual_std=None) is None

    def test_residual_std_from_arrays(self, service):
        y_test = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.5, 2.5, 2.5, 3.5])
        std = service.residual_std(y_test, y_pred)
        assert std == pytest.approx(np.std(y_test - y_pred))

    def test_residual_std_empty_returns_none(self, service):
        assert service.residual_std(np.array([]), np.array([])) is None
