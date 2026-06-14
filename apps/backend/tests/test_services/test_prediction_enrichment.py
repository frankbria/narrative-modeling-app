"""Unit tests for PredictionEnricher (issue #83)."""

import pytest

from app.services.prediction_enrichment import PredictionEnricher


@pytest.fixture
def enricher() -> PredictionEnricher:
    return PredictionEnricher()


class TestPerRecordConfidence:
    def test_none_probabilities_returns_none_none(self, enricher):
        assert enricher.per_record_confidence(None) == (None, None)
        assert enricher.per_record_confidence([]) == (None, None)

    def test_scores_and_flags(self, enricher):
        scores, flags = enricher.per_record_confidence([[0.1, 0.9], [0.45, 0.55]])
        assert scores == pytest.approx([0.9, 0.55])
        assert flags == [False, True]  # 0.55 < 0.7 threshold

    def test_uncomputable_row_is_flagged_low(self, enricher):
        """An empty proba row → 0.0 confidence AND low_confidence=True (#83)."""
        scores, flags = enricher.per_record_confidence([[], [0.2, 0.8]])
        assert scores[0] == 0.0
        assert flags[0] is True  # never "0% but not flagged"
        assert flags[1] is False


class TestPredictionIntervals:
    def test_none_residual_std_returns_none(self, enricher):
        assert enricher.prediction_intervals([1.0, 2.0], None) is None

    def test_intervals_per_record(self, enricher):
        intervals = enricher.prediction_intervals([10.0], residual_std=2.0)
        low, high = intervals[0]
        assert low == pytest.approx(10.0 - 1.96 * 2.0)
        assert high == pytest.approx(10.0 + 1.96 * 2.0)


class TestExplanations:
    def test_returns_schema_objects_for_explainable_model(self, enricher):
        import numpy as np
        from sklearn.datasets import make_classification
        from sklearn.linear_model import LogisticRegression

        X, y = make_classification(
            n_samples=60, n_features=2, n_informative=2, n_redundant=0, random_state=0
        )
        model = LogisticRegression().fit(X, y)
        preds = model.predict(X[:2]).tolist()

        out = enricher.explanations(
            model, np.asarray(X[:2]), ["f1", "f2"], preds, "binary_classification"
        )
        assert out is not None and len(out) == 2
        assert out[0].method == "linear_coefficients"
        assert out[0].explanation_text
        assert out[0].top_features[0].feature_name in {"f1", "f2"}

    def test_unexplainable_model_returns_none(self, enricher):
        import numpy as np
        from sklearn.datasets import make_classification
        from sklearn.neighbors import KNeighborsClassifier

        X, y = make_classification(
            n_samples=60, n_features=2, n_informative=2, n_redundant=0, random_state=0
        )
        model = KNeighborsClassifier().fit(X, y)  # no coef_/feature_importances_

        # any_explained guard: not one row could be explained -> None, not [None]
        out = enricher.explanations(
            model, np.asarray(X[:2]), ["f1", "f2"], [0, 1], "binary_classification"
        )
        assert out is None
