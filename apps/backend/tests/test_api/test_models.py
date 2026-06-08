"""
TDD Tests for Model API Routes (Task 1.3)

Following strict TDD methodology:
1. RED: Write failing test
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve code quality

Tests cover model lifecycle endpoints using ModelService.
"""

import pytest
import uuid

from app.models.model import ProblemType


@pytest.mark.integration
class TestModelRoutes:
    """Integration tests for Model API routes using ModelService."""

    # =====================================================================
    # POST /api/v1/models/train - Train Model (Create ModelConfig)
    # =====================================================================

    @pytest.mark.asyncio
    async def test_train_model_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test successful model training initiation using ModelService.
        Should create ModelConfig with TRAINING status and return training response.
        """
        # ARRANGE: Create test dataset
        from app.services.dataset_service import DatasetService
        from app.models.dataset import SchemaField

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="train_dataset",
            filename="train_data.csv",
            original_filename="train_data.csv",
            file_type="csv",
            file_path="datasets/train_data.csv",
            s3_url="s3://bucket/train_data.csv",
            num_rows=1000,
            num_columns=10,
            columns=["feature1", "feature2", "target"],
            data_schema=[
                SchemaField(
                    field_name="target",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=2,
                    missing_values=0
                )
            ]
        )

        # ACT: Train model
        request_data = {
            "dataset_id": dataset.dataset_id,
            "name": "Test Classification Model",
            "description": "Test model for binary classification",
            "problem_type": "binary_classification",
            "algorithm": "Random Forest",
            "target_column": "target",
            "feature_columns": ["feature1", "feature2"],
            "train_test_split": 0.8,
            "cv_folds": 5,
            "validation_strategy": "k-fold",
            "hyperparameters": {"n_estimators": 100, "max_depth": 10},
            "early_stopping": False,
            "optimization_metric": "accuracy"
        }

        response = await async_authorized_client.post(
            "/api/v1/models/train",
            json=request_data
        )

        # ASSERT: Verify training response
        assert response.status_code == 201
        data = response.json()

        assert "model_id" in data
        assert data["status"] == "training"
        assert "message" in data
        assert "training_time" in data
        assert "performance_metrics" in data

    @pytest.mark.asyncio
    async def test_train_model_dataset_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model training with non-existent dataset.
        Should return 404 error.
        """
        # ACT: Attempt to train with invalid dataset
        request_data = {
            "dataset_id": "nonexistent_dataset",
            "name": "Test Model",
            "problem_type": "binary_classification",
            "algorithm": "Random Forest",
            "target_column": "target",
            "feature_columns": ["feature1"],
            "train_test_split": 0.8,
            "cv_folds": 5
        }

        response = await async_authorized_client.post(
            "/api/v1/models/train",
            json=request_data
        )

        # ASSERT: Verify 404 error
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_train_model_invalid_problem_type(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model training with invalid problem type.
        Should return 422 validation error.
        """
        # ARRANGE: Create dataset
        from app.services.dataset_service import DatasetService
        from app.models.dataset import SchemaField

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="validation_dataset",
            filename="validation_data.csv",
            original_filename="validation_data.csv",
            file_type="csv",
            file_path="datasets/validation_data.csv",
            s3_url="s3://bucket/validation_data.csv",
            num_rows=100,
            num_columns=5,
            columns=["col1", "target"],
            data_schema=[
                SchemaField(
                    field_name="target",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=2,
                    missing_values=0
                )
            ]
        )

        # ACT: Attempt training with invalid problem type
        request_data = {
            "dataset_id": dataset.dataset_id,
            "name": "Test Model",
            "problem_type": "invalid_type",  # Invalid
            "algorithm": "Random Forest",
            "target_column": "target",
            "feature_columns": ["col1"],
            "train_test_split": 0.8,
            "cv_folds": 5
        }

        response = await async_authorized_client.post(
            "/api/v1/models/train",
            json=request_data
        )

        # ASSERT: Verify validation error
        assert response.status_code == 422

    # =====================================================================
    # GET /api/v1/models/{model_id} - Retrieve Model
    # =====================================================================

    @pytest.mark.asyncio
    async def test_get_model_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test successful model retrieval using ModelService.
        Should return complete ModelConfig details.
        """
        # ARRANGE: Create model using ModelService
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics,
            HyperparameterConfig
        )

        model_service = ModelService()
        model_id = f"model_{uuid.uuid4().hex[:8]}"

        await model_service.create_model_config(
            user_id="test_user_123",
            dataset_id="test_dataset",
            model_id=model_id,
            name="Test Model",
            description="Test model description",
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            algorithm="Random Forest",
            feature_config=FeatureConfig(
                feature_names=["feature1", "feature2"],
                target_column="target",
                numeric_features=["feature1", "feature2"]
            ),
            training_config=TrainingConfig(
                train_test_split=0.8,
                cv_folds=5,
                validation_strategy="k-fold",
                training_time=45.5,
                n_samples_train=800,
                n_samples_test=200,
                early_stopping=False,
                optimization_metric="accuracy"
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.85,
                test_score=0.83,
                accuracy=0.83,
                precision=0.84,
                recall=0.82,
                f1_score=0.83
            ),
            model_path="models/test_model.pkl",
            model_size=1024000,
            hyperparameters=HyperparameterConfig(
                n_estimators=100,
                max_depth=10
            )
        )

        # ACT: Retrieve model
        response = await async_authorized_client.get(f"/api/v1/models/{model_id}")

        # ASSERT: Verify model details
        assert response.status_code == 200
        data = response.json()

        assert data["model_id"] == model_id
        assert data["name"] == "Test Model"
        assert data["description"] == "Test model description"
        assert data["problem_type"] == "binary_classification"
        assert data["algorithm"] == "Random Forest"
        assert data["status"] == "training"
        assert "feature_config" in data
        assert "training_config" in data
        assert "performance_metrics" in data

    @pytest.mark.asyncio
    async def test_get_model_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model retrieval with non-existent ID.
        Should return 404 error.
        """
        # ACT: Attempt to retrieve non-existent model
        response = await async_authorized_client.get("/api/v1/models/nonexistent_model")

        # ASSERT: Verify 404 error
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    # =====================================================================
    # GET /api/v1/models - List Models
    # =====================================================================

    @pytest.mark.asyncio
    async def test_list_models_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test successful model listing using ModelService.
        Should return list of models for authenticated user.
        """
        # ARRANGE: Create multiple models
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()

        # Create 3 test models
        for i in range(3):
            await model_service.create_model_config(
                user_id="test_user_123",
                dataset_id=f"dataset_{i}",
                model_id=f"model_{uuid.uuid4().hex[:8]}",
                name=f"Test Model {i}",
                problem_type=ProblemType.CLASSIFICATION,
                algorithm="Random Forest",
                feature_config=FeatureConfig(
                    feature_names=["feature1"],
                    target_column="target"
                ),
                training_config=TrainingConfig(
                    training_time=30.0,
                    n_samples_train=800,
                    n_samples_test=200
                ),
                performance_metrics=PerformanceMetrics(
                    cv_score=0.85,
                    test_score=0.83
                ),
                model_path=f"models/model_{i}.pkl",
                model_size=1024000
            )

        # ACT: List models
        response = await async_authorized_client.get("/api/v1/models")

        # ASSERT: Verify model list
        assert response.status_code == 200
        data = response.json()

        assert "models" in data
        assert "total" in data
        assert data["total"] >= 3
        assert len(data["models"]) >= 3

        # Verify model list items have required fields
        first_model = data["models"][0]
        assert "model_id" in first_model
        assert "name" in first_model
        assert "problem_type" in first_model
        assert "algorithm" in first_model
        assert "status" in first_model
        assert "test_score" in first_model
        assert "created_at" in first_model

    @pytest.mark.asyncio
    async def test_list_models_filter_by_dataset(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model listing filtered by dataset_id.
        Should return only models for specified dataset.
        """
        # ARRANGE: Create models for different datasets
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()
        target_dataset = "target_dataset_123"

        # Create 2 models for target dataset
        for i in range(2):
            await model_service.create_model_config(
                user_id="test_user_123",
                dataset_id=target_dataset,
                model_id=f"target_model_{uuid.uuid4().hex[:8]}",
                name=f"Target Model {i}",
                problem_type=ProblemType.REGRESSION,
                algorithm="Linear Regression",
                feature_config=FeatureConfig(
                    feature_names=["feature1"],
                    target_column="target"
                ),
                training_config=TrainingConfig(
                    training_time=20.0,
                    n_samples_train=500,
                    n_samples_test=100
                ),
                performance_metrics=PerformanceMetrics(
                    cv_score=0.75,
                    test_score=0.73
                ),
                model_path=f"models/target_{i}.pkl",
                model_size=512000
            )

        # Create 1 model for different dataset
        await model_service.create_model_config(
            user_id="test_user_123",
            dataset_id="other_dataset",
            model_id=f"other_model_{uuid.uuid4().hex[:8]}",
            name="Other Model",
            problem_type=ProblemType.REGRESSION,
            algorithm="Linear Regression",
            feature_config=FeatureConfig(
                feature_names=["feature1"],
                target_column="target"
            ),
            training_config=TrainingConfig(
                training_time=20.0,
                n_samples_train=500,
                n_samples_test=100
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.70,
                test_score=0.68
            ),
            model_path="models/other.pkl",
            model_size=512000
        )

        # ACT: List models filtered by dataset
        response = await async_authorized_client.get(
            f"/api/v1/models?dataset_id={target_dataset}"
        )

        # ASSERT: Verify only target dataset models returned
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        for model in data["models"]:
            # Note: ModelListItem doesn't include dataset_id in schema
            # We verify by checking the count matches what we created
            pass

    @pytest.mark.asyncio
    async def test_list_models_filter_by_status(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model listing filtered by status.
        Should return only models with specified status.
        """
        # ARRANGE: Create models and mark some as trained
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()

        # Create 2 training models
        training_ids = []
        for i in range(2):
            model_id = f"training_model_{uuid.uuid4().hex[:8]}"
            await model_service.create_model_config(
                user_id="test_user_123",
                dataset_id="test_dataset",
                model_id=model_id,
                name=f"Training Model {i}",
                problem_type=ProblemType.CLASSIFICATION,
                algorithm="XGBoost",
                feature_config=FeatureConfig(
                    feature_names=["feature1"],
                    target_column="target"
                ),
                training_config=TrainingConfig(
                    training_time=30.0,
                    n_samples_train=700,
                    n_samples_test=300
                ),
                performance_metrics=PerformanceMetrics(
                    cv_score=0.88,
                    test_score=0.86
                ),
                model_path=f"models/training_{i}.pkl",
                model_size=2048000
            )
            training_ids.append(model_id)

        # Create 1 trained model
        trained_id = f"trained_model_{uuid.uuid4().hex[:8]}"
        await model_service.create_model_config(
            user_id="test_user_123",
            dataset_id="test_dataset",
            model_id=trained_id,
            name="Trained Model",
            problem_type=ProblemType.CLASSIFICATION,
            algorithm="XGBoost",
            feature_config=FeatureConfig(
                feature_names=["feature1"],
                target_column="target"
            ),
            training_config=TrainingConfig(
                training_time=30.0,
                n_samples_train=700,
                n_samples_test=300
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.88,
                test_score=0.86
            ),
            model_path="models/trained.pkl",
            model_size=2048000
        )
        await model_service.mark_model_trained(trained_id)

        # ACT: List models filtered by status=trained
        response = await async_authorized_client.get("/api/v1/models?status=trained")

        # ASSERT: Verify only trained models returned
        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 1
        for model in data["models"]:
            assert model["status"] == "trained"

    @pytest.mark.asyncio
    async def test_list_models_pagination(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model listing with pagination.
        Should respect page and limit parameters.
        """
        # ARRANGE: Create 25 models
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()

        for i in range(25):
            await model_service.create_model_config(
                user_id="test_user_123",
                dataset_id="pagination_dataset",
                model_id=f"pagination_model_{i}_{uuid.uuid4().hex[:8]}",
                name=f"Pagination Model {i}",
                problem_type=ProblemType.CLASSIFICATION,
                algorithm="Decision Tree",
                feature_config=FeatureConfig(
                    feature_names=["feature1"],
                    target_column="target"
                ),
                training_config=TrainingConfig(
                    training_time=10.0,
                    n_samples_train=400,
                    n_samples_test=100
                ),
                performance_metrics=PerformanceMetrics(
                    cv_score=0.80,
                    test_score=0.78
                ),
                model_path=f"models/pagination_{i}.pkl",
                model_size=256000
            )

        # ACT: Request page 1 with limit 10
        response = await async_authorized_client.get("/api/v1/models?page=1&limit=10")

        # ASSERT: Verify pagination
        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 25
        assert len(data["models"]) <= 10

    # =====================================================================
    # PUT /api/v1/models/{model_id} - Update Model
    # =====================================================================

    @pytest.mark.asyncio
    async def test_update_model_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test successful model update using ModelService.
        Should update metadata fields and return updated model.
        """
        # ARRANGE: Create model
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()
        model_id = f"update_model_{uuid.uuid4().hex[:8]}"

        await model_service.create_model_config(
            user_id="test_user_123",
            dataset_id="test_dataset",
            model_id=model_id,
            name="Original Name",
            description="Original description",
            problem_type=ProblemType.CLASSIFICATION,
            algorithm="Random Forest",
            feature_config=FeatureConfig(
                feature_names=["feature1"],
                target_column="target"
            ),
            training_config=TrainingConfig(
                training_time=30.0,
                n_samples_train=800,
                n_samples_test=200
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.85,
                test_score=0.83
            ),
            model_path="models/update_test.pkl",
            model_size=1024000
        )

        # ACT: Update model
        update_data = {
            "name": "Updated Name",
            "description": "Updated description",
            "tags": ["production", "v1.0"],
            "notes": "Updated notes"
        }

        response = await async_authorized_client.put(
            f"/api/v1/models/{model_id}",
            json=update_data
        )

        # ASSERT: Verify update
        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert "production" in data["tags"]
        assert data["notes"] == "Updated notes"

    @pytest.mark.asyncio
    async def test_update_model_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model update with non-existent ID.
        Should return 404 error.
        """
        # ACT: Attempt to update non-existent model
        update_data = {
            "name": "Updated Name"
        }

        response = await async_authorized_client.put(
            "/api/v1/models/nonexistent_model",
            json=update_data
        )

        # ASSERT: Verify 404 error
        assert response.status_code == 404

    # =====================================================================
    # GET /api/v1/models/{model_id}/performance - Performance Metrics
    # =====================================================================

    @pytest.mark.asyncio
    async def test_get_performance_metrics_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test successful performance metrics retrieval.
        Should return complete PerformanceMetrics from ModelConfig.
        """
        # ARRANGE: Create model with performance metrics
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()
        model_id = f"perf_model_{uuid.uuid4().hex[:8]}"

        await model_service.create_model_config(
            user_id="test_user_123",
            dataset_id="test_dataset",
            model_id=model_id,
            name="Performance Test Model",
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            algorithm="Logistic Regression",
            feature_config=FeatureConfig(
                feature_names=["feature1", "feature2", "feature3"],
                target_column="target"
            ),
            training_config=TrainingConfig(
                training_time=25.0,
                n_samples_train=900,
                n_samples_test=100
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.92,
                test_score=0.90,
                accuracy=0.90,
                precision=0.91,
                recall=0.89,
                f1_score=0.90,
                roc_auc=0.95,
                confusion_matrix=[[80, 10], [5, 5]]
            ),
            model_path="models/perf_test.pkl",
            model_size=512000
        )

        # ACT: Get performance metrics
        response = await async_authorized_client.get(
            f"/api/v1/models/{model_id}/performance"
        )

        # ASSERT: Verify metrics
        assert response.status_code == 200
        data = response.json()

        assert data["cv_score"] == 0.92
        assert data["test_score"] == 0.90
        assert data["accuracy"] == 0.90
        assert data["precision"] == 0.91
        assert data["recall"] == 0.89
        assert data["f1_score"] == 0.90
        assert data["roc_auc"] == 0.95
        assert data["confusion_matrix"] == [[80, 10], [5, 5]]

    @pytest.mark.asyncio
    async def test_get_performance_metrics_regression(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test performance metrics for regression model.
        Should return regression-specific metrics (rmse, mae, r2_score).
        """
        # ARRANGE: Create regression model
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()
        model_id = f"regression_model_{uuid.uuid4().hex[:8]}"

        await model_service.create_model_config(
            user_id="test_user_123",
            dataset_id="test_dataset",
            model_id=model_id,
            name="Regression Test Model",
            problem_type=ProblemType.REGRESSION,
            algorithm="Linear Regression",
            feature_config=FeatureConfig(
                feature_names=["feature1", "feature2"],
                target_column="price"
            ),
            training_config=TrainingConfig(
                training_time=15.0,
                n_samples_train=800,
                n_samples_test=200
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.85,
                test_score=0.83,
                rmse=12.5,
                mae=8.3,
                r2_score=0.83
            ),
            model_path="models/regression_test.pkl",
            model_size=256000
        )

        # ACT: Get performance metrics
        response = await async_authorized_client.get(
            f"/api/v1/models/{model_id}/performance"
        )

        # ASSERT: Verify regression metrics
        assert response.status_code == 200
        data = response.json()

        assert data["cv_score"] == 0.85
        assert data["test_score"] == 0.83
        assert data["rmse"] == 12.5
        assert data["mae"] == 8.3
        assert data["r2_score"] == 0.83

    @pytest.mark.asyncio
    async def test_get_performance_metrics_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test performance metrics retrieval for non-existent model.
        Should return 404 error.
        """
        # ACT: Attempt to get metrics for non-existent model
        response = await async_authorized_client.get(
            "/api/v1/models/nonexistent_model/performance"
        )

        # ASSERT: Verify 404 error
        assert response.status_code == 404

    # =====================================================================
    # PUT /api/v1/models/{model_id}/deploy - Deploy Model
    # =====================================================================

    @pytest.mark.asyncio
    async def test_deploy_model_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test successful model deployment (TRAINED → DEPLOYED).
        Should update status and deployment configuration.
        """
        # ARRANGE: Create trained model
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()
        model_id = f"deploy_model_{uuid.uuid4().hex[:8]}"

        await model_service.create_model_config(
            user_id="test_user_123",
            dataset_id="test_dataset",
            model_id=model_id,
            name="Deploy Test Model",
            problem_type=ProblemType.CLASSIFICATION,
            algorithm="Random Forest",
            feature_config=FeatureConfig(
                feature_names=["feature1"],
                target_column="target"
            ),
            training_config=TrainingConfig(
                training_time=30.0,
                n_samples_train=800,
                n_samples_test=200
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.85,
                test_score=0.83
            ),
            model_path="models/deploy_test.pkl",
            model_size=1024000
        )

        # Mark as trained
        await model_service.mark_model_trained(model_id)

        # ACT: Deploy model
        deploy_data = {
            "endpoint": "https://api.example.com/models/deploy_test"
        }

        response = await async_authorized_client.put(
            f"/api/v1/models/{model_id}/deploy",
            json=deploy_data
        )

        # ASSERT: Verify deployment
        assert response.status_code == 200
        data = response.json()

        assert data["model_id"] == model_id
        assert data["status"] == "deployed"
        assert "deployed_at" in data
        assert data["deployment_endpoint"] == "https://api.example.com/models/deploy_test"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_deploy_model_not_trained(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model deployment when status is not TRAINED.
        Should return 400 Bad Request (invalid state transition).
        """
        # ARRANGE: Create model in TRAINING state (not TRAINED)
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()
        model_id = f"untrained_model_{uuid.uuid4().hex[:8]}"

        await model_service.create_model_config(
            user_id="test_user_123",
            dataset_id="test_dataset",
            model_id=model_id,
            name="Untrained Model",
            problem_type=ProblemType.CLASSIFICATION,
            algorithm="Random Forest",
            feature_config=FeatureConfig(
                feature_names=["feature1"],
                target_column="target"
            ),
            training_config=TrainingConfig(
                training_time=30.0,
                n_samples_train=800,
                n_samples_test=200
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.85,
                test_score=0.83
            ),
            model_path="models/untrained.pkl",
            model_size=1024000
        )

        # ACT: Attempt to deploy untrained model
        deploy_data = {
            "endpoint": "https://api.example.com/models/untrained"
        }

        response = await async_authorized_client.put(
            f"/api/v1/models/{model_id}/deploy",
            json=deploy_data
        )

        # ASSERT: Verify 400 error
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "trained" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_deploy_model_already_deployed(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model deployment when already deployed.
        Should return 409 Conflict.
        """
        # ARRANGE: Create and deploy model
        from app.services.model_service import ModelService
        from app.models.model import (
            FeatureConfig, TrainingConfig, PerformanceMetrics
        )

        model_service = ModelService()
        model_id = f"already_deployed_{uuid.uuid4().hex[:8]}"

        await model_service.create_model_config(
            user_id="test_user_123",
            dataset_id="test_dataset",
            model_id=model_id,
            name="Already Deployed Model",
            problem_type=ProblemType.CLASSIFICATION,
            algorithm="Random Forest",
            feature_config=FeatureConfig(
                feature_names=["feature1"],
                target_column="target"
            ),
            training_config=TrainingConfig(
                training_time=30.0,
                n_samples_train=800,
                n_samples_test=200
            ),
            performance_metrics=PerformanceMetrics(
                cv_score=0.85,
                test_score=0.83
            ),
            model_path="models/already_deployed.pkl",
            model_size=1024000
        )

        # Mark as trained and deployed
        await model_service.mark_model_trained(model_id)
        await model_service.mark_model_deployed(model_id, "https://api.example.com/v1")

        # ACT: Attempt to deploy again
        deploy_data = {
            "endpoint": "https://api.example.com/v2"
        }

        response = await async_authorized_client.put(
            f"/api/v1/models/{model_id}/deploy",
            json=deploy_data
        )

        # ASSERT: Verify 409 conflict
        assert response.status_code == 409
        data = response.json()
        assert "detail" in data
        assert "already deployed" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_deploy_model_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test model deployment for non-existent model.
        Should return 404 error.
        """
        # ACT: Attempt to deploy non-existent model
        deploy_data = {
            "endpoint": "https://api.example.com/models/nonexistent"
        }

        response = await async_authorized_client.put(
            "/api/v1/models/nonexistent_model/deploy",
            json=deploy_data
        )

        # ASSERT: Verify 404 error
        assert response.status_code == 404
