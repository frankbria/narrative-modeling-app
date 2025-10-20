"""
Pydantic schemas for Model API endpoints.

These schemas define request/response models for model training and deployment operations,
using ModelConfig model.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime


# Request Schemas

class ModelTrainRequest(BaseModel):
    """Request schema for model training."""

    dataset_id: str = Field(..., description="Dataset to train on")
    name: str = Field(..., description="Human-readable model name")
    description: Optional[str] = Field(None, description="Model description")
    problem_type: str = Field(..., description="ML problem type")
    algorithm: str = Field(..., description="Algorithm to use")
    target_column: str = Field(..., description="Target column name")
    feature_columns: List[str] = Field(..., description="Feature column names")

    # Training configuration
    train_test_split: float = Field(default=0.8, gt=0.0, lt=1.0)
    cv_folds: int = Field(default=5, ge=2)
    validation_strategy: str = Field(default="k-fold")

    # Hyperparameters (optional)
    hyperparameters: Optional[Dict[str, Any]] = None

    # Advanced options
    early_stopping: bool = Field(default=False)
    optimization_metric: str = Field(default="accuracy")


class ModelUpdateRequest(BaseModel):
    """Request schema for updating model configuration."""

    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class ModelDeployRequest(BaseModel):
    """Request schema for deploying a model."""

    endpoint: Optional[str] = Field(None, description="Deployment endpoint URL")


class ModelPredictionRequest(BaseModel):
    """Request schema for making predictions."""

    input_data: List[Dict[str, Any]] = Field(..., description="Input data for prediction")


# Response Schemas

class FeatureConfigResponse(BaseModel):
    """Response schema for feature configuration."""

    feature_names: List[str]
    target_column: str
    engineered_features: List[str] = Field(default_factory=list)
    dropped_features: List[str] = Field(default_factory=list)
    feature_importance: Optional[Dict[str, float]] = None
    numeric_features: List[str] = Field(default_factory=list)
    categorical_features: List[str] = Field(default_factory=list)
    datetime_features: List[str] = Field(default_factory=list)


class PerformanceMetricsResponse(BaseModel):
    """Response schema for performance metrics."""

    cv_score: float
    test_score: float

    # Classification metrics
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None

    # Regression metrics
    rmse: Optional[float] = None
    mae: Optional[float] = None
    r2_score: Optional[float] = None

    # Additional metrics
    additional_metrics: Dict[str, Any] = Field(default_factory=dict)
    confusion_matrix: Optional[List[List[int]]] = None


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
    deployed_at: Optional[datetime] = None
    deployment_endpoint: Optional[str] = None
    prediction_count: int = 0
    last_prediction_at: Optional[datetime] = None
    average_prediction_time: Optional[float] = None
    error_rate: Optional[float] = None


class ModelConfigResponse(BaseModel):
    """Response schema for model configuration."""

    model_id: str = Field(..., description="Unique model identifier")
    user_id: str = Field(..., description="User who owns the model")
    dataset_id: str = Field(..., description="Dataset used for training")

    # Model metadata
    name: str
    description: Optional[str] = None
    problem_type: str
    algorithm: str

    # Configuration
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    feature_config: FeatureConfigResponse
    training_config: TrainingConfigResponse

    # Performance
    performance_metrics: PerformanceMetricsResponse

    # Storage
    model_path: str
    model_file_url: Optional[str] = None
    feature_transformer_path: Optional[str] = None
    model_size: int

    # Status and lifecycle
    status: str
    deployment_config: DeploymentConfigResponse

    # Versioning
    version: str
    is_active: bool
    parent_model_id: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    trained_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    # Metadata
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class ModelListItem(BaseModel):
    """Schema for model list item."""

    model_id: str
    name: str
    description: Optional[str] = None
    problem_type: str
    algorithm: str
    status: str
    test_score: float
    is_active: bool
    is_deployed: bool
    created_at: datetime
    trained_at: Optional[datetime] = None


class ModelListResponse(BaseModel):
    """Response schema for list models endpoint."""

    models: List[ModelListItem] = Field(default_factory=list)
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
    deployment_endpoint: Optional[str] = None
    message: str = Field(..., description="Status message")


class ModelPredictionResponse(BaseModel):
    """Response schema for model predictions."""

    model_id: str = Field(..., description="Model used for prediction")
    predictions: List[Any] = Field(..., description="Prediction results")
    prediction_time_ms: float = Field(..., description="Prediction time in milliseconds")


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
    classification_metrics: Optional[Dict[str, float]] = None
    regression_metrics: Optional[Dict[str, float]] = None

    # Feature importance
    top_features: List[Dict[str, Any]] = Field(default_factory=list)


class ModelStatusUpdateResponse(BaseModel):
    """Response schema for model status update."""

    model_id: str
    status: str
    updated_at: datetime
    message: str
