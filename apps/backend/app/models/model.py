"""
Model configuration and metadata for MongoDB.

This model focuses on ML model configuration, training parameters, performance metrics,
and deployment settings. It consolidates and enhances the existing MLModel and TrainedModel.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field, HttpUrl, field_validator


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(UTC)


class ProblemType(str, Enum):
    """ML problem types."""
    CLASSIFICATION = "classification"
    BINARY_CLASSIFICATION = "binary_classification"
    MULTICLASS_CLASSIFICATION = "multiclass_classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    TIME_SERIES = "time_series"
    ANOMALY_DETECTION = "anomaly_detection"


class ModelStatus(str, Enum):
    """Model lifecycle status."""
    TRAINING = "training"
    TRAINED = "trained"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    FAILED = "failed"


class HyperparameterConfig(BaseModel):
    """Hyperparameter configuration for model training."""

    # Common hyperparameters
    n_estimators: int | None = Field(None, ge=1, description="Number of estimators (for ensemble methods)")
    max_depth: int | None = Field(None, ge=1, description="Maximum tree depth")
    learning_rate: float | None = Field(None, gt=0, description="Learning rate")
    random_state: int | None = Field(None, description="Random state for reproducibility")

    # Additional hyperparameters (flexible)
    additional_params: dict[str, Any] = Field(default_factory=dict, description="Additional algorithm-specific parameters")


class FeatureConfig(BaseModel):
    """Feature engineering and selection configuration."""

    feature_names: list[str] = Field(..., description="List of feature column names")
    target_column: str = Field(..., description="Target column name")

    # Feature engineering
    engineered_features: list[str] = Field(default_factory=list, description="List of engineered feature names")
    dropped_features: list[str] = Field(default_factory=list, description="Features dropped during selection")

    # Feature importance
    feature_importance: dict[str, float] | None = Field(None, description="Feature importance scores")

    # Feature types
    numeric_features: list[str] = Field(default_factory=list, description="Numeric feature names")
    categorical_features: list[str] = Field(default_factory=list, description="Categorical feature names")
    datetime_features: list[str] = Field(default_factory=list, description="Datetime feature names")


class PerformanceMetrics(BaseModel):
    """Model performance metrics."""

    # Core metrics
    cv_score: float = Field(..., ge=0.0, le=1.0, description="Cross-validation score")
    test_score: float = Field(..., ge=0.0, le=1.0, description="Test set score")

    # Classification metrics
    accuracy: float | None = Field(None, ge=0.0, le=1.0)
    precision: float | None = Field(None, ge=0.0, le=1.0)
    recall: float | None = Field(None, ge=0.0, le=1.0)
    f1_score: float | None = Field(None, ge=0.0, le=1.0)
    roc_auc: float | None = Field(None, ge=0.0, le=1.0)

    # Regression metrics
    rmse: float | None = Field(None, ge=0.0, description="Root Mean Squared Error")
    mae: float | None = Field(None, ge=0.0, description="Mean Absolute Error")
    r2_score: float | None = Field(None, description="R-squared score")

    # Additional metrics
    additional_metrics: dict[str, Any] = Field(default_factory=dict, description="Additional problem-specific metrics")

    # Confusion matrix (for classification)
    confusion_matrix: list[list[int]] | None = None


class TrainingConfig(BaseModel):
    """Training configuration and parameters."""

    # Training parameters
    train_test_split: float = Field(default=0.8, gt=0.0, lt=1.0, description="Train/test split ratio")
    cv_folds: int = Field(default=5, ge=2, description="Number of cross-validation folds")
    validation_strategy: str = Field(default="k-fold", description="Validation strategy: k-fold, stratified, time-series")

    # Training resources
    training_time: float = Field(..., ge=0.0, description="Training duration in seconds")
    n_samples_train: int = Field(..., ge=1, description="Number of training samples")
    n_samples_test: int = Field(..., ge=1, description="Number of test samples")

    # Optimization
    early_stopping: bool = Field(default=False, description="Whether early stopping was used")
    optimization_metric: str = Field(default="accuracy", description="Metric used for optimization")

    @field_validator('validation_strategy')
    @classmethod
    def validate_validation_strategy(cls, v: str) -> str:
        """Validate validation_strategy is one of supported types."""
        allowed_strategies = {'k-fold', 'stratified', 'time-series', 'holdout', 'leave-one-out'}
        if v not in allowed_strategies:
            raise ValueError(f"validation_strategy must be one of {allowed_strategies}, got: {v}")
        return v


class DeploymentConfig(BaseModel):
    """Model deployment configuration."""

    is_deployed: bool = Field(default=False, description="Whether model is deployed")
    deployed_at: datetime | None = None
    deployment_endpoint: str | None = Field(None, description="API endpoint for deployed model")

    # Monitoring
    prediction_count: int = Field(default=0, ge=0, description="Total number of predictions made")
    last_prediction_at: datetime | None = None

    # Performance monitoring
    average_prediction_time: float | None = Field(None, ge=0.0, description="Average prediction time in ms")
    error_rate: float | None = Field(None, ge=0.0, le=1.0, description="Prediction error rate")


class ModelConfig(Document):
    """
    Model configuration and metadata document.

    Stores comprehensive ML model configuration including algorithm selection,
    hyperparameters, feature configuration, performance metrics, and deployment settings.

    This model consolidates and enhances the existing MLModel and TrainedModel,
    providing focused responsibility for model configuration management.
    """

    # Ownership and identification
    user_id: Annotated[str, Indexed()] = Field(..., description="User who owns this model")
    dataset_id: Annotated[str, Indexed()] = Field(..., description="Dataset used for training")
    model_id: Annotated[str, Indexed()] = Field(..., description="Unique model identifier")

    # Model metadata
    name: str = Field(..., description="Human-readable model name")
    description: str | None = Field(None, description="Model description")
    problem_type: ProblemType = Field(..., description="Type of ML problem")
    algorithm: str = Field(..., description="Algorithm name (e.g., 'Random Forest', 'XGBoost')")

    # Configuration
    hyperparameters: HyperparameterConfig = Field(default_factory=HyperparameterConfig)
    feature_config: FeatureConfig
    training_config: TrainingConfig

    # Performance
    performance_metrics: PerformanceMetrics

    # Storage
    model_path: str = Field(..., description="Storage path for serialized model (e.g., S3 key)")
    model_file_url: HttpUrl | None = Field(None, description="HTTP URL for model file access")
    feature_transformer_path: str | None = Field(None, description="Storage path for feature transformer")
    model_size: int = Field(..., ge=0, description="Model file size in bytes")

    # Status and lifecycle
    status: ModelStatus = Field(default=ModelStatus.TRAINING, description="Model lifecycle status")
    deployment_config: DeploymentConfig | None = Field(default_factory=DeploymentConfig)

    # Versioning
    version: str = Field(default="1.0.0", description="Model version (semantic versioning)")
    is_active: bool = Field(default=True, description="Whether this is the active version")
    parent_model_id: str | None = Field(None, description="Parent model if this is a retrained version")

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)
    trained_at: datetime | None = None
    last_used_at: datetime | None = None

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tags for organization and search")
    notes: str | None = Field(None, description="Additional notes about the model")

    class Settings:
        name = "model_configs"
        indexes = [
            # Single field indexes for basic queries
            "user_id",
            "dataset_id",
            "model_id",
            "status",
            "created_at",
            "is_active",
            # Compound indexes for common query patterns
            [("user_id", 1), ("created_at", -1)],  # List user models chronologically
            [("user_id", 1), ("is_active", 1)],  # Filter active models
            [("user_id", 1), ("is_active", 1), ("created_at", -1)],  # Active models chronologically
            [("dataset_id", 1), ("is_active", 1)],  # Dataset's active models
            [("user_id", 1), ("status", 1)],  # Filter by status
            [("user_id", 1), ("status", 1), ("created_at", -1)],  # Status filtered chronologically
            [("dataset_id", 1), ("created_at", -1)],  # Dataset models chronologically
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = get_current_time()
