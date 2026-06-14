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
