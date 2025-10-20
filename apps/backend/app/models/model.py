"""
Model configuration and metadata for MongoDB.

This model focuses on ML model configuration, training parameters, performance metrics,
and deployment settings. It consolidates and enhances the existing MLModel and TrainedModel.
"""

from beanie import Document, Indexed, Link
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from beanie import PydanticObjectId
from enum import Enum


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(timezone.utc)


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
    n_estimators: Optional[int] = Field(None, ge=1, description="Number of estimators (for ensemble methods)")
    max_depth: Optional[int] = Field(None, ge=1, description="Maximum tree depth")
    learning_rate: Optional[float] = Field(None, gt=0, description="Learning rate")
    random_state: Optional[int] = Field(None, description="Random state for reproducibility")

    # Additional hyperparameters (flexible)
    additional_params: Dict[str, Any] = Field(default_factory=dict, description="Additional algorithm-specific parameters")


class FeatureConfig(BaseModel):
    """Feature engineering and selection configuration."""

    feature_names: List[str] = Field(..., description="List of feature column names")
    target_column: str = Field(..., description="Target column name")

    # Feature engineering
    engineered_features: List[str] = Field(default_factory=list, description="List of engineered feature names")
    dropped_features: List[str] = Field(default_factory=list, description="Features dropped during selection")

    # Feature importance
    feature_importance: Optional[Dict[str, float]] = Field(None, description="Feature importance scores")

    # Feature types
    numeric_features: List[str] = Field(default_factory=list, description="Numeric feature names")
    categorical_features: List[str] = Field(default_factory=list, description="Categorical feature names")
    datetime_features: List[str] = Field(default_factory=list, description="Datetime feature names")


class PerformanceMetrics(BaseModel):
    """Model performance metrics."""

    # Core metrics
    cv_score: float = Field(..., ge=0.0, le=1.0, description="Cross-validation score")
    test_score: float = Field(..., ge=0.0, le=1.0, description="Test set score")

    # Classification metrics
    accuracy: Optional[float] = Field(None, ge=0.0, le=1.0)
    precision: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(None, ge=0.0, le=1.0)
    f1_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    roc_auc: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Regression metrics
    rmse: Optional[float] = Field(None, ge=0.0, description="Root Mean Squared Error")
    mae: Optional[float] = Field(None, ge=0.0, description="Mean Absolute Error")
    r2_score: Optional[float] = Field(None, description="R-squared score")

    # Additional metrics
    additional_metrics: Dict[str, Any] = Field(default_factory=dict, description="Additional problem-specific metrics")

    # Confusion matrix (for classification)
    confusion_matrix: Optional[List[List[int]]] = None


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
    deployed_at: Optional[datetime] = None
    deployment_endpoint: Optional[str] = Field(None, description="API endpoint for deployed model")

    # Monitoring
    prediction_count: int = Field(default=0, ge=0, description="Total number of predictions made")
    last_prediction_at: Optional[datetime] = None

    # Performance monitoring
    average_prediction_time: Optional[float] = Field(None, ge=0.0, description="Average prediction time in ms")
    error_rate: Optional[float] = Field(None, ge=0.0, le=1.0, description="Prediction error rate")


