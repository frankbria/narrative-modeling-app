"""Unit tests for AIOrchestrationService rule engine (issue #89).

These exercise the deterministic core — recommendations, pipeline ordering,
parameter optimization, constraints — by passing an OrchestrationProfile
directly, so they need no database or OpenAI key.
"""

import os
from unittest.mock import patch

import pytest

from app.models.transformation import TransformationType
from app.schemas.ai_orchestration import (
    Objective,
    ParameterOptimizationRequest,
    ToolConstraints,
)
from app.services.ai_orchestration_service import (
    AIOrchestrationService,
    OrchestrationProfile,
)


def _service() -> AIOrchestrationService:
    # Force the no-key path so unit tests never touch OpenAI.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("OPENAI_API_KEY", None)
        return AIOrchestrationService()


def _profile(**kwargs) -> OrchestrationProfile:
    base = dict(
        dataset_id="ds_1",
        n_rows=1000,
        n_columns=4,
        numeric_columns=["age", "income"],
        categorical_columns=["city", "plan"],
        datetime_columns=["signup_date"],
        high_cardinality_columns=[],
    )
    base.update(kwargs)
    return OrchestrationProfile(**base)


def test_no_openai_key_uses_rule_based_only():
    svc = _service()
    assert svc.client is None


def test_cleaning_recommends_for_detected_issues():
    svc = _service()
    profile = _profile(
        columns_with_missing={"age": 0.1},
        detected_issue_types=["duplicates", "type_mismatch"],
        has_duplicates=True,
    )
    recs = svc._rule_recommendations(profile, Objective.DATA_CLEANING)
    tool_types = {r.tool_type for r in recs}
    assert TransformationType.REMOVE_DUPLICATES.value in tool_types
    assert TransformationType.FILL_MISSING.value in tool_types
    assert TransformationType.TO_NUMERIC.value in tool_types
    assert all(r.source == "rule_based" for r in recs)


def test_cleaning_drops_when_mostly_missing():
    svc = _service()
    profile = _profile(columns_with_missing={"notes": 0.9})
    recs = svc._rule_recommendations(profile, Objective.DATA_CLEANING)
    tool_types = {r.tool_type for r in recs}
    # Advisory column-drop (not the row-dropping drop_missing transform).
    assert "drop_columns" in tool_types
    assert TransformationType.FILL_MISSING.value not in tool_types


def test_cleaning_splits_drop_and_impute_by_threshold():
    """A mostly-empty column is dropped while a lightly-missing one is imputed.

    Regression for codex finding: drop must not sweep in lightly-missing columns.
    """
    svc = _service()
    profile = _profile(columns_with_missing={"notes": 0.9, "age": 0.05})
    recs = svc._rule_recommendations(profile, Objective.DATA_CLEANING)
    by_type = {r.tool_type: r for r in recs}
    assert by_type["drop_columns"].parameters["columns"] == ["notes"]
    assert by_type[TransformationType.FILL_MISSING.value].parameters["columns"] == ["age"]


def test_cleaning_imputes_categorical_with_mode():
    """Categorical missing values get mode, not median (codex: median is numeric-only)."""
    svc = _service()
    profile = _profile(
        numeric_columns=["age"],
        categorical_columns=["city"],
        columns_with_missing={"age": 0.1, "city": 0.1},
    )
    recs = svc._rule_recommendations(profile, Objective.DATA_CLEANING)
    fills = [r for r in recs if r.tool_type == TransformationType.FILL_MISSING.value]
    by_method = {r.parameters["method"]: r.parameters["columns"] for r in fills}
    assert by_method["median"] == ["age"]
    assert by_method["mode"] == ["city"]


def test_feature_engineering_encodes_by_cardinality():
    svc = _service()
    profile = _profile(
        categorical_columns=["city", "user_id"],
        high_cardinality_columns=["user_id"],
    )
    recs = svc._rule_recommendations(profile, Objective.FEATURE_ENGINEERING)
    tool_types = {r.tool_type for r in recs}
    assert TransformationType.ONE_HOT_ENCODE.value in tool_types  # low-card "city"
    assert TransformationType.LABEL_ENCODE.value in tool_types  # high-card "user_id"
    assert TransformationType.STANDARDIZE.value in tool_types  # numeric present
    assert TransformationType.EXTRACT_DATE_PARTS.value in tool_types  # datetime present


