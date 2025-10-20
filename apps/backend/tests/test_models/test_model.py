"""
Tests for ModelConfig model - Unit tests only (no database required).

Tests cover:
- ProblemType and ModelStatus enums
- HyperparameterConfig model
- FeatureConfig model
- PerformanceMetrics model
- TrainingConfig model
- DeploymentConfig model
- ModelConfig model
- Helper methods
- Edge cases and error conditions
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.models.model import (
    ModelConfig,
    ProblemType,
    ModelStatus,
    HyperparameterConfig,
    FeatureConfig,
    PerformanceMetrics,
    TrainingConfig,
    DeploymentConfig,
    get_current_time
)


class TestGetCurrentTime:
    """Tests for get_current_time utility function."""

    def test_get_current_time_returns_datetime(self):
        """Test that get_current_time returns a datetime object."""
        current_time = get_current_time()
        assert isinstance(current_time, datetime)

    def test_get_current_time_has_utc_timezone(self):
        """Test that returned datetime has UTC timezone."""
        current_time = get_current_time()
        assert current_time.tzinfo == timezone.utc


class TestProblemType:
    """Tests for ProblemType enum."""

    def test_problem_type_values(self):
        """Test all ProblemType enum values."""
        assert ProblemType.CLASSIFICATION == "classification"
        assert ProblemType.BINARY_CLASSIFICATION == "binary_classification"
        assert ProblemType.MULTICLASS_CLASSIFICATION == "multiclass_classification"
        assert ProblemType.REGRESSION == "regression"
        assert ProblemType.CLUSTERING == "clustering"
        assert ProblemType.TIME_SERIES == "time_series"
        assert ProblemType.ANOMALY_DETECTION == "anomaly_detection"


class TestModelStatus:
    """Tests for ModelStatus enum."""

    def test_model_status_values(self):
        """Test all ModelStatus enum values."""
        assert ModelStatus.TRAINING == "training"
        assert ModelStatus.TRAINED == "trained"
        assert ModelStatus.DEPLOYED == "deployed"
        assert ModelStatus.ARCHIVED == "archived"
        assert ModelStatus.FAILED == "failed"


class TestHyperparameterConfig:
    """Tests for HyperparameterConfig model."""

    def test_create_hyperparameter_config_empty(self):
        """Test creating HyperparameterConfig with no parameters."""
        config = HyperparameterConfig()

        assert config.n_estimators is None
        assert config.max_depth is None
        assert config.learning_rate is None
        assert config.random_state is None
        assert config.additional_params == {}

    def test_create_hyperparameter_config_with_common_params(self):
        """Test creating HyperparameterConfig with common parameters."""
        config = HyperparameterConfig(
            n_estimators=100,
            max_depth=10,
            learning_rate=0.01,
            random_state=42
        )

        assert config.n_estimators == 100
        assert config.max_depth == 10
        assert config.learning_rate == 0.01
        assert config.random_state == 42

    def test_hyperparameter_config_validates_positive_estimators(self):
        """Test that n_estimators must be positive."""
        with pytest.raises(ValidationError):
            HyperparameterConfig(n_estimators=0)

        with pytest.raises(ValidationError):
            HyperparameterConfig(n_estimators=-1)

    def test_hyperparameter_config_validates_positive_depth(self):
        """Test that max_depth must be positive."""
        with pytest.raises(ValidationError):
            HyperparameterConfig(max_depth=0)

    def test_hyperparameter_config_validates_positive_learning_rate(self):
        """Test that learning_rate must be positive."""
        with pytest.raises(ValidationError):
            HyperparameterConfig(learning_rate=0.0)

        with pytest.raises(ValidationError):
            HyperparameterConfig(learning_rate=-0.01)

    def test_hyperparameter_config_with_additional_params(self):
        """Test HyperparameterConfig with additional parameters."""
        config = HyperparameterConfig(
            additional_params={
                "min_samples_split": 2,
                "min_samples_leaf": 1,
                "criterion": "gini"
            }
        )

        assert config.additional_params["min_samples_split"] == 2
        assert config.additional_params["criterion"] == "gini"


class TestFeatureConfig:
    """Tests for FeatureConfig model."""

    def test_create_feature_config_minimal(self):
        """Test creating FeatureConfig with minimal fields."""
        config = FeatureConfig(
            feature_names=["age", "income", "education"],
            target_column="salary"
        )

        assert len(config.feature_names) == 3
        assert config.target_column == "salary"
        assert config.engineered_features == []
        assert config.dropped_features == []
        assert config.feature_importance is None

    def test_feature_config_with_all_fields(self):
        """Test creating FeatureConfig with all fields."""
        config = FeatureConfig(
            feature_names=["age", "income", "age_squared"],
            target_column="salary",
            engineered_features=["age_squared"],
            dropped_features=["id", "name"],
            feature_importance={"age": 0.5, "income": 0.3, "age_squared": 0.2},
            numeric_features=["age", "income"],
            categorical_features=[],
            datetime_features=[]
        )

        assert len(config.feature_names) == 3
        assert "age_squared" in config.engineered_features
        assert len(config.dropped_features) == 2
        assert config.feature_importance["age"] == 0.5

    def test_feature_config_feature_types(self):
        """Test FeatureConfig with different feature types."""
        config = FeatureConfig(
            feature_names=["age", "category", "timestamp"],
            target_column="target",
            numeric_features=["age"],
            categorical_features=["category"],
            datetime_features=["timestamp"]
        )

        assert "age" in config.numeric_features
        assert "category" in config.categorical_features
        assert "timestamp" in config.datetime_features


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics model."""

    def test_create_performance_metrics_minimal(self):
        """Test creating PerformanceMetrics with minimal fields."""
        metrics = PerformanceMetrics(
            cv_score=0.85,
            test_score=0.83
        )

        assert metrics.cv_score == 0.85
        assert metrics.test_score == 0.83
        assert metrics.accuracy is None
        assert metrics.additional_metrics == {}

    def test_performance_metrics_classification(self):
        """Test PerformanceMetrics for classification."""
        metrics = PerformanceMetrics(
            cv_score=0.90,
            test_score=0.88,
            accuracy=0.87,
            precision=0.86,
            recall=0.85,
            f1_score=0.855,
            roc_auc=0.92
        )

        assert metrics.accuracy == 0.87
        assert metrics.precision == 0.86
        assert metrics.recall == 0.85
        assert metrics.f1_score == 0.855
        assert metrics.roc_auc == 0.92

    def test_performance_metrics_regression(self):
        """Test PerformanceMetrics for regression."""
        metrics = PerformanceMetrics(
            cv_score=0.85,
            test_score=0.83,
            rmse=12.5,
            mae=8.3,
            r2_score=0.82
        )

        assert metrics.rmse == 12.5
        assert metrics.mae == 8.3
        assert metrics.r2_score == 0.82

    def test_performance_metrics_validates_scores(self):
        """Test that metric scores must be between 0 and 1."""
        with pytest.raises(ValidationError):
            PerformanceMetrics(cv_score=1.5, test_score=0.8)

        with pytest.raises(ValidationError):
            PerformanceMetrics(cv_score=0.8, test_score=-0.1)

    def test_performance_metrics_validates_positive_errors(self):
        """Test that error metrics must be non-negative."""
        with pytest.raises(ValidationError):
            PerformanceMetrics(
                cv_score=0.8,
                test_score=0.75,
                rmse=-10.0
            )

    def test_performance_metrics_with_confusion_matrix(self):
        """Test PerformanceMetrics with confusion matrix."""
        metrics = PerformanceMetrics(
            cv_score=0.90,
            test_score=0.88,
            confusion_matrix=[[45, 5], [3, 47]]
        )

        assert metrics.confusion_matrix is not None
        assert len(metrics.confusion_matrix) == 2
        assert metrics.confusion_matrix[0][0] == 45


