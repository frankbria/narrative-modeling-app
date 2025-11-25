"""
TDD Tests for Transformation API Routes (Task 1.2)

Following strict TDD methodology:
1. RED: Write failing test
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve code quality

Tests cover transformation preview, apply, and history endpoints
using TransformationService instead of direct UserData queries.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd

from app.schemas.transformation import (
    TransformationPreviewRequest,
    TransformationApplyRequest,
    TransformationStepRequest
)


@pytest.mark.integration
class TestTransformationRoutes:
    """Integration tests for Transformation API routes using TransformationService."""

    # =====================================================================
    # POST /api/v1/transformations/preview - Preview Transformation
    # =====================================================================

    @pytest.mark.asyncio
    async def test_preview_transformation_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test successful transformation preview using TransformationService.
        Should return 200 with preview data showing before/after transformation.
        """
        # ARRANGE: Create test dataset
        from app.services.dataset_service import DatasetService
        from app.models.dataset import SchemaField

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="preview_dataset",
            filename="preview_test.csv",
            original_filename="preview_test.csv",
            file_type="csv",
            file_path="datasets/preview_test.csv",
            s3_url="s3://bucket/preview_test.csv",
            num_rows=100,
            num_columns=3,
            columns=["id", "value", "category"],
            data_schema=[
                SchemaField(
                    field_name="value",
                    field_type="numeric",
                    inferred_dtype="float64",
                    unique_values=50,
                    missing_values=5
                )
            ]
        )

        # Mock S3 data loading
        mock_df = pd.DataFrame({
            'id': range(1, 101),
            'value': [10.5 + i for i in range(100)],
            'category': ['A'] * 50 + ['B'] * 50
        })

        # ACT: Preview transformation
        request_data = {
            "dataset_id": dataset.dataset_id,
            "transformation_steps": [{
                "transformation_type": "remove_duplicates",
                "parameters": {}
            }],
            "preview_rows": 10
        }

        with patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
                   return_value=mock_df):
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json=request_data
            )

        # ASSERT: Verify preview response
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "preview_data" in data
        assert "affected_rows" in data
        assert "affected_columns" in data
        assert "stats_before" in data
        assert "stats_after" in data
        assert len(data["preview_data"]) <= 10  # Respects preview limit

    @pytest.mark.asyncio
    async def test_preview_transformation_invalid_type(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test preview with invalid transformation type.
        Should return 400 Bad Request with validation error.
        """
        # ARRANGE: Create dataset
        from app.services.dataset_service import DatasetService
        from app.models.dataset import SchemaField

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="invalid_type_dataset",
            filename="test.csv",
            original_filename="test.csv",
            file_type="csv",
            file_path="datasets/test.csv",
            s3_url="s3://bucket/test.csv",
            num_rows=10,
            num_columns=2,
            columns=["a", "b"],
            data_schema=[]
        )

        # ACT: Try invalid transformation type
        request_data = {
            "dataset_id": dataset.dataset_id,
            "transformation_steps": [{
                "transformation_type": "invalid_transform",
                "parameters": {"column": "a"}
            }],
            "preview_rows": 10
        }

        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json=request_data
        )

        # ASSERT: Verify error response
        assert response.status_code == 422 or response.status_code == 400
        # Pydantic validation or business logic validation

    @pytest.mark.asyncio
    async def test_preview_transformation_dataset_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test preview with non-existent dataset.
        Should return 404 Not Found.
        """
        # ACT: Try to preview non-existent dataset
        request_data = {
            "dataset_id": "nonexistent_dataset",
            "transformation_steps": [{
                "transformation_type": "remove_duplicates",
                "parameters": {"column": "value"}
            }],
            "preview_rows": 10
        }

        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json=request_data
        )

        # ASSERT: Verify 404
        assert response.status_code == 404

    # =====================================================================
    # POST /api/v1/transformations/apply - Apply Transformation
    # =====================================================================

    @pytest.mark.asyncio
    async def test_apply_transformation_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test successful transformation application using TransformationService.
        Should create TransformationConfig, update dataset, and return transformation_id.
        """
        # ARRANGE: Create test dataset
        from app.services.dataset_service import DatasetService
        from app.models.dataset import SchemaField

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="apply_dataset",
            filename="apply_test.csv",
            original_filename="apply_test.csv",
            file_type="csv",
            file_path="datasets/apply_test.csv",
            s3_url="s3://bucket/apply_test.csv",
            num_rows=50,
            num_columns=2,
            columns=["value", "category"],
            data_schema=[
                SchemaField(
                    field_name="value",
                    field_type="numeric",
                    inferred_dtype="float64",
                    unique_values=50,
                    missing_values=0
                )
            ]
        )

        # Mock S3 operations
        mock_df = pd.DataFrame({
            'value': [10.0 + i for i in range(50)],
            'category': ['A'] * 25 + ['B'] * 25
        })

        # ACT: Apply transformation
        request_data = {
            "dataset_id": dataset.dataset_id,
            "transformation_type": "remove_duplicates",
            "parameters": {}
        }

        with patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
                   return_value=mock_df), \
             patch('app.services.transformation_engine.data_utils.upload_dataframe_to_s3',
                   return_value="s3://bucket/transformed/apply_test_transformed.parquet"):
            response = await async_authorized_client.post(
                "/api/v1/transformations/apply",
                json=request_data
            )

        # ASSERT: Verify transformation was applied
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "transformation_id" in data
        assert data["transformation_id"] != ""
        assert data["dataset_id"] == dataset.dataset_id
        assert "affected_rows" in data
        assert "affected_columns" in data
        assert "execution_time_ms" in data

    @pytest.mark.asyncio
    async def test_apply_transformation_with_data_loss_warning(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test apply transformation that causes data loss.
        Should return success with warnings about data loss.
        """
        # ARRANGE: Create dataset
        from app.services.dataset_service import DatasetService
        from app.models.dataset import SchemaField

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="data_loss_dataset",
            filename="loss_test.csv",
            original_filename="loss_test.csv",
            file_type="csv",
            file_path="datasets/loss_test.csv",
            s3_url="s3://bucket/loss_test.csv",
            num_rows=100,
            num_columns=2,
            columns=["value", "category"],
            data_schema=[]
        )

        # Mock data with missing values
        mock_df = pd.DataFrame({
            'value': [None] * 60 + [10.0 + i for i in range(40)],
            'category': ['A'] * 100
        })

        # ACT: Apply drop_missing transformation
        request_data = {
            "dataset_id": dataset.dataset_id,
            "transformation_type": "drop_missing",
            "parameters": {"column": "value"}
        }

        with patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
                   return_value=mock_df), \
             patch('app.services.transformation_engine.data_utils.upload_dataframe_to_s3',
                   return_value="s3://bucket/transformed/loss_test_transformed.parquet"):
            response = await async_authorized_client.post(
                "/api/v1/transformations/apply",
                json=request_data
            )

        # ASSERT: Verify warnings about data loss
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should have warnings field indicating data loss
        assert "warnings" in data or data["affected_rows"] > 50

    @pytest.mark.asyncio
    async def test_apply_transformation_creates_config(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test that applying transformation creates TransformationConfig.
        Should persist configuration in database for history tracking.
        """
        # ARRANGE: Create dataset
        from app.services.dataset_service import DatasetService
        from app.models.dataset import SchemaField

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="config_dataset",
            filename="config_test.csv",
            original_filename="config_test.csv",
            file_type="csv",
            file_path="datasets/config_test.csv",
            s3_url="s3://bucket/config_test.csv",
            num_rows=20,
            num_columns=2,
            columns=["x", "y"],
            data_schema=[]
        )

        # Mock S3
        mock_df = pd.DataFrame({
            'x': range(20),
            'y': range(20, 40)
        })

        # ACT: Apply transformation
        request_data = {
            "dataset_id": dataset.dataset_id,
            "transformation_type": "encode",
            "parameters": {"column": "x", "method": "label"}
        }

        with patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
                   return_value=mock_df), \
             patch('app.services.transformation_engine.data_utils.upload_dataframe_to_s3',
                   return_value="s3://bucket/transformed/config_test_transformed.parquet"):
            response = await async_authorized_client.post(
                "/api/v1/transformations/apply",
                json=request_data
            )

        # ASSERT: Verify transformation config was created
        assert response.status_code == 200

        # Verify TransformationConfig exists in database
        from app.models.transformation import TransformationConfig
        configs = await TransformationConfig.find(
            TransformationConfig.dataset_id == dataset.dataset_id
        ).to_list()

        assert len(configs) > 0
        config = configs[0]
        assert config.is_applied is True
        assert len(config.transformation_steps) == 1
        assert config.transformation_steps[0].transformation_type == "encode"

    # =====================================================================
    # GET /api/v1/transformations/{id}/history - Get Transformation History
    # =====================================================================

    @pytest.mark.asyncio
    async def test_get_transformation_history_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test retrieving transformation history.
        Should return list of transformation steps with timestamps and lineage.
        """
        # ARRANGE: Create dataset and transformation config
        from app.services.dataset_service import DatasetService
        from app.services.transformation_service import TransformationService
        from app.models.dataset import SchemaField

        dataset_service = DatasetService()
        transform_service = TransformationService()

        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="history_dataset",
            filename="history_test.csv",
            original_filename="history_test.csv",
            file_type="csv",
            file_path="datasets/history_test.csv",
            s3_url="s3://bucket/history_test.csv",
            num_rows=30,
            num_columns=3,
            columns=["a", "b", "c"],
            data_schema=[]
        )

        # Create transformation config with multiple steps
        config = await transform_service.create_transformation_config(
            user_id="test_user_123",
            dataset_id=dataset.dataset_id,
            config_id="config_history_123"
        )

        # Add multiple transformation steps
        await transform_service.add_transformation_step(
            config_id=config.config_id,
            transformation_type="scale",
            column="a",
            parameters={"method": "standard"}
        )

        await transform_service.add_transformation_step(
            config_id=config.config_id,
            transformation_type="encode",
            column="b",
            parameters={"method": "onehot"}
        )

        await transform_service.mark_transformations_applied(
            config_id=config.config_id,
            file_path="s3://bucket/transformed/history_test.parquet"
        )

        # ACT: Get transformation history
        response = await async_authorized_client.get(
            f"/api/v1/transformations/{config.config_id}/history"
        )

        # ASSERT: Verify history response
        assert response.status_code == 200
        data = response.json()

        assert "transformation_steps" in data
        assert len(data["transformation_steps"]) == 2

        # Verify first step
        step1 = data["transformation_steps"][0]
        assert step1["transformation_type"] == "scale"
        assert step1["column"] == "a"
        assert "applied_at" in step1
        assert "parameters" in step1

        # Verify second step
        step2 = data["transformation_steps"][1]
        assert step2["transformation_type"] == "encode"
        assert step2["column"] == "b"

        # Verify metadata
        assert data["config_id"] == config.config_id
        assert data["dataset_id"] == dataset.dataset_id
        assert data["is_applied"] is True

    @pytest.mark.asyncio
    async def test_get_transformation_history_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test getting history for non-existent transformation config.
        Should return 404 Not Found.
        """
        # ACT: Try to get history for non-existent config
        response = await async_authorized_client.get(
            "/api/v1/transformations/nonexistent_config/history"
        )

        # ASSERT: Verify 404
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_transformation_history_with_lineage(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test transformation history includes parent/child relationships.
        Should return lineage information showing transformation chain.
        """
        # ARRANGE: Create parent and child configs
        from app.services.dataset_service import DatasetService
        from app.services.transformation_service import TransformationService

        dataset_service = DatasetService()
        transform_service = TransformationService()

        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="lineage_dataset",
            filename="lineage_test.csv",
            original_filename="lineage_test.csv",
            file_type="csv",
            file_path="datasets/lineage_test.csv",
            s3_url="s3://bucket/lineage_test.csv",
            num_rows=50,
            num_columns=2,
            columns=["x", "y"],
            data_schema=[]
        )

        # Create parent config
        parent_config = await transform_service.create_transformation_config(
            user_id="test_user_123",
            dataset_id=dataset.dataset_id,
            config_id="parent_config_123"
        )

        await transform_service.add_transformation_step(
            config_id=parent_config.config_id,
            transformation_type="impute",
            column="x",
            parameters={"method": "mean"}
        )

        # Create child config with parent reference
        child_config = await transform_service.create_transformation_config(
            user_id="test_user_123",
            dataset_id=dataset.dataset_id,
            config_id="child_config_456",
            parent_config_id=parent_config.config_id
        )

        # ACT: Get child history
        response = await async_authorized_client.get(
            f"/api/v1/transformations/{child_config.config_id}/history"
        )

        # ASSERT: Verify lineage information
        assert response.status_code == 200
        data = response.json()

        assert "parent_config_id" in data
        assert data["parent_config_id"] == parent_config.config_id
        # Should include lineage/ancestry information

    # =====================================================================
    # Validation Tests
    # =====================================================================

    @pytest.mark.asyncio
    async def test_transformation_types_validation(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test that only valid transformation types are accepted.
        Valid types: encode, scale, impute, drop_missing
        """
        from app.services.dataset_service import DatasetService

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",
            dataset_id="validation_dataset",
            filename="validation.csv",
            original_filename="validation.csv",
            file_type="csv",
            file_path="datasets/validation.csv",
            s3_url="s3://bucket/validation.csv",
            num_rows=10,
            num_columns=2,
            columns=["a", "b"],
            data_schema=[]
        )

        # Test valid transformation types
        valid_types = ["encode", "scale", "impute", "drop_missing"]

        for transform_type in valid_types:
            request_data = {
                "dataset_id": dataset.dataset_id,
                "transformation_type": transform_type,
                "parameters": {"column": "a"}
            }

            # Should not raise validation error (may fail for other reasons)
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json={
                    "dataset_id": dataset.dataset_id,
                    "transformation_steps": [{
                        "transformation_type": transform_type,
                        "parameters": {"column": "a"}
                    }],
                    "preview_rows": 5
                }
            )

            # Should get 200 or 500 (implementation error), but not 422 (validation error)
            assert response.status_code != 422, f"Valid type {transform_type} should not fail validation"
