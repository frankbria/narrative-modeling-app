"""Unit tests for ErrorAnalysisService (issue #81)."""

import numpy as np
import pytest

from app.services.error_analysis_service import (
    ErrorAnalysisData,
    ErrorAnalysisService,
)


@pytest.fixture
def service():
    return ErrorAnalysisService()


def _classification_fixture(n=200, seed=0):
    """Build a held-out set where errors concentrate at low feature_0."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3))
    y_true = np.where(x[:, 0] > 0, "A", "B")
    y_pred = y_true.copy()
    # Inject errors: flip ~60% of the low-feature_0 region (B) to A.
    low = np.where(x[:, 0] < -0.5)[0]
    flip = low[: int(len(low) * 0.6)]
    y_pred[flip] = "A"
    proba = np.zeros((n, 2))
    for i in range(n):
        p = 0.9 if y_pred[i] == "A" else 0.1
        proba[i] = [p, 1 - p]
    return x, y_true, y_pred, proba, ["A", "B"], ["feature_0", "feature_1", "feature_2"]


def test_distribution_counts_errors(service):
    x, yt, yp, proba, labels, names = _classification_fixture()
    data = service.analyze(
        problem_type="classification",
        y_test=yt, y_pred=yp, y_proba=proba, class_labels=labels,
        x_test=x, feature_names=names,
    )
    dist = data.distribution
    assert dist.total_samples == len(yt)
    assert dist.total_errors == int((yt != yp).sum())
    assert 0 < dist.overall_error_rate < 1
    assert set(dist.per_class_error_rate) == {"A", "B"}


def test_confusion_pairs_detects_b_predicted_as_a(service):
    x, yt, yp, proba, labels, names = _classification_fixture()
    data = service.analyze(
        problem_type="classification",
        y_test=yt, y_pred=yp, y_proba=proba, class_labels=labels,
        x_test=x, feature_names=names,
    )
    assert data.confusion_pairs
    top = data.confusion_pairs[0]
    assert (top.actual, top.predicted) == ("B", "A")
    assert top.count > 0
    assert 0 < top.rate <= 1


def test_segments_flag_high_error_feature_region(service):
    x, yt, yp, proba, labels, names = _classification_fixture()
    data = service.analyze(
        problem_type="classification",
        y_test=yt, y_pred=yp, y_proba=proba, class_labels=labels,
        x_test=x, feature_names=names,
    )
    assert data.segments
    # The injected errors live at low feature_0, so a feature_0 segment should rank.
    assert any(s.feature == "feature_0" for s in data.segments)
    assert all(s.error_rate > 0 for s in data.segments)


def test_patterns_extract_decision_rules(service):
    x, yt, yp, proba, labels, names = _classification_fixture()
    data = service.analyze(
        problem_type="classification",
        y_test=yt, y_pred=yp, y_proba=proba, class_labels=labels,
        x_test=x, feature_names=names,
    )
    assert data.patterns
    assert all("AND" in p.rule or "<=" in p.rule or ">" in p.rule for p in data.patterns)
    assert all(0 < p.error_rate <= 1 for p in data.patterns)


def test_clusters_group_errors(service):
    x, yt, yp, proba, labels, names = _classification_fixture()
    data = service.analyze(
        problem_type="classification",
        y_test=yt, y_pred=yp, y_proba=proba, class_labels=labels,
        x_test=x, feature_names=names,
    )
    assert data.clusters
    assert sum(c.size for c in data.clusters) == int((yt != yp).sum())


def test_cases_include_confidence_and_features(service):
    x, yt, yp, proba, labels, names = _classification_fixture()
    data = service.analyze(
        problem_type="classification",
        y_test=yt, y_pred=yp, y_proba=proba, class_labels=labels,
        x_test=x, feature_names=names, max_cases=5,
    )
    assert 0 < len(data.cases) <= 5
    case = data.cases[0]
    assert case.actual != case.predicted
    assert case.confidence is not None
    assert "feature_0" in case.top_features


def test_partial_without_feature_matrix(service):
    x, yt, yp, proba, labels, names = _classification_fixture()
    data = service.analyze(
        problem_type="classification",
        y_test=yt, y_pred=yp, y_proba=proba, class_labels=labels,
        x_test=None, feature_names=None,
    )
    assert data.has_feature_matrix is False
    assert data.distribution is not None
    assert data.confusion_pairs  # still works from y arrays
    assert data.segments == [] and data.clusters == [] and data.patterns == []
    assert data.cases  # cases work without features (no top_features)
    assert data.cases[0].top_features == {}


def test_no_errors_yields_empty_sections(service):
    x = np.random.default_rng(1).normal(size=(50, 2))
    yt = np.array(["A"] * 25 + ["B"] * 25)
    data = service.analyze(
        problem_type="classification",
        y_test=yt, y_pred=yt.copy(), y_proba=None, class_labels=["A", "B"],
        x_test=x, feature_names=["f0", "f1"],
    )
    assert data.distribution.total_errors == 0
    assert data.confusion_pairs == []
    assert data.cases == []
    assert data.patterns == []  # no errors -> single-class indicator


def test_regression_uses_residual_threshold(service):
    rng = np.random.default_rng(2)
    n = 200
    x = rng.normal(size=(n, 2))
    yt = x[:, 0] * 3.0
    yp = yt.copy()
    # Large errors for a region.
    big = np.where(x[:, 0] > 1.0)[0]
    yp[big] += 10.0
    data = service.analyze(
        problem_type="regression",
        y_test=yt, y_pred=yp, y_proba=None, class_labels=None,
        x_test=x, feature_names=["f0", "f1"],
    )
    assert data.distribution.total_errors > 0
    assert data.confusion_pairs == []  # N/A for regression
    assert data.cases
    assert data.cases[0].confidence is None


def test_analyze_never_raises_on_garbage(service):
    # Mismatched/garbage inputs must degrade, not raise.
    data = service.analyze(
        problem_type="classification",
        y_test=np.array(["A", "B"]),
        y_pred=np.array(["A"]),
        y_proba=None,
        class_labels=["A", "B"],
        x_test=[["not", "numeric"]],
        feature_names=["f0", "f1"],
    )
    assert isinstance(data, ErrorAnalysisData)


@pytest.mark.asyncio
async def test_fallback_suggestions_without_openai(service, monkeypatch):
    monkeypatch.setattr(service, "client", None)
    x, yt, yp, proba, labels, names = _classification_fixture()
    data = service.analyze(
        problem_type="classification",
        y_test=yt, y_pred=yp, y_proba=proba, class_labels=labels,
        x_test=x, feature_names=names,
    )
    suggestions, generated_by = await service.generate_suggestions(
        data, problem_type="classification", algorithm="Random Forest"
    )
    assert generated_by == "fallback"
    assert suggestions
    assert any("confuse" in s.lower() or "error" in s.lower() for s in suggestions)
