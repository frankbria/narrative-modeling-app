"""
Tests for model training API endpoints
"""

import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio

from app.models.ml_model import MLModel
from app.services.model_training import ProblemType
from app.services.model_training.automl_engine import AutoMLResult, ModelCandidate


@pytest.fixture
def sample_dataset():
    """Create a sample dataset mock"""
    mock_dataset = MagicMock()
    mock_dataset.id = "dataset_123"
    mock_dataset.user_id = "test_user"
    mock_dataset.filename = "test_data.csv"
    mock_dataset.file_type = "csv"
    mock_dataset.num_rows = 100
    mock_dataset.data_schema = []
    mock_dataset.file_key = "uploads/test_user/test_data.csv"
    mock_dataset.s3_url = "s3://test-bucket/uploads/test_user/test_data.csv"
    mock_dataset.created_at = datetime.now(UTC)
    return mock_dataset


@pytest.fixture
def sample_ml_model():
    """Create a sample ML model mock"""
    import uuid

    from beanie import PydanticObjectId

    mock_model = MagicMock()
    mock_model._id = PydanticObjectId()
    mock_model.revision_id = uuid.uuid4()
    mock_model.user_id = "test_user"
    mock_model.dataset_id = "dataset_123"
    mock_model.model_id = "model_123"
    mock_model.name = "Test Model"
    mock_model.description = "Test model description"
    mock_model.problem_type = "binary_classification"
    mock_model.algorithm = "Random Forest"
    mock_model.target_column = "target"
    mock_model.feature_names = ["feature1", "feature2", "feature3"]
    mock_model.cv_score = 0.85
    mock_model.test_score = 0.83
    mock_model.training_time = 45.2
    mock_model.model_size = 1048576
    mock_model.n_samples_train = 1000
    mock_model.n_features = 3
    mock_model.model_path = "s3://bucket/models/model_123.pkl"
    mock_model.feature_transformer_path = "s3://bucket/transformers/transformer_123.pkl"
    mock_model.evaluation_data_path = None
    mock_model.metrics = {"accuracy": 0.85, "f1": 0.83}
    mock_model.feature_importance = {"feature1": 0.5, "feature2": 0.3, "feature3": 0.2}
    # Confidence/uncertainty metadata (issue #83) — defaults for a pre-#83-style model.
    mock_model.is_calibrated = False
    mock_model.calibration_method = None
    mock_model.calibration_score = None
    # Calibration/eval honesty flags (issue #201) — defaults for a pre-#201 model.
    mock_model.calibration_score_is_insample = True
    mock_model.evaluation_on_calibration_set = False
    mock_model.residual_std = None
    # SHAP interpretability metadata (issue #80) — defaults for a pre-#80 model.
    mock_model.shap_values_path = None
    mock_model.shap_explainer_type = None
    # Hyperparameter tuning metadata (issue #77) — defaults for an untuned model.
    mock_model.tuning_strategy = None
    mock_model.tuning_time = None
    mock_model.improvement_from_tuning = None
    mock_model.tuning_results = None
    # Versioning & lineage metadata (issue #78) — defaults for a pre-#78 model.
    mock_model.parent_model_id = None
    mock_model.is_production = False
    mock_model.promoted_at = None
    mock_model.environment_metadata = None
    mock_model.dataset_version_id = None
    mock_model.version_notes = None
    mock_model.training_config = {"max_models": 5, "cv_folds": 5}
    mock_model.version = "1.0.0"
    mock_model.created_at = datetime.now(UTC)
    mock_model.updated_at = datetime.now(UTC)
    mock_model.last_used_at = None
    mock_model.is_active = True
    # Deployment fields (issue #84) — required so response_model=MLModel validates.
    mock_model.is_deployed = False
    mock_model.deployment_endpoint = None
    mock_model.deployed_at = None
    mock_model.save = AsyncMock()
    return mock_model


@pytest.fixture
def sample_dataframe():
    """Create a sample dataframe"""
    np.random.seed(42)
    return pd.DataFrame(
        {
            "feature1": np.random.randn(100),
            "feature2": np.random.randn(100),
            "feature3": np.random.choice(["A", "B", "C"], 100),
            "target": np.random.choice([0, 1], 100),
        }
    )


