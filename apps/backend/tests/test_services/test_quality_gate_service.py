"""Tests for soft quality gates (issue #102, AC4)."""

from app.services.quality_gate_service import (
    DEFAULT_GATES,
    evaluate_gates,
    overall_score,
)


def _report(score=85.0, completeness=90.0, validity=80.0):
    return {
        "score_0_100": score,
        "component_scores": {
            "completeness": completeness,
            "validity": validity,
            "consistency": 95.0,
            "uniqueness": 100.0,
            "accuracy": 80.0,
        },
        "critical_issues": [],
        "warnings": [],
    }


class TestQualityGates:
    def test_gate_passes_for_high_quality(self):
        results = evaluate_gates(_report())
        assert len(results) == len(DEFAULT_GATES)
        gate = results[0]
        assert gate.passed is True
        assert gate.failing_dimensions == []
        assert gate.is_blocking is False  # soft gate, always

    def test_gate_fails_on_low_overall(self):
        gate = evaluate_gates(_report(score=50.0))[0]
        assert gate.passed is False
        assert gate.actual_score == 50.0
        assert gate.required_score == 70.0

    def test_gate_reports_failing_dimensions(self):
        gate = evaluate_gates(_report(completeness=60.0))[0]
        assert gate.passed is False
        assert "completeness" in gate.failing_dimensions

    def test_gates_are_never_blocking(self):
        for gate in evaluate_gates(_report(score=10.0, completeness=10.0)):
            assert gate.is_blocking is False

    def test_backward_compat_pre_102_report(self):
        """Pre-#102 report (no score_0_100/component_scores) derives from 0-1 dims."""
        legacy = {
            "overall_quality_score": 0.9,
            "dimension_scores": {
                "completeness": 0.9,
                "validity": 0.8,
                "consistency": 0.95,
                "uniqueness": 1.0,
                "accuracy": 0.8,
            },
        }
        assert overall_score(legacy) > 0  # derived, not zero
        gate = evaluate_gates(legacy)[0]
        assert gate.passed is True

    def test_overall_score_last_resort_legacy_scalar(self):
        assert overall_score({"overall_quality_score": 0.75}) == 75.0
