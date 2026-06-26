"""
Machine Learning Model document for MongoDB
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from beanie import Document, Indexed
from pydantic import Field


class MLModel(Document):
    """ML Model metadata stored in MongoDB"""

    # Ownership and identification
    user_id: Annotated[str, Indexed()]
    dataset_id: Annotated[str, Indexed()]
    model_id: Annotated[str, Indexed()] = Field(description="Unique model identifier")
    name: str
    description: str | None = None

    # Model details
    problem_type: str  # classification, regression, etc.
    algorithm: str  # e.g., "Random Forest", "XGBoost"
    target_column: str
    feature_names: list[str]

    # Performance metrics
    cv_score: float
    test_score: float
    metrics: dict[str, Any] = Field(default_factory=dict)

    # Model metadata
    training_time: float  # seconds
    model_size: int  # bytes
    n_samples_train: int
    n_features: int

    # Storage information
    model_path: str  # S3 path to serialized model
    feature_transformer_path: str | None = None  # S3 path to feature transformer
    # S3 path to held-out evaluation arrays (issue #79); None for models
    # trained before the evaluation dashboard existed (backward compatible)
    evaluation_data_path: str | None = None

    # Versioning
    version: str = Field(
        default="1.0.0", description="Semantic version (major.minor.patch)"
    )
    is_active: bool = True

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None

    # Feature importance
    feature_importance: dict[str, float] | None = None

    # SHAP interpretability (issue #80). All optional so pre-#80 models degrade
    # gracefully: the interpretability endpoints return native feature
    # importance and report SHAP as unavailable. ``shap_values_path`` is the S3
    # path to the global SHAP summary (mean |SHAP| per feature) computed at
    # training time; ``shap_explainer_type`` is "tree" or "linear" (None when
    # the model type isn't SHAP-supported).
    shap_values_path: str | None = None
    shap_explainer_type: str | None = None

    # Confidence & uncertainty (issue #83). All optional/defaulted so models
    # trained before #83 keep working: classification degrades to raw
    # max-probability confidence (is_calibrated=False) and regression has no
    # prediction interval (residual_std=None).
    is_calibrated: bool = False  # persisted model yields calibrated probabilities
    calibration_method: str | None = None  # "sigmoid" or "isotonic"
    # Brier (binary) / log loss (multiclass) — an IN-SAMPLE diagnostic measured
    # on the calibration-fit split, so optimistic (see ConfidenceService).
    calibration_score: float | None = None
    residual_std: float | None = (
        None  # held-out residual std for regression intervals
    )

    # Hyperparameter tuning (issue #77). All optional so models trained without
    # tuning (the default) keep working. ``tuning_results`` is the serialized
    # per-algorithm payload (best params + inline visualization data: parameter
    # importance, optimization history, improvement vs default) surfaced by
    # ``GET /{model_id}/tuning-results``; ``improvement_from_tuning`` is the best
    # model's CV-score gain over its default hyperparameters.
    tuning_strategy: str | None = None
    tuning_time: float | None = None
    improvement_from_tuning: float | None = None
    tuning_results: dict[str, Any] | None = None

    # Model versioning & lineage (issue #78). All optional/defaulted so pre-#78
    # models degrade: they appear as standalone v1 with no production flag.
    # A "version family" = all models sharing (user_id, dataset_id, name);
    # ``parent_model_id`` links each version to the previous one in its family.
    parent_model_id: str | None = None
    is_production: bool = False  # the promoted version within its family
    promoted_at: datetime | None = None
    # Runtime environment captured at training time (python/sklearn/xgboost
    # versions, platform) for reproducibility.
    environment_metadata: dict[str, Any] | None = None
    # The specific DatasetVersion the model was trained on, when available.
    dataset_version_id: str | None = None
    version_notes: str | None = None  # user-provided note for this version

    # Deployment (issue #84). All optional/defaulted so pre-#84 models degrade to
    # "not deployed". Production serving already works by model_id; these fields
    # just mark a model deployed and surface its live endpoint URL to the UI.
    is_deployed: bool = False
    deployment_endpoint: str | None = None
    deployed_at: datetime | None = None

    # Training configuration
    training_config: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "ml_models"
        indexes = [
            "user_id",
            "dataset_id",
            "model_id",
            [("user_id", 1), ("created_at", -1)],
            [("dataset_id", 1), ("is_active", 1)],
            # Version-family lookup (issue #78).
            [("user_id", 1), ("dataset_id", 1), ("name", 1)],
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "dataset_id": "dataset_456",
                "model_id": "model_789",
                "name": "Sales Prediction Model",
                "problem_type": "regression",
                "algorithm": "Random Forest",
                "target_column": "sales",
                "feature_names": ["month", "store_id", "temperature"],
                "cv_score": 0.85,
                "test_score": 0.83,
                "training_time": 45.2,
                "model_size": 1048576,
                "n_samples_train": 10000,
                "n_features": 25,
                "model_path": "s3://bucket/models/model_789.pkl",
            }
        }
