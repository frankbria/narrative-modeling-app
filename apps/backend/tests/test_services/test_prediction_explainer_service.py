"""Unit tests for PredictionExplainerService (issue #83).

Per-prediction explanations use *model-native* importance only (no SHAP —
that machinery is issue #80). Linear models give genuinely per-row
contributions (coef * value); tree models fall back to global importance.
Real scikit-learn estimators are used (no mocking).
"""

import pytest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.datasets import make_classification, make_regression
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LinearRegression, LogisticRegression

from app.services.prediction_explainer_service import PredictionExplainerService


@pytest.fixture
def service() -> PredictionExplainerService:
    return PredictionExplainerService()


FEATURES = ["age", "income", "score", "tenure"]


@pytest.fixture
def linear_classifier():
    X, y = make_classification(
        n_samples=200, n_features=4, n_informative=3, n_redundant=0, random_state=1
    )
    return LogisticRegression(max_iter=200).fit(X, y), X[0]


@pytest.fixture
def tree_classifier():
    X, y = make_classification(
        n_samples=200, n_features=4, n_informative=3, n_redundant=0, random_state=1
    )
    return RandomForestClassifier(n_estimators=20, random_state=1).fit(X, y), X[0]


class TestExplainLinear:
    def test_linear_contributions_are_per_row(self, service, linear_classifier):
        model, row = linear_classifier
        result = service.explain(model, row, FEATURES, prediction=1)
        assert result is not None
        assert len(result.top_features) <= 5
        names = {f.feature_name for f in result.top_features}
        assert names.issubset(set(FEATURES))
        # contribution = coef * value, so it depends on the actual row
        for f in result.top_features:
            assert f.feature_value is not None

    def test_top_n_respected(self, service, linear_classifier):
        model, row = linear_classifier
        result = service.explain(model, row, FEATURES, prediction=1, top_n=2)
        assert len(result.top_features) == 2

    def test_sorted_by_absolute_contribution(self, service, linear_classifier):
        model, row = linear_classifier
        result = service.explain(model, row, FEATURES, prediction=1)
        mags = [abs(f.contribution) for f in result.top_features]
        assert mags == sorted(mags, reverse=True)


class TestExplainTree:
    def test_tree_uses_per_row_shap(self, service, tree_classifier):
        """Tree models get per-row SHAP contributions (issue #80)."""
        model, row = tree_classifier
        result = service.explain(model, row, FEATURES, prediction=1)
        assert result is not None
        assert result.method == "shap_tree"
        assert len(result.top_features) <= 5

    def test_tree_shap_contributions_differ_per_row(self, service, tree_classifier):
        """Unlike global importance, SHAP contributions depend on the row."""
        model, _ = tree_classifier
        X, _y = make_classification(
            n_samples=200, n_features=4, n_informative=3, n_redundant=0, random_state=1
        )
        c0 = {
            f.feature_name: f.contribution
            for f in service.explain(model, X[0], FEATURES, prediction=1).top_features
        }
        c5 = {
            f.feature_name: f.contribution
            for f in service.explain(model, X[5], FEATURES, prediction=1).top_features
        }
        assert c0 != c5

    def test_tree_falls_back_to_global_importance_without_shap(
        self, service, tree_classifier, monkeypatch
    ):
        """If SHAP is unavailable, trees fall back to #83 global importance."""
        model, row = tree_classifier
        monkeypatch.setattr(
            service._interpretability,
            "compute_instance_shap",
            lambda *a, **k: None,
        )
        result = service.explain(model, row, FEATURES, prediction=1)
        assert result is not None
        assert result.method == "tree_importance"


class TestExplainRegression:
    def test_linear_regression_contributions(self, service):
        X, y = make_regression(n_samples=200, n_features=4, random_state=2)
        model = LinearRegression().fit(X, y)
        result = service.explain(
            model,
            X[0],
            FEATURES,
            prediction=float(model.predict([X[0]])[0]),
            problem_type="regression",
        )
        assert result is not None
        assert result.method == "linear_coefficients"


class TestExplainCalibratedWrapper:
    def test_unwraps_calibrated_classifier(self, service):
        X, y = make_classification(
            n_samples=200, n_features=4, n_informative=3, n_redundant=0, random_state=1
        )
        base = LogisticRegression(max_iter=200).fit(X, y)
        cal = CalibratedClassifierCV(FrozenEstimator(base)).fit(X, y)
        result = service.explain(cal, X[0], FEATURES, prediction=1)
        assert result is not None
        assert result.method == "linear_coefficients"


class TestExplanationText:
    def test_text_mentions_top_feature(self, service, linear_classifier):
        model, row = linear_classifier
        result = service.explain(model, row, FEATURES, prediction=1)
        assert result.explanation_text
        top_name = result.top_features[0].feature_name
        assert top_name in result.explanation_text

    def test_unsupported_model_returns_none(self, service):
        from sklearn.neighbors import KNeighborsClassifier

        X, y = make_classification(
            n_samples=100, n_features=4, n_informative=3, n_redundant=0, random_state=1
        )
        model = KNeighborsClassifier().fit(X, y)
        # No coef_, no feature_importances_, no importance dict → None
        result = service.explain(model, X[0], FEATURES, prediction=1)
        assert result is None

    def test_importance_dict_fallback(self, service):
        from sklearn.neighbors import KNeighborsClassifier

        X, y = make_classification(
            n_samples=100, n_features=4, n_informative=3, n_redundant=0, random_state=1
        )
        model = KNeighborsClassifier().fit(X, y)
        importance = {"age": 0.5, "income": 0.3, "score": 0.1, "tenure": 0.1}
        result = service.explain(
            model, X[0], FEATURES, prediction=1, feature_importance=importance
        )
        assert result is not None
        assert result.method == "stored_importance"
        assert result.top_features[0].feature_name == "age"
