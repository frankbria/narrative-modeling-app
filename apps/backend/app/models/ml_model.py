"""
Machine Learning Model document for MongoDB
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from beanie import Document, Indexed
from pydantic import Field


class MLModel(Document):
    """ML Model metadata stored in MongoDB"""
    
    # Ownership and identification
    user_id: Indexed(str)
    dataset_id: Indexed(str)
    model_id: Indexed(str) = Field(description="Unique model identifier")
    name: str
    description: Optional[str] = None
    
    # Model details
    problem_type: str  # classification, regression, etc.
    algorithm: str  # e.g., "Random Forest", "XGBoost"
    target_column: str
    feature_names: List[str]
    
    # Performance metrics
    cv_score: float
    test_score: float
    metrics: Dict[str, Any] = Field(default_factory=dict)
    
    # Model metadata
    training_time: float  # seconds
    model_size: int  # bytes
    n_samples_train: int
    n_features: int
    
    # Storage information
    model_path: str  # S3 path to serialized model
    feature_transformer_path: Optional[str] = None  # S3 path to feature transformer
    
    # Versioning
    version: str = Field(default="1.0.0", description="Semantic version (major.minor.patch)")
    is_active: bool = True
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = None
    
    # Feature importance
    feature_importance: Optional[Dict[str, float]] = None
    
    # Training configuration
    training_config: Dict[str, Any] = Field(default_factory=dict)
    
    class Settings:
        name = "ml_models"
        indexes = [
            "user_id",
            "dataset_id", 
            "model_id",
            [("user_id", 1), ("created_at", -1)],
            [("dataset_id", 1), ("is_active", 1)]
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
                "model_path": "s3://bucket/models/model_789.pkl"
            }
        }