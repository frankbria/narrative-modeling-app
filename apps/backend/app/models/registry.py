"""Canonical list of Beanie document models for database initialization.

Single source of truth used by the app lifespan (app/main.py) and the test
database fixture (tests/conftest.py). Keeping one list prevents the drift that
previously left VisualizationCache, TransformationConfig, RevisedData,
SharedRecipe, and DataIssueRecord unregistered at app startup (issue #160).
"""

from app.models.ab_test import ABTest
from app.models.ai_feedback import AIRecommendationFeedback
from app.models.analytics_result import AnalyticsResult
from app.models.api_key import APIKey
from app.models.batch_job import BatchJob
from app.models.bulk_transformation import BulkTransformationJob
from app.models.column_stats import ColumnStats
from app.models.data_issue import DataIssueRecord
from app.models.dataset import DatasetMetadata
from app.models.feature import FeatureDefinition
from app.models.feature_store import FeatureCollection, FeatureVersion, StoredFeature
from app.models.feedback import Feedback
from app.models.ml_model import MLModel
from app.models.model import ModelConfig
from app.models.plot import Plot
from app.models.revised_data import RevisedData
from app.models.trained_model import TrainedModel
from app.models.training_job import TrainingJob
from app.models.transformation import TransformationConfig
from app.models.user_data import UserData
from app.models.version import DatasetVersion, TransformationLineage
from app.models.visualization_cache import VisualizationCache
from app.models.workflow import WorkflowState
from app.services.transformation_engine.recipe_manager import (
    RecipeExecutionHistory,
    SharedRecipe,
    TransformationRecipe,
)

DOCUMENT_MODELS = [
    ABTest,
    AIRecommendationFeedback,
    AnalyticsResult,
    APIKey,
    BatchJob,
    BulkTransformationJob,
    ColumnStats,
    DataIssueRecord,
    DatasetMetadata,
    DatasetVersion,
    FeatureCollection,
    FeatureDefinition,
    FeatureVersion,
    Feedback,
    MLModel,
    ModelConfig,
    Plot,
    RecipeExecutionHistory,
    RevisedData,
    SharedRecipe,
    StoredFeature,
    TrainedModel,
    TrainingJob,
    TransformationConfig,
    TransformationLineage,
    TransformationRecipe,
    UserData,
    VisualizationCache,
    WorkflowState,
]
