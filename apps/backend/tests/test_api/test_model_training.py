"""
Tests for model training API endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import io
import joblib

from app.models.ml_model import MLModel
from app.models.user_data import UserData
from app.services.model_training import AutoMLEngine, ProblemType
from app.services.model_training.automl_engine import ModelCandidate, AutoMLResult


@pytest.fixture
def sample_dataset():
    """Create a sample dataset mock"""
    mock_dataset = MagicMock()
    mock_dataset.id = "dataset_123"
    mock_dataset.user_id = "test_user"
    mock_dataset.filename = "test_data.csv"
    mock_dataset.file_size = 1024
    mock_dataset.file_type = "csv"
    mock_dataset.file_key = "uploads/test_user/test_data.csv"
    mock_dataset.created_at = datetime.now(timezone.utc)
    return mock_dataset


@pytest.fixture
def sample_ml_model():
    """Create a sample ML model mock"""
    mock_model = MagicMock()
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
    mock_model.created_at = datetime.now(timezone.utc)
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
    async def test_train_model_endpoint(self, mock_async_client):
        """Test POST /api/v1/ml/train"""
        # Mock dataset lookup
        mock_user_data = MagicMock(
            id="dataset_123",
            user_id="test_user",
            file_key="uploads/test_user/test_data.csv"
        )
        
        with patch('app.models.user_data.UserData.find_one') as mock_find:
            async def return_user_data(*args, **kwargs):
                return mock_user_data
            
            mock_find.return_value = return_user_data()
            
            # Mock background task
            with patch('app.api.routes.model_training.BackgroundTasks') as mock_bg:
                request_data = {
                    "dataset_id": "dataset_123",
                    "target_column": "target",
                    "name": "My Model",
                    "description": "Test model"
                }
                
                response = await mock_async_client.post(
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
    async def test_list_models_endpoint(self, mock_async_client):
        """Test GET /api/v1/ml/"""
        # Mock model listing
        with patch('app.services.model_storage.ModelStorageService.list_models') as mock_list:
            mock_list.return_value = AsyncMock(return_value=[
                MagicMock(
                    model_id="model_123",
                    name="Test Model",
                    description="Test description",
                    problem_type="classification",
                    algorithm="Random Forest",
                    target_column="target",
                    cv_score=0.85,
                    test_score=0.83,
                    created_at=datetime.now(timezone.utc),
                    last_used_at=None,
                    is_active=True
                )
            ])()
            
            response = await mock_async_client.get(
                "/api/v1/ml/",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["model_id"] == "model_123"
            assert data[0]["name"] == "Test Model"
    
    @pytest.mark.asyncio
    async def test_get_model_endpoint(self, mock_async_client, sample_ml_model):
        """Test GET /api/v1/ml/{model_id}"""
        with patch('app.models.ml_model.MLModel.find_one') as mock_find:
            mock_find.return_value = AsyncMock(return_value=sample_ml_model)()
            
            response = await mock_async_client.get(
                "/api/v1/ml/model_123",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["model_id"] == "model_123"
            assert data["name"] == "Test Model"
            assert data["algorithm"] == "Random Forest"
    
    @pytest.mark.asyncio
    async def test_predict_endpoint(self, mock_async_client):
        """Test POST /api/v1/ml/{model_id}/predict"""
        # Mock model loading
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0, 1, 0])
        mock_model.predict_proba.return_value = np.array([[0.8, 0.2], [0.3, 0.7], [0.9, 0.1]])
        
        with patch('app.services.model_storage.ModelStorageService.load_model') as mock_load:
            mock_load.return_value = AsyncMock(return_value=(mock_model, None))()
            
            # Mock model metadata
            with patch('app.models.ml_model.MLModel.find_one') as mock_find:
                mock_find.return_value = AsyncMock(return_value=MagicMock(
                    model_id="model_123",
                    algorithm="Random Forest",
                    problem_type="binary_classification",
                    target_column="target",
                    feature_names=["feature1", "feature2", "feature3"]
                ))()
                
                request_data = {
                    "data": [
                        {"feature1": 1.0, "feature2": 2.0, "feature3": "A"},
                        {"feature1": 1.5, "feature2": 2.5, "feature3": "B"},
                        {"feature1": 2.0, "feature2": 3.0, "feature3": "C"}
                    ],
                    "include_probabilities": True
                }
                
                response = await mock_async_client.post(
                    "/api/v1/ml/model_123/predict",
                    json=request_data,
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["predictions"] == [0, 1, 0]
                assert len(data["probabilities"]) == 3
                assert data["feature_names"] == ["feature1", "feature2", "feature3"]
    
    @pytest.mark.asyncio
    async def test_delete_model_endpoint(self, mock_async_client):
        """Test DELETE /api/v1/ml/{model_id}"""
        with patch('app.services.model_storage.ModelStorageService.delete_model') as mock_delete:
            mock_delete.return_value = AsyncMock(return_value=True)()
            
            response = await mock_async_client.delete(
                "/api/v1/ml/model_123",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "deleted successfully" in data["message"]
    
    @pytest.mark.asyncio
    async def test_deactivate_model_endpoint(self, mock_async_client, sample_ml_model):
        """Test PUT /api/v1/ml/{model_id}/deactivate"""
        sample_ml_model.save = AsyncMock()
        
        with patch('app.models.ml_model.MLModel.find_one') as mock_find:
            mock_find.return_value = AsyncMock(return_value=sample_ml_model)()
            
            response = await mock_async_client.put(
                "/api/v1/ml/model_123/deactivate",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "deactivated" in data["message"]
            assert sample_ml_model.is_active is False
    
    @pytest.mark.asyncio
    async def test_train_model_not_found(self, mock_async_client):
        """Test training with non-existent dataset"""
        with patch('app.models.user_data.UserData.find_one') as mock_find:
            mock_find.return_value = AsyncMock(return_value=None)()
            
            request_data = {
                "dataset_id": "non_existent",
                "target_column": "target"
            }
            
            response = await mock_async_client.post(
                "/api/v1/ml/train",
                json=request_data,
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 404
            assert "Dataset not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_predict_model_not_found(self, mock_async_client):
        """Test prediction with non-existent model"""
        with patch('app.services.model_storage.ModelStorageService.load_model') as mock_load:
            mock_load.side_effect = ValueError("Model not found")
            
            request_data = {
                "data": [{"feature1": 1.0}]
            }
            
            response = await mock_async_client.post(
                "/api/v1/ml/non_existent/predict",
                json=request_data,
                headers={"Authorization": "Bearer test_token"}
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
        with patch('app.services.s3_service.get_file_from_s3') as mock_s3:
            # Return CSV data
            csv_buffer = io.BytesIO()
            sample_dataframe.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            mock_s3.return_value = AsyncMock(return_value=csv_buffer.getvalue())()
            
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
            
            with patch('app.services.model_training.AutoMLEngine.run') as mock_run:
                mock_run.return_value = AsyncMock(return_value=mock_result)()
                
                # Mock model storage
                with patch('app.services.model_storage.ModelStorageService.save_model') as mock_save:
                    mock_save.return_value = AsyncMock(return_value=MagicMock(model_id="model_123"))()
                    
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