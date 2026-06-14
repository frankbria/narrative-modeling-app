"""Unit tests for InterpretabilityService (issue #80).

SHAP-based global + per-instance interpretability. TreeExplainer for
tree/ensemble models, LinearExplainer for linear models; unsupported models
(e.g. KNN) degrade to ``None``. Real scikit-learn estimators and the real
``shap`` library are used (no mocking, per project conventions).
"""

import math

import pandas as pd
import pytest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.datasets import make_classification, make_regression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.neighbors import KNeighborsClassifier

from app.services.interpretability_service import InterpretabilityService

FEATURES = ["age", "income", "score", "tenure"]


@pytest.fixture
def service() -> InterpretabilityService:
    return InterpretabilityService()


def _classification_frame(n_samples=200, n_classes=2):
    X, y = make_classification(
        n_samples=n_samples,
        n_features=4,
        n_informative=3,
        n_redundant=0,
        n_classes=n_classes,
        n_clusters_per_class=1,
        random_state=7,
    )
    return pd.DataFrame(X, columns=FEATURES), y


def _regression_frame(n_samples=200):
    X, y = make_regression(
        n_samples=n_samples, n_features=4, n_informative=3, random_state=7
    )
    return pd.DataFrame(X, columns=FEATURES), y


# --- select_explainer_type ------------------------------------------------


def test_select_explainer_type_tree(service):
    X, y = _classification_frame()
    model = RandomForestClassifier(n_estimators=15, random_state=0).fit(X, y)
    assert service.select_explainer_type(model) == "tree"


def test_select_explainer_type_linear(service):
    X, y = _classification_frame()
    model = LogisticRegression(max_iter=500).fit(X, y)
    assert service.select_explainer_type(model) == "linear"


def test_select_explainer_type_unsupported(service):
    X, y = _classification_frame()
    model = KNeighborsClassifier().fit(X, y)
    assert service.select_explainer_type(model) is None


def test_select_explainer_type_unwraps_calibrated(service):
    """A calibrated tree classifier still resolves to its underlying type."""
    X, y = _classification_frame()
    base = RandomForestClassifier(n_estimators=15, random_state=0).fit(X, y)
    calibrated = CalibratedClassifierCV(FrozenEstimator(base)).fit(X, y)
    assert service.select_explainer_type(calibrated) == "tree"


# --- compute_global_shap ---------------------------------------------------


def test_global_shap_tree_classification(service):
    X, y = _classification_frame()
    model = RandomForestClassifier(n_estimators=15, random_state=0).fit(X, y)
    result = service.compute_global_shap(model, X, FEATURES, "classification")
    assert result is not None
    assert result.explainer_type == "tree"
    assert set(result.shap_importance) == set(FEATURES)
    assert all(math.isfinite(v) and v >= 0 for v in result.shap_importance.values())
    assert result.n_samples > 0


def test_global_shap_linear_regression(service):
    X, y = _regression_frame()
    model = LinearRegression().fit(X, y)
    result = service.compute_global_shap(model, X, FEATURES, "regression")
    assert result is not None
    assert result.explainer_type == "linear"
    assert set(result.shap_importance) == set(FEATURES)
    assert all(math.isfinite(v) and v >= 0 for v in result.shap_importance.values())


def test_global_shap_multiclass_tree(service):
    X, y = _classification_frame(n_classes=3)
    model = RandomForestClassifier(n_estimators=15, random_state=0).fit(X, y)
    result = service.compute_global_shap(model, X, FEATURES, "classification")
    assert result is not None
    assert len(result.shap_importance) == len(FEATURES)


def test_global_shap_unsupported_returns_none(service):
    X, y = _classification_frame()
    model = KNeighborsClassifier().fit(X, y)
    assert service.compute_global_shap(model, X, FEATURES, "classification") is None


def test_global_shap_samples_large_datasets(service):
    """Sampling keeps SHAP fast: at most ``max_samples`` rows are explained."""
    X, y = _classification_frame(n_samples=500)
    model = RandomForestClassifier(n_estimators=10, random_state=0).fit(X, y)
    result = service.compute_global_shap(
        model, X, FEATURES, "classification", max_samples=50
    )
    assert result is not None
    assert result.n_samples <= 50


def test_global_shap_never_raises_on_garbage(service):
    assert service.compute_global_shap(object(), None, FEATURES, "classification") is None


def test_global_shap_importance_json_safe(service):
    """Importance values must be plain finite floats (JSON-serializable)."""
    import json

    X, y = _classification_frame()
    model = RandomForestClassifier(n_estimators=15, random_state=0).fit(X, y)
    result = service.compute_global_shap(model, X, FEATURES, "classification")
    json.dumps(result.shap_importance)  # must not raise
    assert all(isinstance(v, float) for v in result.shap_importance.values())


# --- compute_instance_shap -------------------------------------------------


def test_instance_shap_tree(service):
    X, y = _classification_frame()
    model = RandomForestClassifier(n_estimators=15, random_state=0).fit(X, y)
    row = X.iloc[0].to_numpy()
    pred = model.predict(X.iloc[[0]])[0]
    result = service.compute_instance_shap(model, row, FEATURES, prediction=pred)
    assert result is not None
    assert len(result.contributions) == len(FEATURES)
    assert all(math.isfinite(float(c)) for c in result.contributions)


def test_instance_shap_tree_regression(service):
    X, y = _regression_frame()
    model = RandomForestRegressor(n_estimators=15, random_state=0).fit(X, y)
    row = X.iloc[0].to_numpy()
    result = service.compute_instance_shap(
        model, row, FEATURES, problem_type="regression"
    )
    assert result is not None
    assert len(result.contributions) == len(FEATURES)


def test_instance_shap_unsupported_returns_none(service):
    """Linear/other models are handled by the native explainer, not here."""
    X, y = _classification_frame()
    model = KNeighborsClassifier().fit(X, y)
    row = X.iloc[0].to_numpy()
    assert service.compute_instance_shap(model, row, FEATURES) is None


def test_instance_shap_never_raises_on_garbage(service):
    assert service.compute_instance_shap(object(), [1, 2, 3, 4], FEATURES) is None


# --- compute_instance_shap_batch -------------------------------------------


def test_instance_shap_batch_tree(service):
    X, y = _classification_frame()
    model = RandomForestClassifier(n_estimators=15, random_state=0).fit(X, y)
    preds = model.predict(X.iloc[:3]).tolist()
    rows = service.compute_instance_shap_batch(model, X.iloc[:3], FEATURES, preds)
    assert rows is not None
    assert len(rows) == 3
    assert all(len(r) == len(FEATURES) for r in rows)
    # Per-row SHAP: different rows yield different contributions
    assert list(rows[0]) != list(rows[1])


def test_instance_shap_batch_unsupported_returns_none(service):
    X, y = _classification_frame()
    model = KNeighborsClassifier().fit(X, y)
    assert service.compute_instance_shap_batch(model, X.iloc[:3], FEATURES) is None


def test_instance_shap_batch_never_raises_on_garbage(service):
    assert service.compute_instance_shap_batch(object(), None, FEATURES) is None


# --- top_drivers_text ------------------------------------------------------


def test_top_drivers_text_mentions_top_feature(service):
    importance = {"income": 0.5, "age": 0.3, "score": 0.1, "tenure": 0.05}
    text = service.top_drivers_text(importance)
    assert isinstance(text, str) and text
    assert "income" in text


def test_top_drivers_text_empty(service):
    text = service.top_drivers_text({})
    assert isinstance(text, str) and text
