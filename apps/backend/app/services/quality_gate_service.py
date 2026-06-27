"""Soft quality gates for workflow progression (issue #102, AC4).

Stateless evaluator with sensible default thresholds. Gates are advisory only —
``is_blocking`` is always False so they warn but never block a user. No DB model,
no CRUD: thresholds live here as constants.
"""

from typing import Any

from app.schemas.quality import QualityGateResult
from app.services.data_processing.quality_assessment import SCORE_DIMENSIONS

# name -> (min overall 0-100, {dimension: min 0-100})
DEFAULT_GATES: dict[str, tuple[float, dict[str, float]]] = {
    "ML Training Ready": (70.0, {"completeness": 80.0, "validity": 70.0}),
}


def _component_scores(report: dict[str, Any]) -> dict[str, float]:
    """Extract per-dimension 0-100 scores, tolerating pre-#102 cached reports."""
    components = report.get("component_scores")
    if components:
        return {str(k): float(v) for k, v in components.items()}
    # Backward compat: derive from 0-1 dimension_scores.
    dim_scores = report.get("dimension_scores") or {}
    return {
        dim.value: round(float(dim_scores.get(dim.value, 0.0)) * 100, 1)
        for dim in SCORE_DIMENSIONS
        if dim.value in dim_scores
    }


def overall_score(report: dict[str, Any]) -> float:
    """0-100 overall score, tolerating pre-#102 cached reports."""
    if report.get("score_0_100") is not None:
        return float(report["score_0_100"])
    components = _component_scores(report)
    if components:
        return round(sum(components.values()) / len(components), 1)
    # Last resort: the legacy 0-1 overall score.
    return round(float(report.get("overall_quality_score", 0.0)) * 100, 1)


def evaluate_gates(report: dict[str, Any]) -> list[QualityGateResult]:
    """Evaluate all default soft gates against a quality report dict."""
    overall = overall_score(report)
    components = _component_scores(report)

    results: list[QualityGateResult] = []
    for name, (min_overall, min_dims) in DEFAULT_GATES.items():
        failing = [
            dim for dim, threshold in min_dims.items()
            if components.get(dim, 0.0) < threshold
        ]
        passed = overall >= min_overall and not failing
        results.append(
            QualityGateResult(
                gate_name=name,
                passed=passed,
                actual_score=overall,
                required_score=min_overall,
                failing_dimensions=failing,
                is_blocking=False,
            )
        )
    return results
