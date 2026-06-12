"""Schemas for the model evaluation dashboard (issue #79).

Contract shared with the frontend: apps/frontend/lib/types/evaluation.ts
mirrors these models field-for-field. Change both together.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

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
    roc_auc: Optional[float] = Field(
        None, description="Macro one-vs-rest AUC; None when probabilities are unavailable"
    )
    log_loss: Optional[float] = Field(
        None, description="None when probabilities are unavailable"
    )
    per_class_metrics: Dict[str, PerClassMetrics] = Field(default_factory=dict)


class RegressionMetrics(BaseModel):
    """Aggregate regression metrics computed on the held-out test set."""

    mae: float
    mse: float
    rmse: float
    r2: float
    mape: Optional[float] = Field(
        None, description="None when y_test contains zeros (undefined)"
    )


class ConfusionMatrixData(BaseModel):
    """Confusion matrix; matrix[i][j] = count of actual labels[i] predicted as labels[j]."""

    labels: List[str]
    matrix: List[List[int]]


class CurvePoint(BaseModel):
    """One point on a ROC or PR curve."""

    x: float
    y: float
    threshold: Optional[float] = None


class ROCCurveData(BaseModel):
    """Per-class ROC curves (one-vs-rest for multiclass). x=FPR, y=TPR."""

    curves: Dict[str, List[CurvePoint]] = Field(default_factory=dict)
    auc_per_class: Dict[str, float] = Field(default_factory=dict)
    macro_auc: Optional[float] = None


class PRCurveData(BaseModel):
    """Per-class precision-recall curves. x=recall, y=precision."""

    curves: Dict[str, List[CurvePoint]] = Field(default_factory=dict)
    baseline_per_class: Dict[str, float] = Field(
        default_factory=dict,
        description="Positive-class prevalence per class (random-classifier baseline)",
    )


class AIExplanation(BaseModel):
    """Plain-language 'Model Report Card' explanation."""

    overall_assessment: str
    metric_explanations: Dict[str, str] = Field(default_factory=dict)
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    generated_by: Literal["openai", "fallback"] = "fallback"


class ModelEvaluationResponse(BaseModel):
    """Full evaluation payload for one model."""

    model_id: str
    model_name: Optional[str] = None
    algorithm: Optional[str] = None
    problem_type: str
    partial: bool = Field(
        False,
        description=(
            "True when evaluation artifacts are unavailable (models trained before "
            "issue #79) and only stored scalar metrics are returned"
        ),
    )
    metrics: Optional[Union[ClassificationMetrics, RegressionMetrics]] = None
    stored_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Scalar metrics persisted at training time (cv_score, test_score, ...)",
    )
    confusion_matrix: Optional[ConfusionMatrixData] = None
    roc_curve: Optional[ROCCurveData] = None
    pr_curve: Optional[PRCurveData] = None
    feature_importance: Optional[Dict[str, float]] = None
    ai_explanation: Optional[AIExplanation] = None
    evaluated_at: datetime


class ModelComparisonRequest(BaseModel):
    """Request body for POST /api/v1/ml/compare."""

    model_ids: List[str] = Field(..., min_length=2, max_length=5)


class ModelEvaluationSummary(BaseModel):
    """One model's row in a comparison."""

    model_id: str
    name: str
    algorithm: str
    problem_type: str
    cv_score: Optional[float] = None
    test_score: Optional[float] = None
    metrics: Dict[str, float] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class ModelComparisonResponse(BaseModel):
    """Response for POST /api/v1/ml/compare."""

    problem_type: str
    dataset_id: str
    models: List[ModelEvaluationSummary]
