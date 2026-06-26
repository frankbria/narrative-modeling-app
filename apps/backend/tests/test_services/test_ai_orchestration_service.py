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
    WorkflowStageId,
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


@pytest.mark.asyncio
async def test_ai_summary_falls_back_gracefully_on_bad_openai_response():
    """A non-JSON / malformed OpenAI response degrades to None, never raising."""
    from unittest.mock import AsyncMock, MagicMock

    svc = _service()
    svc.client = MagicMock()  # pretend a key is configured

    profile = _profile()
    recs = svc._modeling_recs(profile)

    # _openai_summary raising (bad parse, empty choices, etc.) must be swallowed.
    with patch.object(svc, "_openai_summary", new=AsyncMock(side_effect=ValueError("bad json"))):
        result = await svc._maybe_ai_summary(profile, Objective.MODELING, recs)
    assert result is None


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


def test_interpretability_low_constraint_boosts_complex_models():
    svc = _service()
    recs = svc._modeling_recs(_profile(n_rows=50000))
    lgbm_before = next(r.priority for r in recs if r.tool_type == "lightgbm")
    trace: list[str] = []
    svc._apply_constraints(
        recs, ToolConstraints(interpretability_preference="low"), trace
    )
    lgbm_after = next(r.priority for r in recs if r.tool_type == "lightgbm")
    assert lgbm_after > lgbm_before
    assert trace


def test_time_budget_fast_demotes_slow_automl():
    svc = _service()
    recs = svc._modeling_recs(_profile(n_rows=500))
    train_before = next(r.priority for r in recs if r.tool_type == "train_model")
    trace: list[str] = []
    svc._apply_constraints(recs, ToolConstraints(time_budget="fast"), trace)
    train_after = next(r.priority for r in recs if r.tool_type == "train_model")
    assert train_after < train_before
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


# --------------------------------------------------------------- stage guidance (#90)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", list(WorkflowStageId))
async def test_stage_guidance_all_stages_rule_based(stage):
    """Every one of the 8 stages yields focus + considerations + actions, no key."""
    svc = _service()
    resp = await svc.generate_stage_guidance(_profile(), stage, None, "u1")
    assert resp.stage == stage
    assert resp.focus
    assert resp.guidance_summary
    assert resp.key_considerations
    assert resp.suggested_actions
    assert resp.generated_by == "rule_based"


@pytest.mark.asyncio
async def test_deployment_guidance_is_the_filled_gap():
    """Stage 8 (no prior AI) gets real deployment strategy + monitoring + checklist."""
    svc = _service()
    resp = await svc.generate_stage_guidance(_profile(), WorkflowStageId.DEPLOYMENT, None, "u1")
    blob = " ".join(resp.key_considerations + resp.suggested_actions).lower()
    assert "monitor" in blob
    assert "rollback" in blob or "version" in blob
    assert any("checklist" in a.lower() or "smoke" in a.lower() for a in resp.suggested_actions)


@pytest.mark.asyncio
async def test_deployment_real_time_vs_batch_heuristic():
    svc = _service()
    small = await svc.generate_stage_guidance(
        _profile(n_rows=1000), WorkflowStageId.DEPLOYMENT, None, "u1"
    )
    large = await svc.generate_stage_guidance(
        _profile(n_rows=500_000), WorkflowStageId.DEPLOYMENT, None, "u1"
    )
    assert "real-time" in small.key_considerations[0].lower()
    assert "batch" in large.key_considerations[0].lower()


@pytest.mark.asyncio
async def test_stage_guidance_accumulates_caller_context():
    """Explicit accumulated_context is threaded into context_used (AC3)."""
    svc = _service()
    resp = await svc.generate_stage_guidance(
        _profile(),
        WorkflowStageId.MODEL_TRAINING,
        {"target_column": "churn", "problem_type": "classification"},
        "u1",
    )
    joined = " ".join(resp.context_used)
    assert "target_column" in joined and "churn" in joined
    assert any("accumulated_context" in t for t in resp.reasoning_trace)
    # The rule-based (no-key) path must visibly fold the context into the guidance,
    # not just echo it in context_used (codex P2): a leading consideration cites it.
    assert "churn" in resp.key_considerations[0]
    baseline = await svc.generate_stage_guidance(
        _profile(), WorkflowStageId.MODEL_TRAINING, None, "u1"
    )
    assert resp.key_considerations != baseline.key_considerations


def test_summarize_decision_caps_length_and_handles_types():
    svc = _service()
    assert svc._summarize_decision({"a": 1, "b": 2}) == "a=1, b=2"
    assert svc._summarize_decision(["x", "y"]) == "x, y"
    assert len(svc._summarize_decision("z" * 500)) == 160


def test_data_preparation_guidance_reflects_detected_issues():
    svc = _service()
    clean, _ = svc._stage_rule_guidance(
        WorkflowStageId.DATA_PREPARATION, _profile(has_duplicates=False)
    )
    dirty, _ = svc._stage_rule_guidance(
        WorkflowStageId.DATA_PREPARATION,
        _profile(has_duplicates=True, columns_with_missing={"age": 0.3}),
    )
    assert any("duplicate" in c.lower() for c in dirty)
    # Clean profile still returns guidance (no crash, sensible default).
    assert clean