class TestTrainingConfig:
    """Tests for TrainingConfig model."""

    def test_create_training_config(self):
        """Test creating TrainingConfig."""
        config = TrainingConfig(
            training_time=120.5,
            n_samples_train=8000,
            n_samples_test=2000
        )

        assert config.training_time == 120.5
        assert config.n_samples_train == 8000
        assert config.n_samples_test == 2000
        assert config.train_test_split == 0.8  # default
        assert config.cv_folds == 5  # default

    def test_training_config_with_all_fields(self):
        """Test TrainingConfig with all fields."""
        config = TrainingConfig(
            train_test_split=0.75,
            cv_folds=10,
            validation_strategy="stratified",
            training_time=300.0,
            n_samples_train=10000,
            n_samples_test=2500,
            early_stopping=True,
            optimization_metric="f1_score"
        )

        assert config.train_test_split == 0.75
        assert config.cv_folds == 10
        assert config.validation_strategy == "stratified"
        assert config.early_stopping is True
        assert config.optimization_metric == "f1_score"

    def test_training_config_validates_split_ratio(self):
        """Test that train_test_split must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TrainingConfig(
                train_test_split=0.0,
                training_time=100.0,
                n_samples_train=1000,
                n_samples_test=200
            )

        with pytest.raises(ValidationError):
            TrainingConfig(
                train_test_split=1.0,
                training_time=100.0,
                n_samples_train=1000,
                n_samples_test=200
            )

    def test_training_config_validates_cv_folds(self):
        """Test that cv_folds must be at least 2."""
        with pytest.raises(ValidationError):
            TrainingConfig(
                cv_folds=1,
                training_time=100.0,
                n_samples_train=1000,
                n_samples_test=200
            )

    def test_training_config_validates_validation_strategy(self):
        """Test that validation_strategy must be valid."""
        with pytest.raises(ValidationError):
            TrainingConfig(
                validation_strategy="invalid_strategy",
                training_time=100.0,
                n_samples_train=1000,
                n_samples_test=200
            )


class TestDeploymentConfig:
    """Tests for DeploymentConfig model."""

    def test_create_deployment_config_default(self):
        """Test creating DeploymentConfig with defaults."""
        config = DeploymentConfig()

        assert config.is_deployed is False
        assert config.deployed_at is None
        assert config.deployment_endpoint is None
        assert config.prediction_count == 0
        assert config.last_prediction_at is None

    def test_deployment_config_deployed(self):
        """Test DeploymentConfig for deployed model."""
        deployed_at = get_current_time()
        config = DeploymentConfig(
            is_deployed=True,
            deployed_at=deployed_at,
            deployment_endpoint="https://api.example.com/predict",
            prediction_count=1000,
            average_prediction_time=50.0,
            error_rate=0.02
        )

        assert config.is_deployed is True
        assert config.deployed_at == deployed_at
        assert config.deployment_endpoint == "https://api.example.com/predict"
        assert config.prediction_count == 1000
        assert config.average_prediction_time == 50.0
        assert config.error_rate == 0.02


class TestModelConfig:
    """Tests for ModelConfig model."""

    def test_model_settings(self):
        """Test ModelConfig model settings."""
        assert ModelConfig.Settings.name == "model_configs"
        assert "user_id" in ModelConfig.Settings.indexes
        assert "dataset_id" in ModelConfig.Settings.indexes
        assert "model_id" in ModelConfig.Settings.indexes

    def test_model_config_model_config(self):
        """Test ModelConfig model configuration."""
        assert ModelConfig.model_config["populate_by_name"] is True
        assert ModelConfig.model_config["arbitrary_types_allowed"] is True

    def test_create_model_config_minimal(self):
        """Test creating ModelConfig with minimal fields."""
        feature_config = FeatureConfig(
            feature_names=["age", "income"],
            target_column="salary"
        )
        training_config = TrainingConfig(
            training_time=100.0,
            n_samples_train=1000,
            n_samples_test=200
        )
        performance_metrics = PerformanceMetrics(
            cv_score=0.85,
            test_score=0.83
        )

        model = ModelConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            model_id="model_789",
            name="Test Model",
            problem_type=ProblemType.REGRESSION,
            algorithm="Random Forest",
            feature_config=feature_config,
            training_config=training_config,
            performance_metrics=performance_metrics,
            model_path="s3://bucket/model.pkl",
            model_size=1024000
        )

        assert model.user_id == "user_123"
        assert model.dataset_id == "dataset_456"
        assert model.model_id == "model_789"
        assert model.name == "Test Model"
        assert model.problem_type == ProblemType.REGRESSION
        assert model.algorithm == "Random Forest"

    def test_model_config_default_values(self):
        """Test ModelConfig default values."""
        feature_config = FeatureConfig(
            feature_names=["f1"],
            target_column="target"
        )
        training_config = TrainingConfig(
            training_time=100.0,
            n_samples_train=1000,
            n_samples_test=200
        )
        performance_metrics = PerformanceMetrics(
            cv_score=0.85,
            test_score=0.83
        )

        model = ModelConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            model_id="model_789",
            name="Test",
            problem_type=ProblemType.CLASSIFICATION,
            algorithm="Logistic Regression",
            feature_config=feature_config,
            training_config=training_config,
            performance_metrics=performance_metrics,
            model_path="s3://bucket/model.pkl",
            model_size=1024
        )

        assert model.status == ModelStatus.TRAINING
        assert model.version == "1.0.0"
        assert model.is_active is True
        assert model.tags == []


class TestModelConfigHelperMethods:
    """Test helper methods for ModelConfig."""

    def create_test_model(self):
        """Helper to create a test model."""
        return ModelConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            model_id="model_789",
            name="Test Model",
            problem_type=ProblemType.CLASSIFICATION,
            algorithm="Random Forest",
            feature_config=FeatureConfig(
                feature_names=["age", "income"],
                target_column="target",
                feature_importance={"age": 0.6, "income": 0.4}
            ),
            training_config=TrainingConfig(
                training_time=120.0,
                n_samples_train=1000,
                n_samples_test=200
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.90,
                test_score=0.88,
                accuracy=0.87
            ),
            model_path="s3://bucket/model.pkl",
            model_size=1024000
        )

    def test_update_timestamp_method(self):
        """Test update_timestamp() method."""
        model = self.create_test_model()

        original_updated_at = model.updated_at
        import time
        time.sleep(0.01)
        model.update_timestamp()

        assert model.updated_at > original_updated_at

    def test_mark_trained_method(self):
        """Test mark_trained() method."""
        model = self.create_test_model()

        assert model.status == ModelStatus.TRAINING
        assert model.trained_at is None

        model.mark_trained()

        assert model.status == ModelStatus.TRAINED
        assert isinstance(model.trained_at, datetime)

    def test_mark_deployed_method(self):
        """Test mark_deployed() method."""
        model = self.create_test_model()

        model.mark_deployed("https://api.example.com/predict")

        assert model.status == ModelStatus.DEPLOYED
        assert model.deployment_config is not None
        assert model.deployment_config.is_deployed is True
        assert model.deployment_config.deployment_endpoint == "https://api.example.com/predict"

    def test_mark_archived_method(self):
        """Test mark_archived() method."""
        model = self.create_test_model()

        model.mark_archived()

        assert model.status == ModelStatus.ARCHIVED
        assert model.is_active is False

    def test_mark_failed_method(self):
        """Test mark_failed() method."""
        model = self.create_test_model()

        model.mark_failed()

        assert model.status == ModelStatus.FAILED
        assert model.is_active is False

    def test_record_prediction_method(self):
        """Test record_prediction() method."""
        model = self.create_test_model()
        model.deployment_config = DeploymentConfig()

        model.record_prediction(prediction_time_ms=45.5)

        assert model.deployment_config.prediction_count == 1
        assert model.deployment_config.average_prediction_time == 45.5
        assert isinstance(model.last_used_at, datetime)

    def test_record_multiple_predictions(self):
        """Test recording multiple predictions with running average."""
        model = self.create_test_model()
        model.deployment_config = DeploymentConfig()

        model.record_prediction(50.0)
        model.record_prediction(60.0)
        model.record_prediction(40.0)

        assert model.deployment_config.prediction_count == 3
        assert model.deployment_config.average_prediction_time == 50.0  # (50+60+40)/3

    def test_get_feature_importance_sorted(self):
        """Test get_feature_importance_sorted() method."""
        model = self.create_test_model()

        sorted_features = model.get_feature_importance_sorted()

        assert len(sorted_features) == 2
        assert sorted_features[0] == ("age", 0.6)
        assert sorted_features[1] == ("income", 0.4)

    def test_get_feature_importance_sorted_empty(self):
        """Test get_feature_importance_sorted() with no importance."""
        model = self.create_test_model()
        model.feature_config.feature_importance = None

        sorted_features = model.get_feature_importance_sorted()

        assert sorted_features == []

    def test_get_top_features(self):
        """Test get_top_features() method."""
        model = self.create_test_model()

        top_features = model.get_top_features(n=1)

        assert len(top_features) == 1
        assert top_features[0] == "age"

    def test_get_performance_summary_classification(self):
        """Test get_performance_summary() for classification."""
        model = self.create_test_model()
        model.problem_type = ProblemType.CLASSIFICATION
        model.performance_metrics.f1_score = 0.86
        model.performance_metrics.roc_auc = 0.91

        summary = model.get_performance_summary()

        assert "cv_score" in summary
        assert "test_score" in summary
        assert "accuracy" in summary
        assert "f1_score" in summary
        assert "roc_auc" in summary
        assert summary["accuracy"] == 0.87

    def test_get_performance_summary_regression(self):
        """Test get_performance_summary() for regression."""
        model = self.create_test_model()
        model.problem_type = ProblemType.REGRESSION
        model.performance_metrics.rmse = 12.5
        model.performance_metrics.r2_score = 0.82

        summary = model.get_performance_summary()

        assert "cv_score" in summary
        assert "test_score" in summary
        assert "rmse" in summary
        assert "r2_score" in summary
        assert summary["rmse"] == 12.5

    def test_is_deployed_method(self):
        """Test is_deployed() method."""
        model = self.create_test_model()

        assert model.is_deployed() is False

        model.mark_deployed("https://api.example.com/predict")

        assert model.is_deployed() is True

    def test_get_training_duration_formatted(self):
        """Test get_training_duration_formatted() method."""
        model = self.create_test_model()

        # Test seconds
        model.training_config.training_time = 45.0
        assert model.get_training_duration_formatted() == "45.0s"

        # Test minutes
        model.training_config.training_time = 150.0
        formatted = model.get_training_duration_formatted()
        assert "m" in formatted

        # Test hours
        model.training_config.training_time = 7200.0
        formatted = model.get_training_duration_formatted()
        assert "h" in formatted


class TestModelConfigEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_model_with_all_optional_fields(self):
        """Test ModelConfig with all optional fields populated."""
        model = ModelConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            model_id="model_789",
            name="Complete Model",
            description="A fully populated model configuration",
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            algorithm="XGBoost",
            hyperparameters=HyperparameterConfig(
                n_estimators=200,
                max_depth=10,
                learning_rate=0.01
            ),
            feature_config=FeatureConfig(
                feature_names=["f1", "f2"],
                target_column="target"
            ),
            training_config=TrainingConfig(
                training_time=300.0,
                n_samples_train=10000,
                n_samples_test=2500
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.92,
                test_score=0.90
            ),
            model_path="s3://bucket/model.pkl",
            model_file_url="https://bucket.s3.amazonaws.com/model.pkl",
            feature_transformer_path="s3://bucket/transformer.pkl",
            model_size=2048000,
            status=ModelStatus.DEPLOYED,
            deployment_config=DeploymentConfig(is_deployed=True),
            version="2.1.0",
            is_active=True,
            parent_model_id="model_000",
            tags=["production", "v2"],
            notes="Important production model"
        )

        assert model.description == "A fully populated model configuration"
        assert model.hyperparameters.n_estimators == 200
        assert model.feature_transformer_path == "s3://bucket/transformer.pkl"
        assert len(model.tags) == 2
        assert model.parent_model_id == "model_000"

    def test_model_lifecycle_transitions(self):
        """Test full model lifecycle state transitions."""
        model = ModelConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            model_id="model_789",
            name="Lifecycle Test",
            problem_type=ProblemType.CLASSIFICATION,
            algorithm="Random Forest",
            feature_config=FeatureConfig(
                feature_names=["f1"],
                target_column="target"
            ),
            training_config=TrainingConfig(
                training_time=100.0,
                n_samples_train=1000,
                n_samples_test=200
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.85,
                test_score=0.83
            ),
            model_path="s3://bucket/model.pkl",
            model_size=1024
        )

        # Training -> Trained
        assert model.status == ModelStatus.TRAINING
        model.mark_trained()
        assert model.status == ModelStatus.TRAINED

        # Trained -> Deployed
        model.mark_deployed()
        assert model.status == ModelStatus.DEPLOYED
        assert model.is_deployed()

        # Deployed -> Archived
        model.mark_archived()
        assert model.status == ModelStatus.ARCHIVED
        assert not model.is_active

    def test_model_with_no_feature_importance(self):
        """Test model operations when feature_importance is None."""
        model = ModelConfig.model_construct(
            user_id="user_123",
            dataset_id="dataset_456",
            model_id="model_789",
            name="No Importance",
            problem_type=ProblemType.REGRESSION,
            algorithm="Linear Regression",
            feature_config=FeatureConfig(
                feature_names=["f1", "f2"],
                target_column="target",
                feature_importance=None
            ),
            training_config=TrainingConfig(
                training_time=50.0,
                n_samples_train=500,
                n_samples_test=100
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.75,
                test_score=0.73
            ),
            model_path="s3://bucket/model.pkl",
            model_size=512
        )

        assert model.get_feature_importance_sorted() == []
        assert model.get_top_features(n=5) == []