class ModelConfig(Document):
    """
    Model configuration and metadata document.

    Stores comprehensive ML model configuration including algorithm selection,
    hyperparameters, feature configuration, performance metrics, and deployment settings.

    This model consolidates and enhances the existing MLModel and TrainedModel,
    providing focused responsibility for model configuration management.
    """

    # Ownership and identification
    user_id: Indexed(str) = Field(..., description="User who owns this model")
    dataset_id: Indexed(str) = Field(..., description="Dataset used for training")
    model_id: Indexed(str) = Field(..., description="Unique model identifier")

    # Model metadata
    name: str = Field(..., description="Human-readable model name")
    description: Optional[str] = Field(None, description="Model description")
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
    model_file_url: Optional[HttpUrl] = Field(None, description="HTTP URL for model file access")
    feature_transformer_path: Optional[str] = Field(None, description="Storage path for feature transformer")
    model_size: int = Field(..., ge=0, description="Model file size in bytes")

    # Status and lifecycle
    status: ModelStatus = Field(default=ModelStatus.TRAINING, description="Model lifecycle status")
    deployment_config: Optional[DeploymentConfig] = Field(default_factory=DeploymentConfig)

    # Versioning
    version: str = Field(default="1.0.0", description="Model version (semantic versioning)")
    is_active: bool = Field(default=True, description="Whether this is the active version")
    parent_model_id: Optional[str] = Field(None, description="Parent model if this is a retrained version")

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)
    trained_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags for organization and search")
    notes: Optional[str] = Field(None, description="Additional notes about the model")

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

    def mark_trained(self) -> None:
        """Mark model as trained."""
        self.status = ModelStatus.TRAINED
        self.trained_at = get_current_time()
        self.update_timestamp()

    def mark_deployed(self, endpoint: Optional[str] = None) -> None:
        """Mark model as deployed."""
        self.status = ModelStatus.DEPLOYED
        if self.deployment_config is None:
            self.deployment_config = DeploymentConfig()
        self.deployment_config.is_deployed = True
        self.deployment_config.deployed_at = get_current_time()
        if endpoint:
            self.deployment_config.deployment_endpoint = endpoint
        self.update_timestamp()

    def mark_archived(self) -> None:
        """Mark model as archived."""
        self.status = ModelStatus.ARCHIVED
        self.is_active = False
        self.update_timestamp()

    def mark_failed(self) -> None:
        """Mark model training as failed."""
        self.status = ModelStatus.FAILED
        self.is_active = False
        self.update_timestamp()

    def record_prediction(self, prediction_time_ms: Optional[float] = None) -> None:
        """
        Record a prediction event.

        Args:
            prediction_time_ms: Prediction time in milliseconds
        """
        if self.deployment_config is None:
            self.deployment_config = DeploymentConfig()

        self.deployment_config.prediction_count += 1
        self.deployment_config.last_prediction_at = get_current_time()
        self.last_used_at = get_current_time()

        # Update average prediction time
        if prediction_time_ms is not None:
            if self.deployment_config.average_prediction_time is None:
                self.deployment_config.average_prediction_time = prediction_time_ms
            else:
                # Running average
                count = self.deployment_config.prediction_count
                current_avg = self.deployment_config.average_prediction_time
                self.deployment_config.average_prediction_time = (
                    (current_avg * (count - 1) + prediction_time_ms) / count
                )

        self.update_timestamp()

    def get_feature_importance_sorted(self) -> List[tuple[str, float]]:
        """
        Get feature importance sorted by importance score.

        Returns:
            List of (feature_name, importance_score) tuples sorted by importance
        """
        if not self.feature_config.feature_importance:
            return []

        return sorted(
            self.feature_config.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )

    def get_top_features(self, n: int = 10) -> List[str]:
        """
        Get top N most important features.

        Args:
            n: Number of top features to return

        Returns:
            List of feature names
        """
        sorted_features = self.get_feature_importance_sorted()
        return [name for name, _ in sorted_features[:n]]

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of model performance.

        Returns:
            Dictionary with key performance metrics
        """
        metrics = {
            "cv_score": self.performance_metrics.cv_score,
            "test_score": self.performance_metrics.test_score
        }

        if self.problem_type in {ProblemType.CLASSIFICATION, ProblemType.BINARY_CLASSIFICATION, ProblemType.MULTICLASS_CLASSIFICATION}:
            if self.performance_metrics.accuracy is not None:
                metrics["accuracy"] = self.performance_metrics.accuracy
            if self.performance_metrics.f1_score is not None:
                metrics["f1_score"] = self.performance_metrics.f1_score
            if self.performance_metrics.roc_auc is not None:
                metrics["roc_auc"] = self.performance_metrics.roc_auc

        elif self.problem_type == ProblemType.REGRESSION:
            if self.performance_metrics.rmse is not None:
                metrics["rmse"] = self.performance_metrics.rmse
            if self.performance_metrics.r2_score is not None:
                metrics["r2_score"] = self.performance_metrics.r2_score

        return metrics

    def is_deployed(self) -> bool:
        """Check if model is currently deployed."""
        return (
            self.status == ModelStatus.DEPLOYED and
            self.deployment_config is not None and
            self.deployment_config.is_deployed
        )

    def get_training_duration_formatted(self) -> str:
        """Get formatted training duration."""
        seconds = self.training_config.training_time
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        else:
            return f"{seconds / 3600:.1f}h"
