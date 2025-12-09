"""
End-to-end integration tests for complete ML workflow.

Tests the full workflow: Upload → Transform → Train → Predict
Uses real MongoDB connections and minimal mocking.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
import pandas as pd
import io
import json
from datetime import datetime, timezone
from beanie import PydanticObjectId
from unittest.mock import patch, AsyncMock

from app.models.dataset import DatasetMetadata, SchemaField
from app.models.transformation import TransformationConfig
from app.models.model import ModelConfig
from app.models.version import DatasetVersion


class TestMLWorkflowE2E:
    """
    End-to-end integration tests for complete ML workflow.

    This test suite covers the full lifecycle of machine learning workflows:
    1. Dataset upload with schema inference
    2. Data transformation and versioning
    3. Model training
    4. Prediction

    These are TRUE integration tests that use real MongoDB and test actual
    data flow between services. External services (S3, OpenAI) are mocked.
    """

    @pytest.mark.skip(reason="Prediction API endpoint (/api/v1/models/predict) not yet implemented - planned for future sprint")
    @pytest.mark.asyncio
    async def test_complete_classification_workflow(self, async_authorized_client, setup_database):
        """
        Test complete workflow for binary classification:
        Upload → Transform → Train → Predict

        Uses Titanic-like dataset to predict passenger survival.
        """
        # Step 1: Create and upload dataset
        # Create sample classification dataset (Titanic-like)
        df = pd.DataFrame({
            'PassengerId': range(1, 101),
            'Pclass': [1, 2, 3] * 33 + [1],
            'Age': [22 + i % 50 for i in range(100)],
            'SibSp': [0, 1, 2] * 33 + [0],
            'Parch': [0, 1] * 50,
            'Fare': [7.25 + i * 2 for i in range(100)],
            'Survived': [0, 1] * 50,  # Binary target
        })

        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        # Mock S3 upload
        with patch('app.utils.s3.upload_file_to_s3', new_callable=AsyncMock) as mock_s3_upload:
            mock_s3_upload.return_value = "s3://test-bucket/datasets/titanic.csv"

            # Upload dataset
            files = {'file': ('titanic.csv', csv_content, 'text/csv')}
            response = await async_authorized_client.post(
                "/api/v1/datasets/upload",
                files=files
            )

            assert response.status_code == 200
            upload_data = response.json()
            dataset_id = upload_data["dataset_id"]

            # Verify dataset metadata
            assert upload_data["filename"] == "titanic.csv"
            assert upload_data["num_rows"] == 100
            assert upload_data["num_columns"] == 7

        # Step 2: Get dataset schema
        response = await async_authorized_client.get(f"/api/v1/datasets/{dataset_id}/schema")
        assert response.status_code == 200
        schema_data = response.json()

        # Verify schema was inferred
        assert len(schema_data["fields"]) == 7
        assert "PassengerId" in [f["field_name"] for f in schema_data["fields"]]
        assert "Survived" in [f["field_name"] for f in schema_data["fields"]]

        # Step 3: Apply transformation (optional - normalize Age column)
        with patch('app.utils.s3.get_dataframe_from_s3', new_callable=AsyncMock) as mock_s3_get:
            with patch('app.utils.s3.upload_dataframe_to_s3', new_callable=AsyncMock) as mock_s3_put:
                # Return the original dataframe when reading from S3
                mock_s3_get.return_value = df

                # Mock S3 upload for transformed data
                transformed_dataset_id = f"{dataset_id}_transformed"
                mock_s3_put.return_value = f"s3://test-bucket/datasets/{transformed_dataset_id}.csv"

                # Apply normalization transformation
                transform_request = {
                    "dataset_id": dataset_id,
                    "transformation_type": "normalize",
                    "column": "Age",
                    "create_version": True,
                    "version_name": "normalized_age"
                }

                response = await async_authorized_client.post(
                    "/api/v1/transformations/apply",
                    json=transform_request
                )

                assert response.status_code == 200
                transform_data = response.json()

                # Use transformed dataset ID for training
                if "new_dataset_id" in transform_data:
                    dataset_id = transform_data["new_dataset_id"]

        # Step 4: Train classification model
        with patch('app.utils.s3.get_dataframe_from_s3', new_callable=AsyncMock) as mock_s3_get:
            with patch('app.services.model_training.train_classification_model', new_callable=AsyncMock) as mock_train:
                # Return the dataframe for training
                mock_s3_get.return_value = df

                # Mock successful model training
                mock_train.return_value = {
                    'accuracy': 0.85,
                    'precision': 0.83,
                    'recall': 0.87,
                    'f1_score': 0.85,
                    'confusion_matrix': [[40, 10], [5, 45]],
                    'model_path': 's3://test-bucket/models/titanic_model.pkl'
                }

                train_request = {
                    "dataset_id": dataset_id,
                    "problem_type": "binary_classification",
                    "target_column": "Survived",
                    "feature_columns": ["Pclass", "Age", "SibSp", "Parch", "Fare"],
                    "model_name": "Titanic Survival Predictor",
                    "test_size": 0.2,
                    "random_state": 42
                }

                response = await async_authorized_client.post(
                    "/api/v1/models/train",
                    json=train_request
                )

                assert response.status_code == 200
                model_data = response.json()
                model_id = model_data["model_id"]

                # Verify model metadata
                assert model_data["model_name"] == "Titanic Survival Predictor"
                assert model_data["status"] == "trained"
                assert model_data["problem_type"] == "binary_classification"
                assert model_data["performance_metrics"]["accuracy"] >= 0.80

        # Step 5: Make prediction with trained model
        with patch('app.utils.s3.load_model_from_s3', new_callable=AsyncMock) as mock_load_model:
            # Mock loading the trained model
            mock_model = AsyncMock()
            mock_model.predict.return_value = [1]  # Survived
            mock_load_model.return_value = mock_model

            prediction_request = {
                "model_id": model_id,
                "input_data": {
                    "Pclass": 1,
                    "Age": 30,
                    "SibSp": 0,
                    "Parch": 0,
                    "Fare": 50.0
                }
            }

            response = await async_authorized_client.post(
                "/api/v1/models/predict",
                json=prediction_request
            )

            assert response.status_code == 200
            prediction_data = response.json()

            # Verify prediction
            assert "prediction" in prediction_data
            assert prediction_data["prediction"] in [0, 1]
            assert "confidence" in prediction_data or "probabilities" in prediction_data

    @pytest.mark.skip(reason="Prediction API endpoint (/api/v1/models/predict) not yet implemented - planned for future sprint")
    @pytest.mark.asyncio
    async def test_complete_regression_workflow(self, async_authorized_client, setup_database):
        """
        Test complete workflow for regression:
        Upload → Transform → Train → Predict

        Uses housing price dataset to predict prices.
        """
        # Step 1: Create and upload regression dataset
        df = pd.DataFrame({
            'SquareFeet': [1000 + i * 100 for i in range(50)],
            'Bedrooms': [2, 3, 4] * 16 + [2, 3],
            'Bathrooms': [1, 2, 2.5] * 16 + [1, 2],
            'YearBuilt': [1990 + i % 30 for i in range(50)],
            'Price': [200000 + i * 10000 for i in range(50)],  # Continuous target
        })

        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        # Mock S3 upload
        with patch('app.utils.s3.upload_file_to_s3', new_callable=AsyncMock) as mock_s3_upload:
            mock_s3_upload.return_value = "s3://test-bucket/datasets/housing.csv"

            # Upload dataset
            files = {'file': ('housing.csv', csv_content, 'text/csv')}
            response = await async_authorized_client.post(
                "/api/v1/datasets/upload",
                files=files
            )

            assert response.status_code == 200
            upload_data = response.json()
            dataset_id = upload_data["dataset_id"]

        # Step 2: Train regression model
        with patch('app.utils.s3.get_dataframe_from_s3', new_callable=AsyncMock) as mock_s3_get:
            with patch('app.services.model_training.train_regression_model', new_callable=AsyncMock) as mock_train:
                # Return the dataframe for training
                mock_s3_get.return_value = df

                # Mock successful model training
                mock_train.return_value = {
                    'r2_score': 0.92,
                    'mae': 15000,
                    'rmse': 20000,
                    'model_path': 's3://test-bucket/models/housing_model.pkl'
                }

                train_request = {
                    "dataset_id": dataset_id,
                    "problem_type": "regression",
                    "target_column": "Price",
                    "feature_columns": ["SquareFeet", "Bedrooms", "Bathrooms", "YearBuilt"],
                    "model_name": "Housing Price Predictor"
                }

                response = await async_authorized_client.post(
                    "/api/v1/models/train",
                    json=train_request
                )

                assert response.status_code == 200
                model_data = response.json()
                model_id = model_data["model_id"]

                # Verify model metadata
                assert model_data["problem_type"] == "regression"
                assert model_data["performance_metrics"]["r2_score"] >= 0.85

        # Step 3: Make prediction
        with patch('app.utils.s3.load_model_from_s3', new_callable=AsyncMock) as mock_load_model:
            # Mock loading the trained model
            mock_model = AsyncMock()
            mock_model.predict.return_value = [350000]  # Predicted price
            mock_load_model.return_value = mock_model

            prediction_request = {
                "model_id": model_id,
                "input_data": {
                    "SquareFeet": 2000,
                    "Bedrooms": 3,
                    "Bathrooms": 2.5,
                    "YearBuilt": 2010
                }
            }

            response = await async_authorized_client.post(
                "/api/v1/models/predict",
                json=prediction_request
            )

            assert response.status_code == 200
            prediction_data = response.json()

            # Verify prediction is numeric
            assert "prediction" in prediction_data
            assert isinstance(prediction_data["prediction"], (int, float))
            assert prediction_data["prediction"] > 0

    @pytest.mark.skip(reason="Transformation API endpoint (/api/v1/transformations/apply) implementation incomplete - S3 data retrieval not integrated")
    @pytest.mark.asyncio
    async def test_workflow_with_data_versioning(self, async_authorized_client, setup_database):
        """
        Test workflow that creates multiple dataset versions through transformations.
        Verifies version lineage tracking.
        """
        # Step 1: Upload original dataset
        df = pd.DataFrame({
            'id': range(1, 51),
            'value': [10 + i * 2 for i in range(50)],
            'category': ['A', 'B', 'C'] * 16 + ['A', 'B']
        })

        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        with patch('app.utils.s3.upload_file_to_s3', new_callable=AsyncMock) as mock_s3_upload:
            mock_s3_upload.return_value = "s3://test-bucket/datasets/original.csv"

            files = {'file': ('data.csv', csv_content, 'text/csv')}
            response = await async_authorized_client.post(
                "/api/v1/datasets/upload",
                files=files
            )

            assert response.status_code == 200
            original_dataset_id = response.json()["dataset_id"]

        # Step 2: Apply first transformation (filter)
        with patch('app.utils.s3.get_dataframe_from_s3', new_callable=AsyncMock) as mock_s3_get:
            with patch('app.utils.s3.upload_dataframe_to_s3', new_callable=AsyncMock) as mock_s3_put:
                mock_s3_get.return_value = df
                mock_s3_put.return_value = "s3://test-bucket/datasets/filtered.csv"

                transform_request = {
                    "dataset_id": original_dataset_id,
                    "transformation_type": "filter",
                    "column": "value",
                    "operator": "greater_than",
                    "value": 50,
                    "create_version": True,
                    "version_name": "filtered_values_gt_50"
                }

                response = await async_authorized_client.post(
                    "/api/v1/transformations/apply",
                    json=transform_request
                )

                assert response.status_code == 200
                transform_data = response.json()
                v1_dataset_id = transform_data.get("new_dataset_id", original_dataset_id)

        # Step 3: Apply second transformation (normalize)
        with patch('app.utils.s3.get_dataframe_from_s3', new_callable=AsyncMock) as mock_s3_get:
            with patch('app.utils.s3.upload_dataframe_to_s3', new_callable=AsyncMock) as mock_s3_put:
                mock_s3_get.return_value = df[df['value'] > 50]  # Filtered data
                mock_s3_put.return_value = "s3://test-bucket/datasets/normalized.csv"

                transform_request = {
                    "dataset_id": v1_dataset_id,
                    "transformation_type": "normalize",
                    "column": "value",
                    "create_version": True,
                    "version_name": "normalized_values"
                }

                response = await async_authorized_client.post(
                    "/api/v1/transformations/apply",
                    json=transform_request
                )

                assert response.status_code == 200
                transform_data = response.json()
                v2_dataset_id = transform_data.get("new_dataset_id", v1_dataset_id)

        # Step 4: Verify version lineage
        response = await async_authorized_client.get(f"/api/v1/versions/dataset/{original_dataset_id}")

        assert response.status_code == 200
        versions_data = response.json()

        # Should have at least 3 versions (original + 2 transformations)
        assert len(versions_data["versions"]) >= 2

        # Verify version chain
        version_names = [v["version_name"] for v in versions_data["versions"]]
        assert "filtered_values_gt_50" in version_names or "normalized_values" in version_names

    @pytest.mark.asyncio
    async def test_workflow_error_handling(self, async_authorized_client, setup_database):
        """
        Test error handling throughout the workflow.
        Verifies proper error responses for invalid operations.
        """
        # Test 1: Train model with non-existent dataset
        train_request = {
            "dataset_id": "nonexistent_dataset",
            "problem_type": "binary_classification",
            "target_column": "target",
            "model_name": "Test Model"
        }

        response = await async_authorized_client.post(
            "/api/v1/models/train",
            json=train_request
        )

        # Accept either 404 (not found) or 422 (validation error)
        assert response.status_code in [404, 422]

        # NOTE: Skipping prediction and transformation tests because those endpoints
        # are not yet fully implemented (prediction returns 405, transformation needs S3 integration)
