"""Schemas for the model evaluation dashboard (issue #79).

Contract shared with the frontend: apps/frontend/lib/types/evaluation.ts
mirrors these models field-for-field. Change both together.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PerClassMetrics(BaseModel):
    """Precision/recall/F1 for a single class."""

    precision: float
    recall: float
    f1: float
    support: int = Field(..., ge=0, description="Number of true samples of this class")


class ClassificationMetrics(BaseModel):
    """Aggregate classification metrics computed on the held-out test set."""

    accuracy: float
    precision_macro: float
    precision_weighted: float
    recall_macro: float
    recall_weighted: float
    f1_macro: float
    f1_weighted: float
    roc_auc: float | None = Field(
        None, description="Macro one-vs-rest AUC; None when probabilities are unavailable"
    )
    log_loss: float | None = Field(
        None, description="None when probabilities are unavailable"
    )
    per_class_metrics: dict[str, PerClassMetrics] = Field(default_factory=dict)


class RegressionMetrics(BaseModel):
    """Aggregate regression metrics computed on the held-out test set."""

    mae: float
    mse: float
    rmse: float
    r2: float
    mape: float | None = Field(
        None, description="None when y_test contains zeros (undefined)"
    )


class ConfusionMatrixData(BaseModel):
    """Confusion matrix; matrix[i][j] = count of actual labels[i] predicted as labels[j]."""

    labels: list[str]
    matrix: list[list[int]]


class CurvePoint(BaseModel):
    """One point on a ROC or PR curve."""

    x: float
    y: float
    threshold: float | None = None


class ROCCurveData(BaseModel):
    """Per-class ROC curves (one-vs-rest for multiclass). x=FPR, y=TPR."""

    curves: dict[str, list[CurvePoint]] = Field(default_factory=dict)
    auc_per_class: dict[str, float] = Field(default_factory=dict)
    macro_auc: float | None = None


class PRCurveData(BaseModel):
    """Per-class precision-recall curves. x=recall, y=precision."""

    curves: dict[str, list[CurvePoint]] = Field(default_factory=dict)
    baseline_per_class: dict[str, float] = Field(
        default_factory=dict,
        description="Positive-class prevalence per class (random-classifier baseline)",
    )


class AIExplanation(BaseModel):
    """Plain-language 'Model Report Card' explanation."""

    overall_assessment: str
    metric_explanations: dict[str, str] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_by: Literal["openai", "fallback"] = "fallback"


class ModelEvaluationResponse(BaseModel):
    """Full evaluation payload for one model."""

    model_id: str
    model_name: str | None = None
    algorithm: str | None = None
    problem_type: str
    partial: bool = Field(
        False,
        description=(
            "True when evaluation artifacts are unavailable (models trained before "
            "issue #79) and only stored scalar metrics are returned"
        ),
    )
    metrics: ClassificationMetrics | RegressionMetrics | None = None
    stored_metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Scalar metrics persisted at training time (cv_score, test_score, ...)",
    )
    confusion_matrix: ConfusionMatrixData | None = None
    roc_curve: ROCCurveData | None = None
    pr_curve: PRCurveData | None = None
    feature_importance: dict[str, float] | None = None
    ai_explanation: AIExplanation | None = None
    evaluated_at: datetime


class RankedFeature(BaseModel):
    """One feature's importance, for a ranked importance list (issue #80)."""

    feature_name: str
    importance: float


class FeatureImportanceResponse(BaseModel):
    """Global feature importance for one model (issue #80).

    Carries both the model-native importance (always available when the model
    exposed coef_/feature_importances_/SelectKBest at training) and, when the
    model type is SHAP-supported, SHAP-based importance. ``partial`` is True
    only when neither is available.
    """

    model_id: str
    partial: bool = False
    explainer_type: str | None = Field(
        None, description='"tree", "linear", or None when SHAP is unavailable'
    )
    native_importance: list[RankedFeature] = Field(default_factory=list)
    shap_importance: list[RankedFeature] | None = None
    message: str | None = None


class ShapSummaryResponse(BaseModel):
    """SHAP summary-plot data for one model (issue #80).

    ``feature_importance`` is the mean |SHAP| per feature, ranked. For models
    trained before #80 or whose type isn't SHAP-supported, ``partial`` is True,
    the lists are empty, and ``message`` explains the fallback to native
    importance — the endpoint never 500s for an owned model.
    """

    model_id: str
    partial: bool = False
    explainer_type: str | None = None
    problem_type: str
    feature_importance: list[RankedFeature] = Field(default_factory=list)
    base_value: float | None = None
    plain_language: str = ""
    message: str | None = None
    evaluated_at: datetime


class ModelComparisonRequest(BaseModel):
    """Request body for POST /api/v1/ml/compare."""

    model_ids: list[str] = Field(..., min_length=2, max_length=5)


class ModelEvaluationSummary(BaseModel):
    """One model's row in a comparison."""

    model_id: str
    name: str
    algorithm: str
    problem_type: str
    cv_score: float | None = None
    test_score: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    created_at: datetime | None = None


class ModelComparisonResponse(BaseModel):
    """Response for POST /api/v1/ml/compare."""

    problem_type: str
    dataset_id: str
    models: list[ModelEvaluationSummary]
