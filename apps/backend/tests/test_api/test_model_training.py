"""
Tests for model training API endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import io

from app.models.ml_model import MLModel
from app.services.model_training import ProblemType
from app.services.model_training.automl_engine import ModelCandidate, AutoMLResult


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
    mock_dataset.created_at = datetime.now(timezone.utc)
    return mock_dataset


@pytest.fixture
def sample_ml_model():
    """Create a sample ML model mock"""
    from beanie import PydanticObjectId
    import uuid

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
    mock_model.metrics = {"accuracy": 0.85, "f1": 0.83}
    mock_model.feature_importance = {"feature1": 0.5, "feature2": 0.3, "feature3": 0.2}
    mock_model.training_config = {"max_models": 5, "cv_folds": 5}
    mock_model.version = "1.0.0"
    mock_model.created_at = datetime.now(timezone.utc)
    mock_model.updated_at = datetime.now(timezone.utc)
    mock_model.last_used_at = None
    mock_model.is_active = True
    mock_model.save = AsyncMock()
    return mock_model


@pytest.fixture
def sample_dataframe():
    """Create a sample dataframe"""
    np.random.seed(42)
    return pd.DataFrame({
        'feature1': np.random.randn(100),
        'feature2': np.random.randn(100),
        'feature3': np.random.choice(['A', 'B', 'C'], 100),
        'target': np.random.choice([0, 1], 100)
    })


class TestModelTrainingEndpoints:
    """Test model training API endpoints"""
    
    @pytest.mark.asyncio
    async def test_train_model_endpoint(self, async_authorized_client):
        """Test POST /api/v1/ml/train"""
        # Mock dataset lookup
        mock_user_data = MagicMock(
            id="dataset_123",
            user_id="test_user",
            file_key="uploads/test_user/test_data.csv"
        )

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data

            # Mock the background task function to prevent it from executing
            with patch('app.api.routes.model_training.train_model_task', new_callable=AsyncMock):
                request_data = {
                    "dataset_id": "dataset_123",
                    "target_column": "target",
                    "name": "My Model",
                    "description": "Test model"
                }

                response = await async_authorized_client.post(
                    "/api/v1/ml/train",
                    json=request_data,
                    headers={"Authorization": "Bearer test_token"}
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
        mock_model.created_at = datetime.now(timezone.utc)
        mock_model.last_used_at = None
        mock_model.is_active = True

        # Mock model listing
        with patch('app.services.model_storage.ModelStorageService.list_models', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [mock_model]

            response = await async_authorized_client.get(
                "/api/v1/ml/",
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["model_id"] == "model_123"
            assert data[0]["name"] == "Test Model"
    
    @pytest.mark.asyncio
    async def test_get_model_endpoint(self, async_authorized_client, sample_ml_model):
        """Test GET /api/v1/ml/{model_id}"""
        with patch('app.models.ml_model.MLModel.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = sample_ml_model

            response = await async_authorized_client.get(
                "/api/v1/ml/model_123"
            )

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
        mock_model.predict_proba.return_value = np.array([[0.8, 0.2], [0.3, 0.7], [0.9, 0.1]])

        with patch('app.services.model_storage.ModelStorageService.load_model', new_callable=AsyncMock) as mock_load:
            mock_load.return_value = (mock_model, None)

            # Mock model metadata
            with patch('app.models.ml_model.MLModel.find_one', new_callable=AsyncMock) as mock_find:
                mock_find.return_value = MagicMock(
                    feature_names=["feature1", "feature2", "feature3"]
                )

                request_data = {
                    "data": [
                        {"feature1": 1.0, "feature2": 2.0, "feature3": "A"},
                        {"feature1": 1.5, "feature2": 2.5, "feature3": "B"},
                        {"feature1": 2.0, "feature2": 3.0, "feature3": "C"}
                    ],
                    "include_probabilities": True
                }

                response = await async_authorized_client.post(
                    "/api/v1/ml/model_123/predict",
                    json=request_data
                )
                data = response.json()

                assert response.status_code == 200
                assert data["predictions"] == [0, 1, 0]
                assert len(data["probabilities"]) == 3
                assert data["feature_names"] == ["feature1", "feature2", "feature3"]
    
    @pytest.mark.asyncio
    async def test_delete_model_endpoint(self, async_authorized_client):
        """Test DELETE /api/v1/ml/{model_id}"""
        with patch('app.services.model_storage.ModelStorageService.delete_model', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True

            response = await async_authorized_client.delete(
                "/api/v1/ml/model_123"
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "deleted successfully" in data["message"]
    
    @pytest.mark.asyncio
    async def test_deactivate_model_endpoint(self, async_authorized_client, sample_ml_model):
        """Test PUT /api/v1/ml/{model_id}/deactivate"""
        sample_ml_model.save = AsyncMock()

        with patch('app.models.ml_model.MLModel.find_one', new_callable=AsyncMock) as mock_find:
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
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            request_data = {
                "dataset_id": "non_existent",
                "target_column": "target"
            }

            response = await async_authorized_client.post(
                "/api/v1/ml/train",
                json=request_data
            )

            assert response.status_code == 404
            assert "Dataset not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_predict_model_not_found(self, async_authorized_client):
        """Test prediction with non-existent model"""
        with patch('app.services.model_storage.ModelStorageService.load_model') as mock_load:
            mock_load.side_effect = ValueError("Model not found")
            
            request_data = {
                "data": [{"feature1": 1.0}]
            }
            
            response = await async_authorized_client.post(
                "/api/v1/ml/non_existent/predict",
                json=request_data
            )
            
            assert response.status_code == 404
            assert "Model not found" in response.json()["detail"]


class TestModelTrainingBackgroundTask:
    """Test the background training task"""
    
    @pytest.mark.asyncio
    async def test_train_model_task_success(self, sample_dataset, sample_dataframe):
        """Test successful model training task"""
        from app.api.routes.model_training import train_model_task, TrainModelRequest

        # Mock S3 file loading
        with patch('app.services.s3_service.S3Service.download_file_bytes', new_callable=AsyncMock) as mock_s3:
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
                    training_time=10.5
                ),
                all_models=[],
                problem_type=ProblemType.BINARY_CLASSIFICATION,
                feature_names=["feature1", "feature2", "feature3"],
                feature_importance={"feature1": 0.5, "feature2": 0.3, "feature3": 0.2},
                training_time=15.0,
                metadata={}
            )

            with patch('app.services.model_training.AutoMLEngine.run', new_callable=AsyncMock) as mock_run:
                mock_run.return_value = mock_result

                # Mock model storage
                with patch('app.services.model_storage.ModelStorageService.save_model', new_callable=AsyncMock) as mock_save:
                    mock_save.return_value = MagicMock(model_id="model_123")

                    request = TrainModelRequest(
                        dataset_id="dataset_123",
                        target_column="target",
                        name="Test Model"
                    )

                    # Run the task
                    await train_model_task(
                        sample_dataset,
                        request,
                        "test_user",
                        "model_123"
                    )

                    # Verify calls
                    mock_s3.assert_called_once()
                    mock_run.assert_called_once()
                    mock_save.assert_called_once()


class TestTrainingStatusEndpoint:
    """Test GET /api/v1/ml/{model_id}/status and job lifecycle tracking."""

    @pytest.mark.asyncio
    async def test_train_creates_pending_job(self, async_authorized_client):
        """POST /train persists a pending TrainingJob and it is queryable."""
        from app.models.training_job import TrainingJob
        from app.models.batch_job import JobStatus

        mock_user_data = MagicMock(
            id="dataset_123",
            user_id="test_user_123",
            file_key="uploads/test_user/test_data.csv",
        )

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            with patch('app.api.routes.model_training.train_model_task', new_callable=AsyncMock):
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
        from app.models.training_job import TrainingJob, ModelComparisonEntry

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
                ModelComparisonEntry(algorithm="XGBoost", cv_score=0.91, test_score=0.9),
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
        from app.api.routes.model_training import train_model_task, TrainModelRequest
        from app.models.training_job import TrainingJob
        from app.models.batch_job import JobStatus

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
                'app.services.s3_service.S3Service.download_file_bytes',
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
        from app.api.routes.model_training import train_model_task, TrainModelRequest
        from app.models.training_job import TrainingJob
        from app.models.batch_job import JobStatus
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
                'app.services.s3_service.S3Service.download_file_bytes',
                new_callable=AsyncMock,
            ) as mock_s3:
                mock_s3.return_value = csv_buffer.getvalue()
                with patch(
                    'app.services.model_training.AutoMLEngine.run',
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
    async def test_train_model_task_emits_lifecycle_logs(
        self, sample_dataset, sample_dataframe, setup_database
    ):
        """A successful task records task-start, download, and completion logs."""
        from app.api.routes.model_training import train_model_task, TrainModelRequest
        from app.models.training_job import TrainingJob
        from app.models.batch_job import JobStatus

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
                'app.services.s3_service.S3Service.download_file_bytes',
                new_callable=AsyncMock,
            ) as mock_s3:
                mock_s3.return_value = csv_buffer.getvalue()
                with patch(
                    'app.services.model_training.AutoMLEngine.run',
                    new_callable=AsyncMock,
                ) as mock_run:
                    mock_run.return_value = mock_result
                    with patch(
                        'app.services.model_storage.ModelStorageService.save_model',
                        new_callable=AsyncMock,
                    ) as mock_save:
                        mock_save.return_value = MagicMock(
                            model_id="model_task_logs"
                        )
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
                "Training completed" in m and "Random Forest" in m
                for m in messages
            )
        finally:
            await job.delete()
