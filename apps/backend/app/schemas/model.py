"""
Pydantic schemas for Model API endpoints.

These schemas define request/response models for model training and deployment operations,
using ModelConfig model.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.model import ProblemType

# Request Schemas


class ModelTrainRequest(BaseModel):
    """Request schema for model training."""

    dataset_id: str = Field(..., description="Dataset to train on")
    name: str = Field(..., description="Human-readable model name")
    description: str | None = Field(None, description="Model description")
    problem_type: ProblemType = Field(..., description="ML problem type")
    algorithm: str = Field(..., description="Algorithm to use")
    target_column: str = Field(..., description="Target column name")
    feature_columns: list[str] = Field(..., description="Feature column names")

    # Training configuration
    train_test_split: float = Field(default=0.8, gt=0.0, lt=1.0)
    cv_folds: int = Field(default=5, ge=2)
    validation_strategy: str = Field(default="k-fold")

    # Hyperparameters (optional)
    hyperparameters: dict[str, Any] | None = None

    # Advanced options
    early_stopping: bool = Field(default=False)
    optimization_metric: str = Field(default="accuracy")


class ModelUpdateRequest(BaseModel):
    """Request schema for updating model configuration."""

    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class ModelDeployRequest(BaseModel):
    """Request schema for deploying a model."""

    endpoint: str | None = Field(None, description="Deployment endpoint URL")


class ModelPredictionRequest(BaseModel):
    """Request schema for making predictions."""

    input_data: list[dict[str, Any]] = Field(
        ..., description="Input data for prediction"
    )


# Response Schemas


class FeatureConfigResponse(BaseModel):
    """Response schema for feature configuration."""

    feature_names: list[str]
    target_column: str
    engineered_features: list[str] = Field(default_factory=list)
    dropped_features: list[str] = Field(default_factory=list)
    feature_importance: dict[str, float] | None = None
    numeric_features: list[str] = Field(default_factory=list)
    categorical_features: list[str] = Field(default_factory=list)
    datetime_features: list[str] = Field(default_factory=list)


class PerformanceMetricsResponse(BaseModel):
    """Response schema for performance metrics."""

    cv_score: float
    test_score: float

    # Classification metrics
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    roc_auc: float | None = None

    # Regression metrics
    rmse: float | None = None
    mae: float | None = None
    r2_score: float | None = None

    # Additional metrics
    additional_metrics: dict[str, Any] = Field(default_factory=dict)
    confusion_matrix: list[list[int]] | None = None


class TrainingConfigResponse(BaseModel):
    """Response schema for training configuration."""

    train_test_split: float
    cv_folds: int
    validation_strategy: str
    training_time: float
    n_samples_train: int
    n_samples_test: int
    early_stopping: bool
    optimization_metric: str


class DeploymentConfigResponse(BaseModel):
    """Response schema for deployment configuration."""

    is_deployed: bool
    deployed_at: datetime | None = None
    deployment_endpoint: str | None = None
    prediction_count: int = 0
    last_prediction_at: datetime | None = None
    average_prediction_time: float | None = None
    error_rate: float | None = None


class ModelConfigResponse(BaseModel):
    """Response schema for model configuration."""

    model_id: str = Field(..., description="Unique model identifier")
    user_id: str = Field(..., description="User who owns the model")
    dataset_id: str = Field(..., description="Dataset used for training")

    # Model metadata
    name: str
    description: str | None = None
    problem_type: str
    algorithm: str

    # Configuration
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    feature_config: FeatureConfigResponse
    training_config: TrainingConfigResponse

    # Performance
    performance_metrics: PerformanceMetricsResponse

    # Storage
    model_path: str
    model_file_url: str | None = None
    feature_transformer_path: str | None = None
    model_size: int

    # Status and lifecycle
    status: str
    deployment_config: DeploymentConfigResponse

    # Versioning
    version: str
    is_active: bool
    parent_model_id: str | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    trained_at: datetime | None = None
    last_used_at: datetime | None = None

    # Metadata
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class ModelListItem(BaseModel):
    """Schema for model list item."""

    model_id: str
    name: str
    description: str | None = None
    problem_type: str
    algorithm: str
    status: str
    test_score: float
    is_active: bool
    is_deployed: bool
    created_at: datetime
    trained_at: datetime | None = None


class ModelListResponse(BaseModel):
    """Response schema for list models endpoint."""

    models: list[ModelListItem] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="Total number of models")


class ModelTrainResponse(BaseModel):
    """Response schema for model training operation."""

    model_id: str = Field(..., description="Unique model identifier")
    status: str = Field(..., description="Training status")
    message: str = Field(..., description="Status message")
    training_time: float = Field(..., description="Training duration in seconds")
    performance_metrics: PerformanceMetricsResponse


class ModelDeployResponse(BaseModel):
    """Response schema for model deployment operation."""

    model_id: str = Field(..., description="Model identifier")
    status: str = Field(..., description="Deployment status")
    deployed_at: datetime
    deployment_endpoint: str | None = None
    message: str = Field(..., description="Status message")


class ModelPredictionResponse(BaseModel):
    """Response schema for model predictions."""

    model_id: str = Field(..., description="Model used for prediction")
    predictions: list[Any] = Field(..., description="Prediction results")
    prediction_time_ms: float = Field(
        ..., description="Prediction time in milliseconds"
    )


# Confidence & explainability schemas (issue #83). All fields on the
# prediction responses that carry these are optional, so older clients and
# pre-#83 models keep working unchanged.


class PredictionConfidence(BaseModel):
    """Confidence metadata for a single prediction."""

    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in [0, 1] (max class probability)"
    )
    is_calibrated: bool = Field(
        ..., description="Whether the score comes from a calibrated model"
    )
    calibration_method: str | None = Field(
        None, description="Calibration method used ('sigmoid' or 'isotonic')"
    )
    is_low_confidence: bool = Field(
        ...,
        description="True when confidence is strictly below the threshold "
        "(a value equal to the threshold is NOT flagged)",
    )
    confidence_threshold: float = Field(
        ..., description="Threshold used to flag low confidence (strict less-than)"
    )


class FeatureContribution(BaseModel):
    """A single feature's contribution to a prediction."""

    feature_name: str = Field(..., description="Engineered feature name")
    contribution: float = Field(
        ..., description="Signed contribution (positive raises the prediction)"
    )
    feature_value: float | None = Field(
        None, description="Engineered feature value for this prediction"
    )


class PredictionExplanation(BaseModel):
    """Per-prediction, model-native explanation (no SHAP — see issue #80)."""

    top_features: list[FeatureContribution] = Field(
        default_factory=list, description="Top contributing features"
    )
    explanation_text: str = Field(
        ..., description="Plain-language summary of what drove the prediction"
    )
    method: str = Field(
        ...,
        description="How contributions were derived: linear_coefficients, "
        "tree_importance, or stored_importance",
    )


class ModelDeleteResponse(BaseModel):
    """Response schema for model delete endpoint."""

    status: str = Field(..., description="Delete status")
    model_id: str = Field(..., description="Deleted model ID")
    message: str = Field(..., description="Success message")


class ModelPerformanceSummaryResponse(BaseModel):
    """Response schema for model performance summary."""

    model_id: str
    cv_score: float
    test_score: float
    problem_type: str

    # Problem-specific metrics
    classification_metrics: dict[str, float] | None = None
    regression_metrics: dict[str, float] | None = None

    # Feature importance
    top_features: list[dict[str, Any]] = Field(default_factory=list)


class ModelStatusUpdateResponse(BaseModel):
    """Response schema for model status update."""

    model_id: str
    status: str
    updated_at: datetime
    message: str
