"""AI decision engine for tool selection and parameter optimization (issue #89).

A single cohesive service (mirrors EvaluationExplanationService): rule-based
heuristics are the backbone — the engine works fully with NO OpenAI key — and an
optional OpenAI pass enhances the plain-language summary when a key is present.

Deliberately lean vs the CodeRabbit plan: one module instead of seven, heuristics
encoded inline instead of an external practices.json/KnowledgeBase, simple
feedback-count personalization instead of a learning loop. See tasks/todo.md.
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, cast

from openai import OpenAI, OpenAIError

from app.models.ai_feedback import AIRecommendationFeedback
from app.models.data_issue import DataIssueRecord
from app.models.dataset import DatasetMetadata
from app.models.transformation import TransformationType
from app.models.workflow import WorkflowState
from app.schemas.ai_orchestration import (
    AIFeedbackRequest,
    Objective,
    ParameterAlternative,
    ParameterOptimizationRequest,
    ParameterOptimizationResponse,
    StageGuidanceResponse,
    ToolConstraints,
    ToolRecommendation,
    ToolRecommendationRequest,
    ToolRecommendationResponse,
    WorkflowStageId,
)
from app.utils.circuit_breaker import with_circuit_breaker

logger = logging.getLogger(__name__)

# Shared AI personality so guidance reads consistently across every stage (#90).
AI_MENTOR_PERSONA = (
    "You are a friendly, plain-spoken data-science mentor for a non-expert analyst. "
    "You are encouraging and educational without being condescending, you prefer "
    "concrete next steps over jargon, and you build on the decisions the user has "
    "already made earlier in their workflow."
)

# One-line focus per workflow stage (the consistent framing for stage guidance).
_STAGE_FOCUS: dict[str, str] = {
    WorkflowStageId.DATA_LOADING.value: "Getting clean, well-typed data into the workflow",
    WorkflowStageId.DATA_PROFILING.value: "Understanding your data's shape, quality, and relationships",
    WorkflowStageId.DATA_PREPARATION.value: "Cleaning and fixing data-quality issues before modelling",
    WorkflowStageId.FEATURE_ENGINEERING.value: "Turning raw columns into informative model inputs",
    WorkflowStageId.MODEL_TRAINING.value: "Choosing and training the right algorithm for your data",
    WorkflowStageId.MODEL_EVALUATION.value: "Reading the results and judging if the model is good enough",
    WorkflowStageId.PREDICTION.value: "Making and trusting predictions on new data",
    WorkflowStageId.DEPLOYMENT.value: "Shipping the model as a reliable, monitored service",
}

# Canonical execution order used to assemble multi-stage pipelines. Lower rank
# runs earlier. tool_types not listed sort last (modeling/exploration extras).
_STAGE_ORDER: dict[str, int] = {
    "drop_columns": 0,  # advisory column removal — earliest
    TransformationType.REMOVE_DUPLICATES.value: 0,
    TransformationType.TRIM_WHITESPACE.value: 1,
    TransformationType.FIX_CASING.value: 1,
    TransformationType.TO_NUMERIC.value: 2,
    TransformationType.TO_DATETIME.value: 2,
    TransformationType.IMPUTE_MEDIAN.value: 3,
    TransformationType.IMPUTE_MEAN.value: 3,
    TransformationType.FILL_MISSING.value: 3,
    TransformationType.DROP_MISSING.value: 3,
    TransformationType.EXTRACT_DATE_PARTS.value: 4,
    TransformationType.ONE_HOT_ENCODE.value: 5,
    TransformationType.LABEL_ENCODE.value: 5,
    TransformationType.STANDARDIZE.value: 6,
    TransformationType.SCALE.value: 6,
    TransformationType.NORMALIZE.value: 6,
    "train_model": 7,
}


@dataclass
class OrchestrationProfile:
    """Lightweight aggregate of dataset metadata used for decisions."""

    dataset_id: str
    n_rows: int = 0
    n_columns: int = 0
    numeric_columns: list[str] = field(default_factory=list)
    categorical_columns: list[str] = field(default_factory=list)
    datetime_columns: list[str] = field(default_factory=list)
    high_cardinality_columns: list[str] = field(default_factory=list)
    constant_columns: list[str] = field(default_factory=list)
    columns_with_missing: dict[str, float] = field(default_factory=dict)
    detected_issue_types: list[str] = field(default_factory=list)
    has_duplicates: bool = False
    has_outliers: bool = False
    is_processed: bool = False
    # True when the dataset exists but has thin/missing profiling metadata.
    partial: bool = False

    def summary_text(self) -> str:
        parts = [
            f"{self.n_rows} rows x {self.n_columns} columns",
            f"{len(self.numeric_columns)} numeric",
            f"{len(self.categorical_columns)} categorical",
        ]
        if self.datetime_columns:
            parts.append(f"{len(self.datetime_columns)} datetime")
        if self.columns_with_missing:
            parts.append(f"{len(self.columns_with_missing)} column(s) with missing values")
        if self.high_cardinality_columns:
            parts.append(f"{len(self.high_cardinality_columns)} high-cardinality column(s)")
        if self.detected_issue_types:
            parts.append("detected issues: " + ", ".join(sorted(set(self.detected_issue_types))))
        return "; ".join(parts)


class AIOrchestrationService:
    """Hybrid rule-based + optional-OpenAI recommendation engine. Never raises."""

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning(
                "OPENAI_API_KEY not set - AI orchestration will use the rule-based engine only"
            )
            self.client: OpenAI | None = None
        else:
            self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo")

    # ------------------------------------------------------------------ profile
    async def build_profile(self, dataset_id: str, user_id: str) -> OrchestrationProfile | None:
        """Aggregate dataset metadata into a profile.

        Returns None when the dataset does not exist or is not owned by the user
        (the route turns that into a 404). A found-but-thin dataset returns a
        profile with partial=True.
        """
        dataset = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == dataset_id,
            DatasetMetadata.user_id == user_id,
        )
        if dataset is None:
            return None

        profile = OrchestrationProfile(
            dataset_id=dataset_id,
            n_rows=dataset.num_rows,
            n_columns=dataset.num_columns,
            is_processed=dataset.is_processed,
        )

        for fld in dataset.data_schema:
            name = fld.field_name
            if fld.field_type == "numeric":
                profile.numeric_columns.append(name)
            elif fld.field_type == "datetime":
                profile.datetime_columns.append(name)
            else:  # text, categorical, boolean -> treated as categorical for encoding
                profile.categorical_columns.append(name)
            if fld.is_high_cardinality:
                profile.high_cardinality_columns.append(name)
            if fld.is_constant:
                profile.constant_columns.append(name)
            if fld.missing_values > 0 and dataset.num_rows > 0:
                profile.columns_with_missing[name] = fld.missing_values / dataset.num_rows

        # The /api/v1/datasets upload path stores data_schema=[] and puts the real
        # column metadata in inferred_schema — fall back to it so that common path
        # gets real recommendations, not partial/generic ones (codex).
        if not dataset.data_schema and dataset.inferred_schema:
            self._hydrate_from_inferred(profile, dataset.inferred_schema, dataset.num_rows)

        # Fold in detected data issues (best-effort).
        try:
            # Newest detection run wins — store_detection_results inserts a fresh
            # record each time, so an unsorted find_one can read stale results.
            issue_record = (
                await DataIssueRecord.find(
                    DataIssueRecord.dataset_id == dataset_id,
                    DataIssueRecord.user_id == user_id,
                )
                .sort("-detected_at")
                .first_or_none()
            )
            if issue_record is not None:
                profile.detected_issue_types = [i.issue_type.value for i in issue_record.issues]
                profile.has_duplicates = any(
                    t == "duplicates" for t in profile.detected_issue_types
                )
                profile.has_outliers = any(
                    t == "outliers" for t in profile.detected_issue_types
                )
        except Exception:  # pragma: no cover - defensive; issues are optional
            logger.debug("Could not load data issues for %s", dataset_id, exc_info=True)

        profile.partial = not (
            profile.numeric_columns
            or profile.categorical_columns
            or profile.datetime_columns
        )
        return profile

    # inferred_schema (SchemaInference) data_type -> profile bucket mapping
    _INFERRED_NUMERIC = {"integer", "float", "currency", "percentage"}
    _INFERRED_DATETIME = {"date", "datetime", "time"}
    _INFERRED_HIGH_CARD_THRESHOLD = 50

    @classmethod
    def _hydrate_from_inferred(
        cls, profile: OrchestrationProfile, inferred_schema: dict[str, Any], n_rows: int
    ) -> None:
        """Populate the profile from a SchemaInference dump (inferred_schema)."""
        for col in inferred_schema.get("columns") or []:
            name = col.get("name")
            if not name:
                continue
            dtype = str(col.get("data_type", "")).lower()
            is_numeric = dtype in cls._INFERRED_NUMERIC
            if is_numeric:
                profile.numeric_columns.append(name)
            elif dtype in cls._INFERRED_DATETIME:
                profile.datetime_columns.append(name)
            else:
                profile.categorical_columns.append(name)
            cardinality = col.get("cardinality") or 0
            if not is_numeric and cardinality > cls._INFERRED_HIGH_CARD_THRESHOLD:
                profile.high_cardinality_columns.append(name)
            if cardinality == 1:
                profile.constant_columns.append(name)
            null_count = col.get("null_count") or 0
            if null_count > 0 and n_rows > 0:
                profile.columns_with_missing[name] = null_count / n_rows

    # -------------------------------------------------------------- recommend
    async def recommend_tools(
        self,
        profile: OrchestrationProfile,
        request: ToolRecommendationRequest,
        user_id: str,
    ) -> ToolRecommendationResponse:
        """Produce ranked tool recommendations + an ordered pipeline suggestion."""
        reasoning_trace: list[str] = [
            f"Built profile for dataset {profile.dataset_id}: {profile.summary_text()}"
        ]
        recs = self._rule_recommendations(profile, request.objective)
        reasoning_trace.append(
            f"Rule-based engine produced {len(recs)} recommendation(s) for "
            f"objective '{request.objective.value}'."
        )

        if request.constraints:
            recs = self._apply_constraints(recs, request.constraints, reasoning_trace)

        personalization_applied = await self._personalize(recs, user_id, reasoning_trace)

        # Optional OpenAI enhancement of the narrative summary (never required).
        generated_by = "rule_based"
        summary = profile.summary_text()
        ai_summary = await self._maybe_ai_summary(profile, request.objective, recs)
        if ai_summary:
            summary = ai_summary
            generated_by = "hybrid"
            reasoning_trace.append("OpenAI enhanced the plain-language profile summary.")

        recs.sort(key=lambda r: r.priority, reverse=True)
        pipeline = self._build_pipeline(recs)

        return ToolRecommendationResponse(
            dataset_id=profile.dataset_id,
            objective=request.objective,
            recommendations=recs,
            pipeline_suggestion=pipeline,
            data_profile_summary=summary,
            reasoning_trace=reasoning_trace,
            personalization_applied=personalization_applied,
            generated_by=generated_by,
            partial=profile.partial,
        )

    def _rule_recommendations(
        self, profile: OrchestrationProfile, objective: Objective
    ) -> list[ToolRecommendation]:
        if objective == Objective.DATA_CLEANING:
            return self._cleaning_recs(profile)
        if objective == Objective.FEATURE_ENGINEERING:
            return self._feature_recs(profile)
        if objective == Objective.MODELING:
            return self._modeling_recs(profile)
        return self._exploration_recs(profile)

    def _cleaning_recs(self, profile: OrchestrationProfile) -> list[ToolRecommendation]:
        recs: list[ToolRecommendation] = []
        if profile.has_duplicates:
            recs.append(
                self._rec(
                    TransformationType.REMOVE_DUPLICATES.value,
                    priority=9,
                    confidence=0.9,
                    explanation="Duplicate rows were detected; removing them prevents "
                    "double-counting and leakage between train and test splits.",
                    pros=["Cleaner data", "Avoids inflated metrics"],
                    cons=["Irreversible row loss"],
                    estimated_impact="Removes repeated records",
                )
            )
        if profile.columns_with_missing:
            # Split by missing rate so lightly-missing columns are imputed, not
            # dropped alongside the mostly-empty ones (codex review).
            drop_cols = sorted(
                c for c, frac in profile.columns_with_missing.items() if frac > 0.5
            )
            impute_cols = sorted(
                c for c, frac in profile.columns_with_missing.items() if frac <= 0.5
            )
            if drop_cols:
                # Advisory, not an executable drop_missing: that transform drops
                # ROWS (and is rejected past 50% row loss), which would nuke the
                # dataset for a mostly-empty column. Removing the column is a
                # manual/column-level step, so flag it rather than emit a bogus
                # executable recommendation (codex).
                recs.append(
                    self._rec(
                        "drop_columns",
                        priority=8,
                        confidence=0.7,
                        explanation=f"{len(drop_cols)} column(s) are over 50% empty; imputing "
                        "that much fabricates signal, so consider removing these columns.",
                        parameters={"columns": drop_cols},
                        pros=["Avoids fabricated values"],
                        cons=["Manual column removal (not an automated row-drop)"],
                        estimated_impact="Drops mostly-empty columns",
                    )
                )
            # Split by type: median only works on numeric columns; categorical/text
            # need mode, else FillMissingTransformation silently skips them (codex).
            numeric_set = set(profile.numeric_columns)
            numeric_impute = [c for c in impute_cols if c in numeric_set]
            other_impute = [c for c in impute_cols if c not in numeric_set]
            if numeric_impute:
                recs.append(
                    self._rec(
                        # Executable contract: engine maps FILL_MISSING (not IMPUTE_*).
                        TransformationType.FILL_MISSING.value,
                        priority=8,
                        confidence=0.8,
                        explanation=f"{len(numeric_impute)} numeric column(s) have some missing "
                        "values; median imputation fills gaps robustly without dropping rows.",
                        parameters={"columns": numeric_impute, "method": "median"},
                        pros=["Keeps all rows", "Robust to skew/outliers"],
                        cons=["Reduces variance slightly"],
                        estimated_impact="Fills missing numeric values",
                    )
                )
            if other_impute:
                recs.append(
                    self._rec(
                        TransformationType.FILL_MISSING.value,
                        priority=7,
                        confidence=0.75,
                        explanation=f"{len(other_impute)} categorical/text column(s) have some "
                        "missing values; filling with the most frequent value keeps all rows.",
                        parameters={"columns": other_impute, "method": "mode"},
                        pros=["Keeps all rows", "Works on non-numeric columns"],
                        cons=["Over-represents the most common category"],
                        estimated_impact="Fills missing categorical values",
                    )
                )
        if any(
            t in ("type_mismatch", "numeric_string_mismatch")
            for t in profile.detected_issue_types
        ):
            recs.append(
                self._rec(
                    TransformationType.TO_NUMERIC.value,
                    priority=7,
                    confidence=0.75,
                    explanation="Numeric values are stored as text; converting them lets the "
                    "model treat them as numbers instead of categories.",
                    pros=["Correct dtypes"],
                    cons=["Unparseable values become missing"],
                    estimated_impact="Fixes numeric-as-text columns",
                )
            )
        if any(
            t in ("whitespace_issues", "inconsistent_casing")
            for t in profile.detected_issue_types
        ):
            recs.append(
                self._rec(
                    TransformationType.TRIM_WHITESPACE.value,
                    priority=5,
                    confidence=0.7,
                    explanation="Inconsistent whitespace/casing was detected; normalizing it "
                    "merges values that should be identical.",
                    pros=["Consolidates categories"],
                    cons=[],
                    estimated_impact="Normalizes text values",
                )
            )
        if not recs:
            recs.append(
                self._rec(
                    TransformationType.REMOVE_DUPLICATES.value,
                    priority=4,
                    confidence=0.5,
                    explanation="No major issues detected. A duplicate check is still a cheap, "
                    "safe first cleaning step.",
                    pros=["Low risk"],
                    cons=[],
                    estimated_impact="Sanity cleaning pass",
                )
            )
        return recs

    def _feature_recs(self, profile: OrchestrationProfile) -> list[ToolRecommendation]:
        recs: list[ToolRecommendation] = []
        low_card = [c for c in profile.categorical_columns if c not in profile.high_cardinality_columns]
        if low_card:
            recs.append(
                self._rec(
                    TransformationType.ONE_HOT_ENCODE.value,
                    priority=8,
                    confidence=0.85,
                    explanation=f"{len(low_card)} low-cardinality categorical column(s) are best "
                    "one-hot encoded so the model sees each category independently.",
                    parameters={"columns": sorted(low_card)},
                    pros=["No false ordering", "Works with linear models"],
                    cons=["Adds columns"],
                    estimated_impact="Encodes categoricals for modeling",
                )
            )
        if profile.high_cardinality_columns:
            recs.append(
                self._rec(
                    TransformationType.LABEL_ENCODE.value,
                    priority=6,
                    confidence=0.65,
                    explanation=f"{len(profile.high_cardinality_columns)} high-cardinality "
                    "column(s) would explode under one-hot; label encoding keeps width small.",
                    parameters={"columns": sorted(profile.high_cardinality_columns)},
                    pros=["Compact"],
                    cons=["Implies an ordering tree models tolerate but linear ones don't"],
                    estimated_impact="Encodes high-cardinality categoricals",
                )
            )
        if profile.numeric_columns:
            recs.append(
                self._rec(
                    TransformationType.STANDARDIZE.value,
                    priority=7,
                    confidence=0.8,
                    explanation=f"{len(profile.numeric_columns)} numeric column(s) on different "
                    "scales; standardizing helps distance- and gradient-based models.",
                    parameters={"columns": sorted(profile.numeric_columns)},
                    pros=["Comparable scales"],
                    cons=["Not needed for tree models"],
                    estimated_impact="Scales numeric features",
                )
            )
        if profile.datetime_columns:
            recs.append(
                self._rec(
                    TransformationType.EXTRACT_DATE_PARTS.value,
                    priority=6,
                    confidence=0.75,
                    explanation=f"{len(profile.datetime_columns)} datetime column(s) carry "
                    "signal (month, weekday) the model can't use until extracted.",
                    parameters={"columns": sorted(profile.datetime_columns)},
                    pros=["Exposes seasonality"],
                    cons=[],
                    estimated_impact="Derives date-part features",
                )
            )
        if not recs:
            recs.append(
                self._rec(
                    TransformationType.STANDARDIZE.value,
                    priority=4,
                    confidence=0.5,
                    explanation="No obvious feature engineering needed; standardizing numeric "
                    "features is a safe default.",
                    pros=["Low risk"],
                    cons=[],
                    estimated_impact="Baseline scaling",
                )
            )
        return recs

    def _modeling_recs(self, profile: OrchestrationProfile) -> list[ToolRecommendation]:
        small = profile.n_rows < 5000
        recs = [
            self._rec(
                "train_model",
                priority=9,
                confidence=0.85,
                explanation="Run AutoML training, which compares several algorithms and picks "
                "the best for this dataset.",
                parameters={"strategy": "automl"},
                pros=["Compares many algorithms", "No manual tuning"],
                cons=["Slower than a single model"],
                estimated_impact="Produces a trained, ranked model",
            )
        ]
        if small:
            recs.append(
                self._rec(
                    "random_forest",
                    priority=7,
                    confidence=0.7,
                    explanation="With a smaller dataset, Random Forest is a strong, low-tuning "
                    "baseline that resists overfitting.",
                    pros=["Robust", "Handles mixed features"],
                    cons=["Less interpretable than linear models"],
                    estimated_impact="Solid baseline accuracy",
                )
            )
            recs.append(
                self._rec(
                    "logistic_regression",
                    priority=6,
                    confidence=0.6,
                    explanation="A linear model is fast and highly interpretable — a good "
                    "reference point on smaller data.",
                    pros=["Interpretable", "Fast"],
                    cons=["Misses non-linear patterns"],
                    estimated_impact="Interpretable baseline",
                )
            )
        else:
            recs.append(
                self._rec(
                    "lightgbm",
                    priority=8,
                    confidence=0.75,
                    explanation="On larger data, gradient boosting (LightGBM) usually gives the "
                    "best accuracy and trains efficiently.",
                    pros=["High accuracy", "Scales well"],
                    cons=["More hyperparameters"],
                    estimated_impact="Top-tier accuracy on large data",
                )
            )
        return recs

    def _exploration_recs(self, profile: OrchestrationProfile) -> list[ToolRecommendation]:
        recs = [
            self._rec(
                "correlation_analysis",
                priority=7,
                confidence=0.8,
                explanation="Review feature correlations to spot redundant columns and likely "
                "predictors before modeling.",
                pros=["Finds relationships"],
                cons=[],
                estimated_impact="Reveals feature relationships",
            ),
            self._rec(
                "distribution_plots",
                priority=6,
                confidence=0.75,
                explanation="Plot distributions of numeric columns to catch skew and outliers "
                "early.",
                parameters={"columns": sorted(profile.numeric_columns)},
                pros=["Catches skew/outliers"],
                cons=[],
                estimated_impact="Surfaces data shape issues",
            ),
        ]
        if profile.columns_with_missing or profile.detected_issue_types:
            recs.append(
                self._rec(
                    "missing_value_report",
                    priority=8,
                    confidence=0.85,
                    explanation="This dataset has data-quality gaps; a missingness report shows "
                    "where to focus cleaning first.",
                    pros=["Prioritizes cleaning"],
                    cons=[],
                    estimated_impact="Maps data-quality gaps",
                )
            )
        return recs

    # ----------------------------------------------------------- pipeline/util
    @staticmethod
    def _rec(
        tool_type: str,
        *,
        priority: int,
        confidence: float,
        explanation: str,
        parameters: dict[str, Any] | None = None,
        pros: list[str] | None = None,
        cons: list[str] | None = None,
        estimated_impact: str = "",
        source: str = "rule_based",
    ) -> ToolRecommendation:
        return ToolRecommendation(
            recommendation_id=f"rec_{uuid.uuid4().hex[:12]}",
            tool_type=tool_type,
            priority=priority,
            confidence=confidence,
            explanation=explanation,
            parameters=parameters or {},
            pros=pros or [],
            cons=cons or [],
            estimated_impact=estimated_impact,
            source=source,
        )

    @staticmethod
    def _build_pipeline(recs: list[ToolRecommendation]) -> list[str]:
        """Order recommended tool_types into a coherent multi-stage pipeline."""
        seen: set[str] = set()
        ordered = sorted(
            recs,
            # tool_type tertiary key -> deterministic order when stage+priority tie.
            key=lambda r: (_STAGE_ORDER.get(r.tool_type, 99), -r.priority, r.tool_type),
        )
        pipeline: list[str] = []
        for r in ordered:
            if r.tool_type not in seen:
                seen.add(r.tool_type)
                pipeline.append(r.tool_type)
        return pipeline

    @staticmethod
    def _apply_constraints(
        recs: list[ToolRecommendation],
        constraints: ToolConstraints,
        trace: list[str],
    ) -> list[ToolRecommendation]:
        def adjust(recs: list[ToolRecommendation], up: set[str], down: set[str]) -> None:
            for r in recs:
                if r.tool_type in up:
                    r.priority = min(10, r.priority + 1)
                elif r.tool_type in down:
                    r.priority = max(1, r.priority - 1)

        interpretable = {"logistic_regression", "random_forest", TransformationType.LABEL_ENCODE.value}
        complex_models = {"lightgbm", "xgboost"}

        pref = (constraints.interpretability_preference or "").lower()
        if pref == "high":
            adjust(recs, interpretable, complex_models)
            trace.append("Applied interpretability=high constraint.")
        elif pref == "low":
            adjust(recs, complex_models, interpretable)
            trace.append("Applied interpretability=low constraint (favoring accuracy).")

        budget = (constraints.time_budget or "").lower()
        if budget in ("fast", "quick", "speed", "low"):
            adjust(
                recs,
                {"logistic_regression", "lightgbm", TransformationType.LABEL_ENCODE.value},
                {"train_model", "random_forest", "xgboost"},
            )
            trace.append("Applied time_budget=fast constraint (favoring faster tools).")
        elif budget in ("thorough", "high"):
            adjust(recs, {"train_model"}, set())
            trace.append("Applied time_budget=thorough constraint (favoring exhaustive search).")
        return recs

    # --------------------------------------------------------- personalization
    async def _personalize(
        self,
        recs: list[ToolRecommendation],
        user_id: str,
        trace: list[str],
    ) -> bool:
        """Nudge priorities by the user's past feedback per tool type.

        ponytail: net accepted/rejected counts, not a learning model. Upgrade to
        weighted/recency-aware scoring if personalization quality matters.
        """
        try:
            feedback = await AIRecommendationFeedback.find(
                AIRecommendationFeedback.user_id == user_id
            ).to_list()
        except Exception:  # pragma: no cover - defensive
            logger.debug("Could not load feedback for %s", user_id, exc_info=True)
            return False
        if not feedback:
            return False

        net: dict[str, int] = {}
        for fb in feedback:
            delta = 1 if fb.action == "accepted" else (-1 if fb.action == "rejected" else 0)
            net[fb.tool_type] = net.get(fb.tool_type, 0) + delta

        applied = False
        for r in recs:
            score = net.get(r.tool_type, 0)
            if score > 0:
                r.priority = min(10, r.priority + 1)
                applied = True
            elif score < 0:
                r.priority = max(1, r.priority - 1)
                r.cons = [*r.cons, "You previously rejected this recommendation"]
                applied = True
        if applied:
            trace.append("Adjusted priorities from your past feedback.")
        return applied

    # ------------------------------------------------------------ openai (opt)
    async def _maybe_ai_summary(
        self,
        profile: OrchestrationProfile,
        objective: Objective,
        recs: list[ToolRecommendation],
    ) -> str | None:
        if self.client is None:
            return None
        context = {
            "objective": objective.value,
            "profile": profile.summary_text(),
            "recommended_tools": [r.tool_type for r in recs],
        }
        try:
            return await self._openai_summary(context)
        except Exception as exc:  # includes CircuitBreakerOpen
            logger.warning("OpenAI orchestration summary unavailable: %s", exc)
            return None

    @with_circuit_breaker(
        "openai",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(OpenAIError,),
        fallback_value=None,
    )
    async def _openai_summary(self, context: dict[str, Any]) -> str | None:
        response = await asyncio.to_thread(
            cast(Any, self.client).chat.completions.create,
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a data science assistant. In 2-3 plain-language "
                    "sentences, explain to a non-expert why the recommended tools suit this "
                    "dataset and objective. Respond as JSON: {\"summary\": \"...\"}.",
                },
                {"role": "user", "content": json.dumps(context, default=str)},
            ],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        summary = str(data.get("summary", "")).strip()
        return summary or None

    # --------------------------------------------------------- stage guidance
    async def generate_stage_guidance(
        self,
        profile: OrchestrationProfile,
        stage: WorkflowStageId,
        request_context: dict[str, Any] | None,
        user_id: str,
    ) -> StageGuidanceResponse:
        """Consistent, context-aware AI guidance for one workflow stage (#90).

        Rule-based core works fully with no OpenAI key; an optional OpenAI pass
        enhances only the plain-language summary. Never raises.
        """
        reasoning_trace: list[str] = [
            f"Built profile for dataset {profile.dataset_id}: {profile.summary_text()}"
        ]
        accumulated, context_used = await self._accumulate_context(
            profile.dataset_id, user_id, stage, request_context, reasoning_trace
        )

        focus = _STAGE_FOCUS.get(stage.value, "Working through this stage")
        considerations, actions = self._stage_rule_guidance(stage, profile)
        # Make the no-OpenAI path genuinely context-aware: prior-stage decisions
        # lead the considerations so later guidance visibly builds on earlier ones.
        if context_used:
            considerations = [
                "Building on your earlier choices (" + "; ".join(context_used) + "), "
                "keep them consistent with what you decide here."
            ] + considerations
        reasoning_trace.append(f"Rule-based engine produced guidance for stage '{stage.value}'.")

        guidance_summary = self._stage_rule_summary(focus, profile, context_used)
        generated_by = "rule_based"
        ai_summary = await self._maybe_stage_ai_summary(
            stage, focus, profile, context_used, considerations, actions
        )
        if ai_summary:
            guidance_summary = ai_summary
            generated_by = "hybrid"
            reasoning_trace.append("OpenAI enhanced the plain-language stage guidance.")

        return StageGuidanceResponse(
            dataset_id=profile.dataset_id,
            stage=stage,
            focus=focus,
            guidance_summary=guidance_summary,
            key_considerations=considerations,
            suggested_actions=actions,
            context_used=context_used,
            reasoning_trace=reasoning_trace,
            generated_by=generated_by,
            partial=profile.partial,
        )

    async def _accumulate_context(
        self,
        dataset_id: str,
        user_id: str,
        stage: WorkflowStageId,
        request_context: dict[str, Any] | None,
        reasoning_trace: list[str],
    ) -> tuple[dict[str, Any], list[str]]:
        """Gather prior-stage decisions so later guidance builds on earlier ones.

        Reads persisted workflow state (#87) best-effort, then merges any explicit
        accumulated_context from the caller on top.
        """
        accumulated: dict[str, Any] = {}
        context_used: list[str] = []

        workflow: WorkflowState | None = None
        try:
            workflow = await WorkflowState.find_one(
                WorkflowState.user_id == user_id,
                WorkflowState.dataset_id == dataset_id,
            )
        except Exception:  # pragma: no cover - defensive; persisted state is optional
            logger.debug("Could not load workflow state for %s", dataset_id, exc_info=True)

        if workflow is not None:
            prior_stages = [s for s in workflow.completed_stages if s != stage.value]
            for prior in prior_stages:
                data = workflow.stage_data.get(prior)
                if data:
                    accumulated[prior] = data
                    context_used.append(f"{prior}: {self._summarize_decision(data)}")
            if prior_stages:
                reasoning_trace.append(
                    "Accumulated decisions from completed stage(s): " + ", ".join(prior_stages)
                )

        if request_context:
            accumulated.update(request_context)
            for key, value in request_context.items():
                context_used.append(f"{key}: {self._summarize_decision(value)}")
            reasoning_trace.append("Merged caller-supplied accumulated_context.")

        return accumulated, context_used

    @staticmethod
    def _summarize_decision(value: Any) -> str:
        """Compact, length-capped string for a prior-stage decision."""
        if isinstance(value, dict):
            text = ", ".join(f"{k}={value[k]}" for k in list(value)[:5])
        elif isinstance(value, list):
            text = ", ".join(str(v) for v in value[:5])
        else:
            text = str(value)
        return text[:160]

    def _stage_rule_guidance(
        self,
        stage: WorkflowStageId,
        profile: OrchestrationProfile,
    ) -> tuple[list[str], list[str]]:
        """Per-stage key considerations + suggested actions (rule-based).

        Accumulated cross-stage context is folded in by the caller
        (`generate_stage_guidance`), so this stays a pure function of the stage
        and the dataset profile.
        """
        if stage == WorkflowStageId.DATA_PREPARATION:
            return self._guidance_from_recs(
                self._cleaning_recs(profile),
                fallback_action="Your data looks clean — review the profiling report and continue.",
            )
        if stage == WorkflowStageId.FEATURE_ENGINEERING:
            return self._guidance_from_recs(self._feature_recs(profile))
        if stage == WorkflowStageId.MODEL_TRAINING:
            return self._guidance_from_recs(self._modeling_recs(profile))
        if stage == WorkflowStageId.DEPLOYMENT:
            return self._deployment_guidance(profile)
        # Stages with their own rich, dedicated AI surfaces (#79/#81/#83/#80) or no
        # transformation recs: provide concise mentor-voice considerations + actions.
        return self._STATIC_STAGE_GUIDANCE.get(
            stage.value,
            (["Review the available information for this stage."], ["Continue to the next stage."]),
        )

    @staticmethod
    def _guidance_from_recs(
        recs: list[ToolRecommendation],
        fallback_action: str = "Continue to the next stage.",
    ) -> tuple[list[str], list[str]]:
        recs = sorted(recs, key=lambda r: r.priority, reverse=True)
        considerations = [r.explanation for r in recs] or [
            "No specific issues were flagged from the current profile."
        ]
        actions = [f"{r.tool_type}: {r.estimated_impact or r.explanation}" for r in recs] or [
            fallback_action
        ]
        return considerations, actions

    def _deployment_guidance(
        self, profile: OrchestrationProfile
    ) -> tuple[list[str], list[str]]:
        """Stage 8 deployment guidance — the genuine gap this issue fills."""
        # Larger datasets / batch-shaped workloads lean toward batch scoring; small
        # ones suit a low-latency real-time endpoint. A heuristic, not a hard rule.
        real_time = profile.n_rows < 100_000
        serving = (
            "Start with a real-time REST endpoint — your volumes are modest and "
            "interactive predictions are simplest to reason about."
            if real_time
            else "Consider batch scoring — at this data scale, scheduled batch jobs "
            "are usually cheaper and easier to operate than a hot endpoint."
        )
        considerations = [
            serving,
            "Decide who calls the model and how (API key per consumer, rate limits).",
            "Capture a baseline of input distributions now so you can detect drift later.",
            "Plan a rollback: keep the previous version promotable in case quality drops.",
        ]
        actions = [
            "Deploy the trained model as a versioned production endpoint.",
            "Enable monitoring: track request volume, latency, error rate, and prediction mix.",
            "Set alert thresholds on error rate and latency before real traffic arrives.",
            "Run the pre-deployment checklist: smoke-test the endpoint with a known record.",
        ]
        return considerations, actions

    # Mentor-voice guidance for stages that already have dedicated AI analytics
    # elsewhere (so we complement, not duplicate, those richer surfaces).
    _STATIC_STAGE_GUIDANCE: dict[str, tuple[list[str], list[str]]] = {
        WorkflowStageId.DATA_LOADING.value: (
            [
                "Confirm the file parsed with the column types you expected.",
                "Watch for ID-like or constant columns that won't help a model.",
            ],
            [
                "Upload your dataset and verify the row/column counts.",
                "Continue to profiling to understand the data before changing it.",
            ],
        ),
        WorkflowStageId.DATA_PROFILING.value: (
            [
                "Look at missingness, cardinality, and obvious outliers first.",
                "Note likely target candidates and strongly correlated columns.",
            ],
            [
                "Review the AI data summary and distribution charts.",
                "Decide which issues to fix in the preparation stage.",
            ],
        ),
        WorkflowStageId.MODEL_EVALUATION.value: (
            [
                "Match the metric to the goal: accuracy can mislead on imbalanced data.",
                "Read the confusion matrix and error analysis for systematic mistakes.",
            ],
            [
                "Open the model report card and confusion matrix.",
                "Use error analysis to decide whether to revisit features or data.",
            ],
        ),
        WorkflowStageId.PREDICTION.value: (
            [
                "Treat low-confidence predictions with caution — they need review.",
                "Per-prediction explanations show which features drove each result.",
            ],
            [
                "Run a single prediction and read its confidence and explanation.",
                "For bulk scoring, use batch prediction and check the low-confidence count.",
            ],
        ),
    }

    def _stage_rule_summary(
        self, focus: str, profile: OrchestrationProfile, context_used: list[str]
    ) -> str:
        """Deterministic plain-language summary used when OpenAI is unavailable."""
        summary = f"This stage is about {focus.lower()}. Your data has {profile.summary_text()}."
        if context_used:
            summary += " It also builds on your earlier choices so far."
        return summary

    async def _maybe_stage_ai_summary(
        self,
        stage: WorkflowStageId,
        focus: str,
        profile: OrchestrationProfile,
        context_used: list[str],
        considerations: list[str],
        actions: list[str],
    ) -> str | None:
        if self.client is None:
            return None
        context = {
            "stage": stage.value,
            "focus": focus,
            "profile": profile.summary_text(),
            "prior_decisions": context_used,
            "key_considerations": considerations,
            "suggested_actions": actions,
        }
        try:
            return await self._stage_guidance_summary(context)
        except Exception as exc:  # includes CircuitBreakerOpen
            logger.warning("OpenAI stage guidance unavailable: %s", exc)
            return None

    @with_circuit_breaker(
        "openai",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(OpenAIError,),
        fallback_value=None,
    )
    async def _stage_guidance_summary(self, context: dict[str, Any]) -> str | None:
        response = await asyncio.to_thread(
            cast(Any, self.client).chat.completions.create,
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": AI_MENTOR_PERSONA
                    + " In 2-4 sentences, summarise what the user should focus on at this "
                    "workflow stage, weaving in their earlier decisions where relevant. "
                    'Respond as JSON: {"summary": "..."}.',
                },
                {"role": "user", "content": json.dumps(context, default=str)},
            ],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        summary = str(data.get("summary", "")).strip()
        return summary or None

    # --------------------------------------------------- parameter optimization
    async def optimize_parameters(
        self,
        profile: OrchestrationProfile,
        request: ParameterOptimizationRequest,
    ) -> ParameterOptimizationResponse:
        """Suggest better parameters for a tool given the data profile (rule-based)."""
        tool = request.tool_type
        current = request.current_parameters or {}

        if tool in (
            TransformationType.IMPUTE_MEAN.value,
            TransformationType.IMPUTE_MEDIAN.value,
            TransformationType.FILL_MISSING.value,
            TransformationType.IMPUTE.value,
        ):
            # 'method' is the executable param FillMissingTransformation reads
            # (not 'strategy'). median/mean apply only to numeric columns, so if
            # any requested column is non-numeric, recommend mode — else those
            # columns are silently skipped (codex). Without requested columns,
            # default to median (numeric assumption) and offer mode/mean.
            requested = current.get("columns") or []
            numeric_set = set(profile.numeric_columns)
            any_non_numeric = bool(requested) and any(c not in numeric_set for c in requested)
            if any_non_numeric:
                primary, alt = "mode", "median"
                explanation = (
                    "The selected columns include non-numeric fields, so mode (most frequent "
                    "value) fills them — mean/median apply only to numeric columns."
                )
                alt_explanation = "Use median for the numeric columns in your selection."
            else:
                primary, alt = "median", "mode"
                explanation = (
                    "Median imputation resists outliers and skew better than the mean, the "
                    "safer default for numeric columns when distributions are unknown."
                )
                alt_explanation = "Use mode for categorical columns or mean for symmetric numeric data."
            return ParameterOptimizationResponse(
                dataset_id=profile.dataset_id,
                tool_type=tool,
                optimized_parameters={**current, "method": primary},
                expected_improvement="Imputation method matched to the selected columns' types",
                explanation=explanation,
                alternatives=[
                    ParameterAlternative(
                        parameters={**current, "method": alt},
                        explanation=alt_explanation,
                    )
                ],
                partial=profile.partial,
            )

        if tool in (
            TransformationType.SCALE.value,
            TransformationType.STANDARDIZE.value,
            TransformationType.NORMALIZE.value,
        ):
            method = "robust" if profile.has_outliers else "standard"
            explanation = (
                "Outliers were detected, so a robust scaler (median/IQR) is less distorted "
                "than standardization."
                if profile.has_outliers
                else "No outliers detected, so standardization (zero mean, unit variance) is "
                "the conventional choice."
            )
            return ParameterOptimizationResponse(
                dataset_id=profile.dataset_id,
                tool_type=tool,
                optimized_parameters={**current, "method": method},
                expected_improvement="Scaling matched to the data's outlier profile",
                explanation=explanation,
                alternatives=[
                    ParameterAlternative(
                        parameters={**current, "method": "minmax"},
                        explanation="Min-max scaling to [0,1] when you need bounded features.",
                    )
                ],
                partial=profile.partial,
            )

        if tool in (
            TransformationType.ONE_HOT_ENCODE.value,
            TransformationType.LABEL_ENCODE.value,
            TransformationType.ENCODE.value,
        ):
            # Base the choice on the requested columns when supplied, not the
            # whole dataset — else a low-card one-hot request gets flipped to
            # label just because some unrelated column is high-card (codex).
            requested = current.get("columns") or []
            high_card_set = set(profile.high_cardinality_columns)
            high_card = (
                any(c in high_card_set for c in requested)
                if requested
                else bool(profile.high_cardinality_columns)
            )
            chosen = "label" if high_card else "onehot"
            return ParameterOptimizationResponse(
                dataset_id=profile.dataset_id,
                tool_type=tool,
                optimized_parameters={**current, "method": chosen, "max_onehot_cardinality": 20},
                expected_improvement="Encoding matched to column cardinality",
                explanation=(
                    "High-cardinality columns are present, so label encoding avoids a column "
                    "explosion."
                    if high_card
                    else "Cardinality is low, so one-hot encoding avoids implying a false order."
                ),
                alternatives=[
                    ParameterAlternative(
                        parameters={**current, "method": "onehot" if chosen == "label" else "label"},
                        explanation="Switch encoding if your model handles the trade-off better.",
                    )
                ],
                partial=profile.partial,
            )

        # Unknown tool: echo current params with guidance rather than failing.
        return ParameterOptimizationResponse(
            dataset_id=profile.dataset_id,
            tool_type=tool,
            optimized_parameters=current,
            expected_improvement="",
            explanation=f"No specific parameter heuristics for '{tool}'. Current parameters "
            "are kept as-is.",
            partial=profile.partial,
        )

    # ----------------------------------------------------------------- feedback
    async def record_feedback(
        self, request: AIFeedbackRequest, user_id: str
    ) -> AIRecommendationFeedback:
        """Persist feedback on a recommendation (drives future personalization)."""
        feedback = AIRecommendationFeedback(
            feedback_id=f"aifb_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            recommendation_id=request.recommendation_id,
            tool_type=request.tool_type,
            action=request.action.value,
            dataset_id=request.dataset_id,
            rating=request.rating,
            comment=request.comment,
            modification=request.modification,
        )
        await feedback.insert()
        return feedback


# Module-level singleton (mirrors evaluation_explanation_service).
ai_orchestration_service = AIOrchestrationService()