class TestModelTrainingEndpoints:
    """Test model training API endpoints"""

    @pytest.mark.asyncio
    async def test_train_model_endpoint_real_lookup(self, async_authorized_client):
        """The dataset lookup matches a real UserData document by id string.

        Regression (found during #76 demo): UserData.id is an ObjectId, so
        comparing it to the raw request string never matched and every real
        train request 404'd. The endpoint must coerce the id.
        """
        from app.models.user_data import UserData

        dataset = UserData(
            user_id="test_user_123",
            filename="demo.csv",
            original_filename="demo.csv",
            s3_url="s3://test-bucket/demo.csv",
            num_rows=10,
            num_columns=2,
            data_schema=[],
        )
        await dataset.insert()
        try:
            with patch(
                "app.api.routes.model_training.train_model_task",
                new_callable=AsyncMock,
            ):
                response = await async_authorized_client.post(
                    "/api/v1/ml/train",
                    json={
                        "dataset_id": str(dataset.id),
                        "target_column": "target",
                    },
                )
            assert response.status_code == 200
            assert response.json()["status"] == "training"
        finally:
            from app.models.training_job import TrainingJob

            await TrainingJob.find(TrainingJob.dataset_id == str(dataset.id)).delete()
            await dataset.delete()

    @pytest.mark.asyncio
    async def test_train_model_endpoint(self, async_authorized_client):
        """Test POST /api/v1/ml/train"""
        # Mock dataset lookup
        mock_user_data = MagicMock(
            id="dataset_123",
            user_id="test_user",
            file_key="uploads/test_user/test_data.csv",
        )

        with patch(
            "app.models.user_data.UserData.find_one", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_user_data

            # Mock the background task function to prevent it from executing
            with patch(
                "app.api.routes.model_training.train_model_task", new_callable=AsyncMock
            ):
                request_data = {
                    "dataset_id": "dataset_123",
                    "target_column": "target",
                    "name": "My Model",
                    "description": "Test model",
                }

                response = await async_authorized_client.post(
                    "/api/v1/ml/train",
                    json=request_data,
                    headers={"Authorization": "Bearer test_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert "model_id" in data
                assert data["status"] == "training"
                assert "message" in data

    @pytest.mark.asyncio
    async def test_list_models_endpoint(self, async_authorized_client):
        """Test GET /api/v1/ml/"""
        # Create a proper mock model with spec
        mock_model = MagicMock(spec=MLModel)
        mock_model.model_id = "model_123"
        mock_model.name = "Test Model"
        mock_model.description = "Test description"
        mock_model.problem_type = "classification"
        mock_model.algorithm = "Random Forest"
        mock_model.target_column = "target"
        mock_model.cv_score = 0.85
        mock_model.test_score = 0.83
        mock_model.created_at = datetime.now(UTC)
        mock_model.last_used_at = None
        mock_model.is_active = True

        # Mock model listing
        with patch(
            "app.services.model_storage.ModelStorageService.list_models",
            new_callable=AsyncMock,
        ) as mock_list:
            mock_list.return_value = [mock_model]

            response = await async_authorized_client.get(
                "/api/v1/ml/", headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["model_id"] == "model_123"
            assert data[0]["name"] == "Test Model"

    @pytest.mark.asyncio
    async def test_get_model_endpoint(self, async_authorized_client, sample_ml_model):
        """Test GET /api/v1/ml/{model_id}"""
        with patch(
            "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = sample_ml_model

            response = await async_authorized_client.get("/api/v1/ml/model_123")

            assert response.status_code == 200
            data = response.json()
            assert data["model_id"] == "model_123"
            assert data["name"] == "Test Model"
            assert data["algorithm"] == "Random Forest"

    @pytest.mark.asyncio
    async def test_predict_endpoint(self, async_authorized_client):
        """Test POST /api/v1/ml/{model_id}/predict"""
        # Mock model loading
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0, 1, 0])
        mock_model.predict_proba.return_value = np.array(
            [[0.8, 0.2], [0.3, 0.7], [0.9, 0.1]]
        )

        with patch(
            "app.services.model_storage.ModelStorageService.load_model",
            new_callable=AsyncMock,
        ) as mock_load:
            mock_load.return_value = (mock_model, None)

            # Mock model metadata
            with patch(
                "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
            ) as mock_find:
                mock_find.return_value = MagicMock(
                    feature_names=["feature1", "feature2", "feature3"],
                    problem_type="binary_classification",
                    algorithm="Random Forest",
                    target_column="target",
                    is_calibrated=False,
                    calibration_method=None,
                    residual_std=None,
                    feature_importance=None,
                )

                request_data = {
                    "data": [
                        {"feature1": 1.0, "feature2": 2.0, "feature3": "A"},
                        {"feature1": 1.5, "feature2": 2.5, "feature3": "B"},
                        {"feature1": 2.0, "feature2": 3.0, "feature3": "C"},
                    ],
                    "include_probabilities": True,
                }

                response = await async_authorized_client.post(
                    "/api/v1/ml/model_123/predict", json=request_data
                )
                data = response.json()

                assert response.status_code == 200
                assert data["predictions"] == [0, 1, 0]
                assert len(data["probabilities"]) == 3
                assert data["feature_names"] == ["feature1", "feature2", "feature3"]

    @pytest.mark.asyncio
    async def test_delete_model_endpoint(self, async_authorized_client):
        """Test DELETE /api/v1/ml/{model_id}"""
        with patch(
            "app.services.model_storage.ModelStorageService.delete_model",
            new_callable=AsyncMock,
        ) as mock_delete:
            mock_delete.return_value = True

            response = await async_authorized_client.delete("/api/v1/ml/model_123")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "deleted successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_deactivate_model_endpoint(
        self, async_authorized_client, sample_ml_model
    ):
        """Test PUT /api/v1/ml/{model_id}/deactivate"""
        sample_ml_model.save = AsyncMock()

        with patch(
            "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = sample_ml_model

            response = await async_authorized_client.put(
                "/api/v1/ml/model_123/deactivate"
            )
            data = response.json()

            assert response.status_code == 200
            assert "message" in data
            assert "deactivated" in data["message"]
            assert sample_ml_model.is_active is False

    @pytest.mark.asyncio
    async def test_train_model_not_found(self, async_authorized_client):
        """Test training with non-existent dataset"""
        with patch(
            "app.models.user_data.UserData.find_one", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = None

            request_data = {"dataset_id": "non_existent", "target_column": "target"}

            response = await async_authorized_client.post(
                "/api/v1/ml/train", json=request_data
            )

            assert response.status_code == 404
            assert "Dataset not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_predict_model_not_found(self, async_authorized_client):
        """Test prediction with non-existent model"""
        with patch(
            "app.services.model_storage.ModelStorageService.load_model"
        ) as mock_load:
            mock_load.side_effect = ValueError("Model not found")

            request_data = {"data": [{"feature1": 1.0}]}

            response = await async_authorized_client.post(
                "/api/v1/ml/non_existent/predict", json=request_data
            )

            assert response.status_code == 404
            assert "Model not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_predict_missing_feature_returns_422(self, async_authorized_client):
        """A record missing a required raw input feature is rejected (issue #82)."""
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0])

        with patch(
            "app.services.model_storage.ModelStorageService.load_model",
            new_callable=AsyncMock,
        ) as mock_load:
            mock_load.return_value = (mock_model, None)
            with patch(
                "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
            ) as mock_find:
                mock_find.return_value = MagicMock(
                    feature_names=["feature1", "feature2", "feature3"]
                )

                request_data = {
                    # feature3 is missing
                    "data": [{"feature1": 1.0, "feature2": 2.0}],
                }

                response = await async_authorized_client.post(
                    "/api/v1/ml/model_123/predict", json=request_data
                )

                assert response.status_code == 422
                assert "feature3" in response.json()["detail"]
                mock_model.predict.assert_not_called()

    @pytest.mark.asyncio
    async def test_predict_invalid_value_returns_422(self, async_authorized_client):
        """An unknown categorical value (sklearn ValueError) becomes a clean
        422, not a 500 traceback leak (issue #82 hardening)."""
        mock_model = MagicMock()
        mock_model.predict.side_effect = ValueError(
            "Found unknown categories ['weird'] in column 0"
        )

        with patch(
            "app.services.model_storage.ModelStorageService.load_model",
            new_callable=AsyncMock,
        ) as mock_load:
            mock_load.return_value = (mock_model, None)
            with patch(
                "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
            ) as mock_find:
                mock_find.return_value = MagicMock(feature_names=["feature1"])

                response = await async_authorized_client.post(
                    "/api/v1/ml/model_123/predict",
                    json={"data": [{"feature1": "weird"}]},
                )

                assert response.status_code == 422
                assert "Invalid feature value" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_predict_returns_confidence_and_class_labels(
        self, async_authorized_client
    ):
        """Classification predictions expose per-record confidence + labels (#82)."""
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([1, 0])
        mock_model.predict_proba.return_value = np.array([[0.1, 0.9], [0.7, 0.3]])
        mock_model.classes_ = np.array([0, 1])

        with patch(
            "app.services.model_storage.ModelStorageService.load_model",
            new_callable=AsyncMock,
        ) as mock_load:
            mock_load.return_value = (mock_model, None)
            with patch(
                "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
            ) as mock_find:
                mock_find.return_value = MagicMock(
                    feature_names=["feature1"],
                    problem_type="binary_classification",
                    algorithm="Random Forest",
                    target_column="target",
                    is_calibrated=False,
                    calibration_method=None,
                    residual_std=None,
                    feature_importance=None,
                )

                request_data = {
                    "data": [{"feature1": 1.0}, {"feature1": 2.0}],
                    "include_probabilities": True,
                }

                response = await async_authorized_client.post(
                    "/api/v1/ml/model_123/predict", json=request_data
                )

                assert response.status_code == 200
                data = response.json()
                assert data["predictions"] == [1, 0]
                assert data["confidence"] == [0.9, 0.7]
                assert data["class_labels"] == ["0", "1"]
                # Low-confidence flags present; threshold (0.7) is strict, so
                # neither 0.9 nor exactly-0.7 is flagged.
                assert data["low_confidence"] == [False, False]
                assert data["is_calibrated"] is False
                assert data["confidence_threshold"] == 0.7

    @pytest.mark.asyncio
    async def test_predict_with_explanations(self, async_authorized_client):
        """include_explanations returns model-native feature contributions (#83)."""
        from sklearn.datasets import make_classification
        from sklearn.linear_model import LogisticRegression

        X, y = make_classification(
            n_samples=80,
            n_features=2,
            n_informative=2,
            n_redundant=0,
            random_state=0,
        )
        real_model = LogisticRegression().fit(X, y)

        with patch(
            "app.services.model_storage.ModelStorageService.load_model",
            new_callable=AsyncMock,
        ) as mock_load:
            mock_load.return_value = (real_model, None)
            with patch(
                "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
            ) as mock_find:
                mock_find.return_value = MagicMock(
                    feature_names=["feature1", "feature2"],
                    problem_type="binary_classification",
                    algorithm="Logistic Regression",
                    target_column="target",
                    is_calibrated=False,
                    calibration_method=None,
                    residual_std=None,
                    feature_importance=None,
                )

                request_data = {
                    "data": [{"feature1": float(X[0][0]), "feature2": float(X[0][1])}],
                    "include_explanations": True,
                }

                response = await async_authorized_client.post(
                    "/api/v1/ml/model_123/predict", json=request_data
                )

                assert response.status_code == 200
                data = response.json()
                explanation = data["explanations"][0]
                assert explanation["method"] == "linear_coefficients"
                assert explanation["explanation_text"]
                assert len(explanation["top_features"]) >= 1

    @pytest.mark.asyncio
    async def test_get_model_features_endpoint(self, async_authorized_client):
        """GET /features returns the raw input schema for form generation (#82)."""
        mock_model = MagicMock()
        mock_model.classes_ = np.array(["no", "yes"])

        mock_fe = MagicMock()
        mock_fe.numeric_features = ["age", "income"]
        mock_fe.categorical_features = ["gender"]
        mock_fe.transformers = {}
        mock_fe.config.encoding_method = "onehot"

        with patch(
            "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = MagicMock(
                feature_names=["age", "income", "gender_male"],
                problem_type="binary_classification",
                target_column="churned",
            )
            with patch(
                "app.services.model_storage.ModelStorageService.load_model",
                new_callable=AsyncMock,
            ) as mock_load:
                mock_load.return_value = (mock_model, mock_fe)

                response = await async_authorized_client.get(
                    "/api/v1/ml/model_123/features"
                )

                assert response.status_code == 200
                data = response.json()
                names = [f["name"] for f in data["features"]]
                assert names == ["age", "income", "gender"]
                types = {f["name"]: f["type"] for f in data["features"]}
                assert types["age"] == "number"
                assert types["gender"] == "categorical"
                assert data["class_labels"] == ["no", "yes"]
                assert data["problem_type"] == "binary_classification"
                assert data["target_column"] == "churned"

    @pytest.mark.asyncio
    async def test_get_model_features_not_found(self, async_authorized_client):
        """Unknown model id yields 404 from the features endpoint (#82)."""
        with patch(
            "app.models.ml_model.MLModel.find_one", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = None

            response = await async_authorized_client.get("/api/v1/ml/nope/features")

            assert response.status_code == 404


class TestModelTrainingBackgroundTask:
    """Test the background training task"""

    @pytest.mark.asyncio
    async def test_train_model_task_success(self, sample_dataset, sample_dataframe):
        """Test successful model training task"""
        from app.api.routes.model_training import TrainModelRequest, train_model_task

        # Mock S3 file loading
        with patch(
            "app.services.s3_service.S3Service.download_file_bytes",
            new_callable=AsyncMock,
        ) as mock_s3:
            # Return CSV data as bytes (not BytesIO - the code expects raw bytes)
            csv_buffer = io.BytesIO()
            sample_dataframe.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            mock_s3.return_value = csv_buffer.getvalue()  # Return bytes, not BytesIO

            # Mock AutoML engine
            mock_result = AutoMLResult(
                best_model=ModelCandidate(
                    name="Random Forest",
                    estimator=MagicMock(),
                    hyperparameters={},
                    cv_score=0.85,
                    test_score=0.83,
                    training_time=10.5,
                ),
                all_models=[],
                problem_type=ProblemType.BINARY_CLASSIFICATION,
                feature_names=["feature1", "feature2", "feature3"],
                feature_importance={"feature1": 0.5, "feature2": 0.3, "feature3": 0.2},
                training_time=15.0,
                metadata={},
            )

            with patch(
                "app.services.model_training.AutoMLEngine.run", new_callable=AsyncMock
            ) as mock_run:
                mock_run.return_value = mock_result

                # Mock model storage
                with patch(
                    "app.services.model_storage.ModelStorageService.save_model",
                    new_callable=AsyncMock,
                ) as mock_save:
                    mock_save.return_value = MagicMock(model_id="model_123")

                    request = TrainModelRequest(
                        dataset_id="dataset_123",
                        target_column="target",
                        name="Test Model",
                    )

                    # Run the task
                    await train_model_task(
                        sample_dataset, request, "test_user", "model_123"
                    )

                    # Verify calls
                    mock_s3.assert_called_once()
                    mock_run.assert_called_once()
                    mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_train_task_wires_quick_mode_to_engine(
        self, sample_dataset, sample_dataframe
    ):
        """training_mode=quick resolves to the engine's quick preset (#101)."""
        from app.api.routes.model_training import TrainModelRequest, train_model_task

        with patch(
            "app.services.s3_service.S3Service.download_file_bytes",
            new_callable=AsyncMock,
        ) as mock_s3:
            csv_buffer = io.BytesIO()
            sample_dataframe.to_csv(csv_buffer, index=False)
            mock_s3.return_value = csv_buffer.getvalue()

            mock_result = AutoMLResult(
                best_model=ModelCandidate(
                    name="Logistic Regression",
                    estimator=MagicMock(),
                    hyperparameters={},
                    cv_score=0.9,
                    test_score=0.88,
                    training_time=1.0,
                ),
                all_models=[],
                problem_type=ProblemType.BINARY_CLASSIFICATION,
                feature_names=["feature1"],
                feature_importance=None,
                training_time=2.0,
                metadata={},
            )

            # Patch the engine class in the route so we can inspect construction.
            with patch(
                "app.api.routes.model_training.AutoMLEngine"
            ) as mock_engine_cls:
                engine = mock_engine_cls.return_value
                engine.run = AsyncMock(return_value=mock_result)
                engine.feature_engineer = MagicMock()

                with patch(
                    "app.services.model_storage.ModelStorageService.save_model",
                    new_callable=AsyncMock,
                ) as mock_save:
                    mock_save.return_value = MagicMock(model_id="model_q")

                    request = TrainModelRequest(
                        dataset_id="dataset_123",
                        target_column="target",
                        training_config={"training_mode": "quick"},
                    )
                    await train_model_task(
                        sample_dataset, request, "test_user", "model_q"
                    )

                # Engine built with the quick preset.
                kwargs = mock_engine_cls.call_args.kwargs
                assert kwargs["max_models"] == 3
                assert kwargs["time_limit"] == 300
                assert kwargs["enable_tuning"] is False
                assert kwargs["early_stop_score"] == 0.95


class TestTrainingStatusEndpoint:
    """Test GET /api/v1/ml/{model_id}/status and job lifecycle tracking."""

    @pytest.mark.asyncio
    async def test_train_creates_pending_job(self, async_authorized_client):
        """POST /train persists a pending TrainingJob and it is queryable."""
        from app.models.batch_job import JobStatus
        from app.models.training_job import TrainingJob

        mock_user_data = MagicMock(
            id="dataset_123",
            user_id="test_user_123",
            file_key="uploads/test_user/test_data.csv",
        )

        with patch(
            "app.models.user_data.UserData.find_one", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_user_data
            with patch(
                "app.api.routes.model_training.train_model_task", new_callable=AsyncMock
            ):
                response = await async_authorized_client.post(
                    "/api/v1/ml/train",
                    json={"dataset_id": "dataset_123", "target_column": "target"},
                )

        assert response.status_code == 200
        model_id = response.json()["model_id"]

        # A pending TrainingJob now exists for this model_id.
        job = await TrainingJob.find_one(TrainingJob.model_id == model_id)
        assert job is not None
        assert job.status == JobStatus.PENDING

        # And the status endpoint reports it.
        status_resp = await async_authorized_client.get(f"/api/v1/ml/{model_id}/status")
        assert status_resp.status_code == 200
        body = status_resp.json()
        assert body["status"] == "pending"
        assert body["progress"] == 0.0

        await job.delete()

    @pytest.mark.asyncio
    async def test_status_returns_completed_results(self, async_authorized_client):
        """A completed job returns comparison, recommendations, and explanation."""
        from app.models.training_job import ModelComparisonEntry, TrainingJob

        job = TrainingJob(
            model_id="model_status_done",
            user_id="test_user_123",
            dataset_id="dataset_123",
            target_column="target",
        )
        job.mark_started(total_algorithms=2)
        job.mark_completed(
            best_model_id="model_status_done",
            best_algorithm="XGBoost",
            best_model_explanation="XGBoost won.",
            model_comparison=[
                ModelComparisonEntry(
                    algorithm="XGBoost", cv_score=0.91, test_score=0.9
                ),
                ModelComparisonEntry(algorithm="Random Forest", cv_score=0.88),
            ],
            algorithm_recommendations=[{"algorithm_name": "XGBoost", "priority": 9}],
            metrics={"cv_score": 0.91, "test_score": 0.9},
        )
        await job.insert()

        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/model_status_done/status"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "completed"
            assert body["progress"] == 1.0
            assert body["best_algorithm"] == "XGBoost"
            assert body["explanation"] == "XGBoost won."
            assert len(body["model_comparison"]) == 2
            assert body["model_comparison"][0]["algorithm"] == "XGBoost"
            assert body["algorithm_recommendations"][0]["algorithm_name"] == "XGBoost"
            assert body["metrics"]["cv_score"] == 0.91
        finally:
            await job.delete()

    @pytest.mark.asyncio
    async def test_status_returns_failure(self, async_authorized_client):
        """A failed job surfaces the error message."""
        from app.models.training_job import TrainingJob

        job = TrainingJob(
            model_id="model_status_failed",
            user_id="test_user_123",
            dataset_id="dataset_123",
            target_column="target",
        )
        job.mark_started(total_algorithms=2)
        job.mark_failed("Unsupported file type: txt")
        await job.insert()

        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/model_status_failed/status"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "failed"
            assert body["error"] == "Unsupported file type: txt"
        finally:
            await job.delete()

    @pytest.mark.asyncio
    async def test_status_not_found(self, async_authorized_client):
        """Unknown model_id returns 404."""
        resp = await async_authorized_client.get("/api/v1/ml/does_not_exist/status")
        assert resp.status_code == 404

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_train_model_task_marks_failure(self, sample_dataset, setup_database):
        """A task failure transitions the TrainingJob to FAILED with an error."""
        from app.api.routes.model_training import TrainModelRequest, train_model_task
        from app.models.batch_job import JobStatus
        from app.models.training_job import TrainingJob

        job = TrainingJob(
            model_id="model_task_fail",
            user_id="test_user",
            dataset_id="dataset_123",
            target_column="target",
        )
        await job.insert()

        # Force an unsupported file type so the task raises internally.
        sample_dataset.file_type = "txt"

        try:
            with patch(
                "app.services.s3_service.S3Service.download_file_bytes",
                new_callable=AsyncMock,
            ) as mock_s3:
                mock_s3.return_value = b"irrelevant"
                request = TrainModelRequest(
                    dataset_id="dataset_123", target_column="target"
                )
                # Should NOT raise — failure is recorded on the job.
                await train_model_task(
                    sample_dataset, request, "test_user", "model_task_fail"
                )

            refreshed = await TrainingJob.find_one(
                TrainingJob.model_id == "model_task_fail"
            )
            assert refreshed.status == JobStatus.FAILED
            assert refreshed.error is not None
            # The failure is also surfaced as an error-level log entry.
            assert any(entry.level == "error" for entry in refreshed.logs)
        finally:
            await job.delete()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_train_model_task_cancellation(
        self, sample_dataset, sample_dataframe, setup_database
    ):
        """TrainingCancelledError transitions the job to CANCELLED, not FAILED."""
        from app.api.routes.model_training import TrainModelRequest, train_model_task
        from app.models.batch_job import JobStatus
        from app.models.training_job import TrainingJob
        from app.services.model_training.automl_engine import TrainingCancelledError

        job = TrainingJob(
            model_id="model_task_cancel",
            user_id="test_user",
            dataset_id="dataset_123",
            target_column="target",
        )
        await job.insert()

        csv_buffer = io.BytesIO()
        sample_dataframe.to_csv(csv_buffer, index=False)

        try:
            with patch(
                "app.services.s3_service.S3Service.download_file_bytes",
                new_callable=AsyncMock,
            ) as mock_s3:
                mock_s3.return_value = csv_buffer.getvalue()
                with patch(
                    "app.services.model_training.AutoMLEngine.run",
                    new_callable=AsyncMock,
                ) as mock_run:
                    mock_run.side_effect = TrainingCancelledError("cancelled")
                    request = TrainModelRequest(
                        dataset_id="dataset_123", target_column="target"
                    )
                    # Should NOT raise — cancellation is recorded on the job.
                    await train_model_task(
                        sample_dataset, request, "test_user", "model_task_cancel"
                    )

            refreshed = await TrainingJob.find_one(
                TrainingJob.model_id == "model_task_cancel"
            )
            assert refreshed.status == JobStatus.CANCELLED
            assert refreshed.error is None
            assert refreshed.completed_at is not None
            assert any(
                "Training cancelled by user" in entry.message
                for entry in refreshed.logs
            )
        finally:
            await job.delete()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_cancel_log_survives_event_writes(
        self, sample_dataset, sample_dataframe, setup_database
    ):
        """A log written by the cancel endpoint mid-training is never clobbered.

        Reproduces the race: the task holds a stale in-memory job; the cancel
        endpoint appends "Cancellation requested" and saves; the engine then
        emits another event (which the task persists) and the run is
        cancelled (a terminal full-document save). Both the endpoint's log
        and the flag must survive — the task $push-es log appends and
        re-reads the job before terminal saves.
        """
        from app.api.routes.model_training import TrainModelRequest, train_model_task
        from app.models.batch_job import JobStatus
        from app.models.training_job import TrainingJob
        from app.services.model_training.automl_engine import (
            TrainingCancelledError,
            TrainingEvent,
        )

        job = TrainingJob(
            model_id="model_task_race",
            user_id="test_user",
            dataset_id="dataset_123",
            target_column="target",
        )
        await job.insert()

        csv_buffer = io.BytesIO()
        sample_dataframe.to_csv(csv_buffer, index=False)

        async def run_side_effect(*args, **kwargs):
            # Cancel endpoint writes through its own document instance while
            # the background task still holds its stale copy.
            endpoint_copy = await TrainingJob.find_one(
                TrainingJob.model_id == "model_task_race"
            )
            endpoint_copy.cancellation_requested = True
            endpoint_copy.add_log("info", "Cancellation requested")
            await endpoint_copy.save()

            # The engine then reports one more event via the stale copy...
            await kwargs["event_callback"](
                TrainingEvent(
                    level="info", message="Candidate finished", stage="training"
                )
            )
            # ...and the cooperative check finally sees the flag.
            raise TrainingCancelledError("cancelled")

        try:
            with patch(
                "app.services.s3_service.S3Service.download_file_bytes",
                new_callable=AsyncMock,
            ) as mock_s3:
                mock_s3.return_value = csv_buffer.getvalue()
                with patch(
                    "app.services.model_training.AutoMLEngine.run",
                    new_callable=AsyncMock,
                ) as mock_run:
                    mock_run.side_effect = run_side_effect
                    request = TrainModelRequest(
                        dataset_id="dataset_123", target_column="target"
                    )
                    await train_model_task(
                        sample_dataset, request, "test_user", "model_task_race"
                    )

            refreshed = await TrainingJob.find_one(
                TrainingJob.model_id == "model_task_race"
            )
            assert refreshed.status == JobStatus.CANCELLED
            assert refreshed.cancellation_requested is True
            messages = [entry.message for entry in refreshed.logs]
            assert "Cancellation requested" in messages
            assert "Candidate finished" in messages
            assert "Training cancelled by user" in messages
        finally:
            await job.delete()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_train_model_task_emits_lifecycle_logs(
        self, sample_dataset, sample_dataframe, setup_database
    ):
        """A successful task records task-start, download, and completion logs."""
        from app.api.routes.model_training import TrainModelRequest, train_model_task
        from app.models.batch_job import JobStatus
        from app.models.training_job import TrainingJob

        job = TrainingJob(
            model_id="model_task_logs",
            user_id="test_user",
            dataset_id="dataset_123",
            target_column="target",
        )
        await job.insert()

        csv_buffer = io.BytesIO()
        sample_dataframe.to_csv(csv_buffer, index=False)

        mock_result = AutoMLResult(
            best_model=ModelCandidate(
                name="Random Forest",
                estimator=MagicMock(),
                hyperparameters={},
                cv_score=0.85,
                test_score=0.83,
                training_time=10.5,
            ),
            all_models=[],
            problem_type=ProblemType.BINARY_CLASSIFICATION,
            feature_names=["feature1", "feature2", "feature3"],
            feature_importance=None,
            training_time=15.0,
            metadata={},
        )

        try:
            with patch(
                "app.services.s3_service.S3Service.download_file_bytes",
                new_callable=AsyncMock,
            ) as mock_s3:
                mock_s3.return_value = csv_buffer.getvalue()
                with patch(
                    "app.services.model_training.AutoMLEngine.run",
                    new_callable=AsyncMock,
                ) as mock_run:
                    mock_run.return_value = mock_result
                    with patch(
                        "app.services.model_storage.ModelStorageService.save_model",
                        new_callable=AsyncMock,
                    ) as mock_save:
                        mock_save.return_value = MagicMock(model_id="model_task_logs")
                        request = TrainModelRequest(
                            dataset_id="dataset_123", target_column="target"
                        )
                        await train_model_task(
                            sample_dataset, request, "test_user", "model_task_logs"
                        )

            refreshed = await TrainingJob.find_one(
                TrainingJob.model_id == "model_task_logs"
            )
            assert refreshed.status == JobStatus.COMPLETED
            messages = [entry.message for entry in refreshed.logs]
            assert any("Training task started" in m for m in messages)
            assert any("Dataset downloaded" in m for m in messages)
            # Completion log names the best algorithm.
            assert any(
                "Training completed" in m and "Random Forest" in m for m in messages
            )
        finally:
            await job.delete()


async def _insert_job(
    model_id: str,
    *,
    user_id: str = "test_user_123",
    status: str = "pending",
    **kwargs,
):
    """Insert a TrainingJob in the given lifecycle state and return it."""
    from app.models.batch_job import JobStatus
    from app.models.training_job import TrainingJob

    job = TrainingJob(
        model_id=model_id,
        user_id=user_id,
        dataset_id=kwargs.pop("dataset_id", "dataset_123"),
        target_column=kwargs.pop("target_column", "target"),
    )
    if status in ("running", "completed", "failed", "cancelled"):
        job.mark_started(total_algorithms=kwargs.pop("total_algorithms", 4))
    if status == "completed":
        job.mark_completed(**kwargs)
    elif status == "failed":
        job.mark_failed(kwargs.pop("error", "boom"))
    elif status == "cancelled":
        job.mark_cancelled()
    assert job.status == JobStatus(status)
    await job.insert()
    return job


class TestTrainingJobListEndpoint:
    """Tests for GET /api/v1/ml/jobs.

    These assert on absolute job counts, so each one needs a clean
    ``training_jobs`` collection. They don't use ``setup_database`` (they only
    need the app's lifespan DB from ``async_authorized_client``), and a training
    test's fire-and-forget background task can leak a job past its own cleanup
    window. The autouse fixture below clears the collection at the start of each
    test so the suite is order-independent (issue #198).
    """

    @pytest_asyncio.fixture(autouse=True)
    async def _isolate_training_jobs(self, async_authorized_client):
        from app.models.training_job import TrainingJob

        # Clean slate before the test (drops anything leaked from earlier tests)
        # and after, so a job created here never bleeds into the next test.
        await TrainingJob.find().delete()
        yield
        await TrainingJob.find().delete()

    """Test GET /api/v1/ml/jobs"""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, async_authorized_client):
        resp = await async_authorized_client.get("/api/v1/ml/jobs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["jobs"] == []
        assert body["total_count"] == 0
        assert body["limit"] == 20
        assert body["skip"] == 0

    @pytest.mark.asyncio
    async def test_list_jobs_populated(self, async_authorized_client):
        from app.models.training_job import ModelComparisonEntry

        jobs = [
            await _insert_job("model_jobs_a", status="running"),
            await _insert_job(
                "model_jobs_b",
                status="completed",
                best_algorithm="XGBoost",
                model_comparison=[
                    ModelComparisonEntry(
                        algorithm="XGBoost", cv_score=0.91, test_score=0.9
                    ),
                    ModelComparisonEntry(algorithm="Random Forest", cv_score=0.88),
                ],
            ),
        ]
        try:
            resp = await async_authorized_client.get("/api/v1/ml/jobs")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_count"] == 2
            assert len(body["jobs"]) == 2
            by_id = {j["model_id"]: j for j in body["jobs"]}
            completed = by_id["model_jobs_b"]
            assert completed["status"] == "completed"
            assert completed["best_algorithm"] == "XGBoost"
            assert completed["best_score"] == 0.9  # best test_score
            assert completed["dataset_id"] == "dataset_123"
            assert completed["target_column"] == "target"
            assert completed["progress_percentage"] == 100.0
            assert completed["elapsed_seconds"] is not None
            running = by_id["model_jobs_a"]
            assert running["status"] == "running"
            assert running["best_score"] is None
            assert running["completed_at"] is None
            # Sorted newest first.
            assert [j["model_id"] for j in body["jobs"]] == [
                "model_jobs_b",
                "model_jobs_a",
            ]
        finally:
            for job in jobs:
                await job.delete()

    @pytest.mark.asyncio
    async def test_list_jobs_status_filter(self, async_authorized_client):
        jobs = [
            await _insert_job("model_filter_a", status="running"),
            await _insert_job("model_filter_b", status="failed"),
        ]
        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/jobs", params={"status": "failed"}
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_count"] == 1
            assert body["jobs"][0]["model_id"] == "model_filter_b"
        finally:
            for job in jobs:
                await job.delete()

    @pytest.mark.asyncio
    async def test_list_jobs_multi_status_filter(self, async_authorized_client):
        """Comma-separated statuses paginate over exactly those statuses.

        The history "All" view relies on this so terminal runs are never
        hidden behind pages of in-flight jobs.
        """
        jobs = [
            await _insert_job("model_multi_a", status="running"),
            await _insert_job("model_multi_b", status="completed"),
            await _insert_job("model_multi_c", status="failed"),
            await _insert_job("model_multi_d", status="cancelled"),
        ]
        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/jobs",
                params={"status": "completed,failed,cancelled"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_count"] == 3
            returned = {job["model_id"] for job in body["jobs"]}
            assert returned == {"model_multi_b", "model_multi_c", "model_multi_d"}
        finally:
            for job in jobs:
                await job.delete()

    @pytest.mark.asyncio
    async def test_list_jobs_invalid_status_rejected(self, async_authorized_client):
        resp = await async_authorized_client.get(
            "/api/v1/ml/jobs", params={"status": "not_a_status"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_jobs_invalid_status_in_list_rejected(
        self, async_authorized_client
    ):
        resp = await async_authorized_client.get(
            "/api/v1/ml/jobs", params={"status": "completed,bogus"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_jobs_pagination(self, async_authorized_client):
        jobs = [
            await _insert_job(f"model_page_{i}", status="pending") for i in range(3)
        ]
        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/jobs", params={"limit": 2, "skip": 2}
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_count"] == 3
            assert len(body["jobs"]) == 1
            assert body["limit"] == 2
            assert body["skip"] == 2
        finally:
            for job in jobs:
                await job.delete()

    @pytest.mark.asyncio
    async def test_list_jobs_limit_capped(self, async_authorized_client):
        resp = await async_authorized_client.get(
            "/api/v1/ml/jobs", params={"limit": 101}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_jobs_excludes_other_users(self, async_authorized_client):
        jobs = [
            await _insert_job("model_mine", status="pending"),
            await _insert_job("model_theirs", status="pending", user_id="someone_else"),
        ]
        try:
            resp = await async_authorized_client.get("/api/v1/ml/jobs")
            assert resp.status_code == 200
            body = resp.json()
            ids = [j["model_id"] for j in body["jobs"]]
            assert "model_mine" in ids
            assert "model_theirs" not in ids
        finally:
            for job in jobs:
                await job.delete()


class TestTrainingLogsEndpoint:
    """Test GET /api/v1/ml/{model_id}/logs"""

    @pytest.mark.asyncio
    async def test_logs_not_found(self, async_authorized_client):
        resp = await async_authorized_client.get("/api/v1/ml/no_such_model/logs")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_logs_returns_entries(self, async_authorized_client):
        job = await _insert_job("model_logs_basic", status="running")
        job.add_log("info", "Training task started")
        job.add_log("info", "XGBoost trained: cv_score=0.91", stage="training")
        job.add_log("warning", "SVM failed to train: boom", stage="training")
        await job.save()
        try:
            resp = await async_authorized_client.get("/api/v1/ml/model_logs_basic/logs")
            assert resp.status_code == 200
            body = resp.json()
            assert body["model_id"] == "model_logs_basic"
            assert body["total_count"] == 3
            assert body["has_more"] is False
            assert len(body["logs"]) == 3
            first = body["logs"][0]
            assert first["level"] == "info"
            assert first["message"] == "Training task started"
            assert first["stage"] is None
            assert "timestamp" in first
        finally:
            await job.delete()

    @pytest.mark.asyncio
    async def test_logs_level_filter(self, async_authorized_client):
        job = await _insert_job("model_logs_level", status="running")
        job.add_log("info", "fine")
        job.add_log("error", "bad")
        await job.save()
        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/model_logs_level/logs", params={"level": "error"}
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_count"] == 1
            assert body["logs"][0]["message"] == "bad"
        finally:
            await job.delete()

    @pytest.mark.asyncio
    async def test_logs_pagination(self, async_authorized_client):
        job = await _insert_job("model_logs_page", status="running")
        for i in range(5):
            job.add_log("info", f"line {i}")
        await job.save()
        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/model_logs_page/logs",
                params={"limit": 2, "skip": 2},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_count"] == 5
            assert [entry["message"] for entry in body["logs"]] == ["line 2", "line 3"]
            assert body["has_more"] is True
        finally:
            await job.delete()

    @pytest.mark.asyncio
    async def test_logs_other_users_job_hidden(self, async_authorized_client):
        job = await _insert_job(
            "model_logs_other", status="running", user_id="someone_else"
        )
        try:
            resp = await async_authorized_client.get("/api/v1/ml/model_logs_other/logs")
            assert resp.status_code == 404
        finally:
            await job.delete()


class TestCancelTrainingEndpoint:
    """Test POST /api/v1/ml/{model_id}/cancel"""

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, async_authorized_client):
        resp = await async_authorized_client.post("/api/v1/ml/no_such_model/cancel")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_running_job(self, async_authorized_client):
        from app.models.training_job import TrainingJob

        job = await _insert_job("model_cancel_run", status="running")
        try:
            resp = await async_authorized_client.post(
                "/api/v1/ml/model_cancel_run/cancel"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["model_id"] == "model_cancel_run"
            assert body["cancellation_requested"] is True
            assert body["status"] == "running"
            assert "message" in body

            refreshed = await TrainingJob.find_one(
                TrainingJob.model_id == "model_cancel_run"
            )
            assert refreshed.cancellation_requested is True
            assert any(
                "Cancellation requested" in entry.message for entry in refreshed.logs
            )
        finally:
            await job.delete()

    @pytest.mark.asyncio
    async def test_cancel_terminal_job_conflict(self, async_authorized_client):
        job = await _insert_job("model_cancel_done", status="completed")
        try:
            resp = await async_authorized_client.post(
                "/api/v1/ml/model_cancel_done/cancel"
            )
            assert resp.status_code == 409
        finally:
            await job.delete()

    @pytest.mark.asyncio
    async def test_cancel_other_users_job_hidden(self, async_authorized_client):
        job = await _insert_job(
            "model_cancel_other", status="running", user_id="someone_else"
        )
        try:
            resp = await async_authorized_client.post(
                "/api/v1/ml/model_cancel_other/cancel"
            )
            assert resp.status_code == 404
        finally:
            await job.delete()


class TestExtendedStatusFields:
    """The status endpoint exposes stage, timing, and cancellation fields."""

    @pytest.mark.asyncio
    async def test_status_includes_monitoring_fields(self, async_authorized_client):
        from datetime import timedelta

        from app.models.training_job import _utcnow

        job = await _insert_job("model_status_ext", status="running")
        job.update_progress(completed_algorithms=2, current_algorithm="XGBoost")
        job.progress.current_stage = "training"
        job.started_at = _utcnow() - timedelta(seconds=20)
        await job.save()
        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/model_status_ext/status"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["current_stage"] == "training"
            assert body["cancellation_requested"] is False
            assert body["elapsed_seconds"] >= 19.0
            # Running at 50% with ~20s elapsed -> ~20s remaining.
            assert body["estimated_remaining_seconds"] == pytest.approx(20.0, abs=5.0)
        finally:
            await job.delete()

    @pytest.mark.asyncio
    async def test_status_timing_none_when_pending(self, async_authorized_client):
        job = await _insert_job("model_status_pending_ext", status="pending")
        try:
            resp = await async_authorized_client.get(
                "/api/v1/ml/model_status_pending_ext/status"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["current_stage"] is None
            assert body["elapsed_seconds"] is None
            assert body["estimated_remaining_seconds"] is None
        finally:
            await job.delete()


class TestModeRecommendationEndpoint:
    """GET /api/v1/ml/datasets/{dataset_id}/mode-recommendation (issue #101)."""

    @pytest.mark.asyncio
    async def test_recommends_comprehensive_for_small_dataset(
        self, async_authorized_client
    ):
        from app.models.user_data import UserData

        dataset = UserData(
            user_id="test_user_123",
            filename="small.csv",
            original_filename="small.csv",
            s3_url="s3://test-bucket/small.csv",
            num_rows=500,
            num_columns=6,
            data_schema=[],
        )
        await dataset.insert()
        try:
            resp = await async_authorized_client.get(
                f"/api/v1/ml/datasets/{dataset.id}/mode-recommendation"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["recommended_mode"] == "comprehensive"
            assert body["n_rows"] == 500
            # Feature count excludes the target column (num_columns - 1).
            assert body["n_features"] == 5
            assert body["reason"]
        finally:
            await dataset.delete()

    @pytest.mark.asyncio
    async def test_recommends_quick_for_large_dataset(self, async_authorized_client):
        from app.models.user_data import UserData

        dataset = UserData(
            user_id="test_user_123",
            filename="big.csv",
            original_filename="big.csv",
            s3_url="s3://test-bucket/big.csv",
            num_rows=200_000,
            num_columns=6,
            data_schema=[],
        )
        await dataset.insert()
        try:
            resp = await async_authorized_client.get(
                f"/api/v1/ml/datasets/{dataset.id}/mode-recommendation"
            )
            assert resp.status_code == 200
            assert resp.json()["recommended_mode"] == "quick"
        finally:
            await dataset.delete()

    @pytest.mark.asyncio
    async def test_unknown_dataset_404(self, async_authorized_client):
        resp = await async_authorized_client.get(
            "/api/v1/ml/datasets/000000000000000000000000/mode-recommendation"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_foreign_dataset_404(self, async_authorized_client):
        from app.models.user_data import UserData

        dataset = UserData(
            user_id="someone_else",
            filename="foreign.csv",
            original_filename="foreign.csv",
            s3_url="s3://test-bucket/foreign.csv",
            num_rows=500,
            num_columns=6,
            data_schema=[],
        )
        await dataset.insert()
        try:
            resp = await async_authorized_client.get(
                f"/api/v1/ml/datasets/{dataset.id}/mode-recommendation"
            )
            assert resp.status_code == 404
        finally:
            await dataset.delete()