def test_modeling_recs_scale_with_dataset_size():
    svc = _service()
    small = svc._rule_recommendations(_profile(n_rows=500), Objective.MODELING)
    large = svc._rule_recommendations(_profile(n_rows=50000), Objective.MODELING)
    assert "train_model" in {r.tool_type for r in small}
    assert "random_forest" in {r.tool_type for r in small}
    assert "lightgbm" in {r.tool_type for r in large}


def test_exploration_recs_flag_quality_gaps():
    svc = _service()
    recs = svc._rule_recommendations(
        _profile(columns_with_missing={"age": 0.2}), Objective.EXPLORATION
    )
    assert "missing_value_report" in {r.tool_type for r in recs}


def test_pipeline_orders_cleaning_before_modeling():
    svc = _service()
    profile = _profile(
        columns_with_missing={"age": 0.1},
        detected_issue_types=["duplicates"],
        has_duplicates=True,
    )
    recs = svc._cleaning_recs(profile) + svc._modeling_recs(profile)
    pipeline = svc._build_pipeline(recs)
    assert pipeline.index(TransformationType.REMOVE_DUPLICATES.value) < pipeline.index(
        "train_model"
    )
    # one-hot (stage 5) comes before scaling order is internal; just check no dupes
    assert len(pipeline) == len(set(pipeline))


def test_interpretability_constraint_boosts_interpretable_tools():
    svc = _service()
    recs = svc._modeling_recs(_profile(n_rows=50000))
    lgbm_before = next(r.priority for r in recs if r.tool_type == "lightgbm")
    trace: list[str] = []
    svc._apply_constraints(
        recs, ToolConstraints(interpretability_preference="high"), trace
    )
    lgbm_after = next(r.priority for r in recs if r.tool_type == "lightgbm")
    assert lgbm_after < lgbm_before
    assert trace


@pytest.mark.asyncio
async def test_optimize_imputation_defaults_to_median():
    svc = _service()
    resp = await svc.optimize_parameters(
        _profile(),
        ParameterOptimizationRequest(
            dataset_id="ds_1", tool_type=TransformationType.FILL_MISSING.value
        ),
    )
    assert resp.optimized_parameters["method"] == "median"
    assert any(a.parameters.get("method") == "mode" for a in resp.alternatives)


@pytest.mark.asyncio
async def test_optimize_imputation_uses_mode_for_requested_categorical():
    """A non-numeric requested column gets mode, not median (codex)."""
    svc = _service()
    resp = await svc.optimize_parameters(
        _profile(numeric_columns=["age"], categorical_columns=["city"]),
        ParameterOptimizationRequest(
            dataset_id="ds_1",
            tool_type=TransformationType.FILL_MISSING.value,
            current_parameters={"columns": ["city"]},
        ),
    )
    assert resp.optimized_parameters["method"] == "mode"


@pytest.mark.asyncio
async def test_optimize_onehot_respects_requested_low_card_columns():
    """One-hot for a low-card column isn't flipped to label by an unrelated
    high-card column elsewhere in the dataset (codex)."""
    svc = _service()
    resp = await svc.optimize_parameters(
        _profile(categorical_columns=["city", "user_id"], high_cardinality_columns=["user_id"]),
        ParameterOptimizationRequest(
            dataset_id="ds_1",
            tool_type=TransformationType.ONE_HOT_ENCODE.value,
            current_parameters={"columns": ["city"]},
        ),
    )
    assert resp.optimized_parameters["method"] == "onehot"


@pytest.mark.asyncio
async def test_optimize_scaling_uses_robust_when_outliers():
    svc = _service()
    resp = await svc.optimize_parameters(
        _profile(has_outliers=True),
        ParameterOptimizationRequest(
            dataset_id="ds_1", tool_type=TransformationType.STANDARDIZE.value
        ),
    )
    assert resp.optimized_parameters["method"] == "robust"


@pytest.mark.asyncio
async def test_optimize_encoding_uses_label_for_high_cardinality():
    svc = _service()
    resp = await svc.optimize_parameters(
        _profile(high_cardinality_columns=["user_id"]),
        ParameterOptimizationRequest(
            dataset_id="ds_1", tool_type=TransformationType.ONE_HOT_ENCODE.value
        ),
    )
    assert resp.optimized_parameters["method"] == "label"


@pytest.mark.asyncio
async def test_optimize_unknown_tool_echoes_params():
    svc = _service()
    resp = await svc.optimize_parameters(
        _profile(),
        ParameterOptimizationRequest(
            dataset_id="ds_1", tool_type="some_unknown_tool", current_parameters={"k": 1}
        ),
    )
    assert resp.optimized_parameters == {"k": 1}
    assert "No specific parameter heuristics" in resp.explanation
