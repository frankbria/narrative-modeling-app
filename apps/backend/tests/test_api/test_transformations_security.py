"""
Security Tests for Transformation API Authorization

Tests OWASP A01 (Broken Access Control) and CWE-639 (Authorization Bypass)
prevention in transformation preview and apply endpoints.

Critical security requirements:
1. Users can only preview/transform datasets they own
2. S3 file paths must match dataset's stored path
3. Dataset ID enumeration should not leak information
4. Error messages should not reveal existence of other users' datasets
"""

import pytest
from unittest.mock import AsyncMock, patch
import pandas as pd

from app.models.dataset import SchemaField


@pytest.mark.integration
class TestTransformationSecurityViaAPI:
    """Integration tests for transformation API security via HTTP endpoints."""

    @pytest.mark.asyncio
    async def test_preview_transformation_unauthorized_access(self, async_authorized_client, setup_database):
        """
        Test that user A cannot preview transformations on user B's dataset via API.

        Security requirement: OWASP A01 - Broken Access Control prevention
        Expected: 404 status code without revealing dataset exists
        """
        # ARRANGE: Create dataset owned by different user
        from app.services.dataset_service import DatasetService

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="other_user",  # Different from test_user_123 (the authorized client)
            dataset_id="security_test_dataset_1",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="datasets/security_test.csv",
            s3_url="s3://bucket/security_test.csv",
            num_rows=100,
            num_columns=3,
            columns=["col1", "col2", "col3"],
            data_schema=[
                SchemaField(
                    field_name="col1",
                    field_type="text",
                    inferred_dtype="object",
                    unique_values=50,
                    missing_values=0,
                    example_values=["a", "b", "c"],
                    is_constant=False,
                    is_high_cardinality=False
                )
            ]
        )

        # ACT: Current user (test_user_123) attempts to preview other user's dataset
        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json={
                "dataset_id": "security_test_dataset_1",
                "transformation_steps": [{
                    "transformation_type": "drop_missing",
                    "parameters": {}
                }],
                "preview_rows": 10
            }
        )

        # ASSERT: Should return 404 (not revealing dataset exists)
        assert response.status_code == 404
        assert "not found or not owned by user" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_preview_transformation_authorized_access(self, async_authorized_client, setup_database):
        """
        Test that user CAN preview transformations on their own dataset via API.

        Security requirement: Legitimate access should work
        Expected: 200 status code with preview data
        """
        # ARRANGE: Create dataset owned by current user
        from app.services.dataset_service import DatasetService

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="test_user_123",  # Same as authorized client
            dataset_id="security_test_dataset_2",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="datasets/security_test2.csv",
            s3_url="s3://bucket/security_test2.csv",
            num_rows=100,
            num_columns=3,
            columns=["col1", "col2", "col3"],
            data_schema=[
                SchemaField(
                    field_name="col1",
                    field_type="text",
                    inferred_dtype="object",
                    unique_values=50,
                    missing_values=0,
                    example_values=["a", "b", "c"],
                    is_constant=False,
                    is_high_cardinality=False
                )
            ]
        )

        # Mock S3 data
        mock_df = pd.DataFrame({
            'col1': ['a', 'b', 'c'],
            'col2': [1, 2, 3],
            'col3': [None, 5, 6]
        })

        # ACT: Current user previews their own dataset
        with patch('app.services.transformation_engine.data_utils.get_dataframe_from_s3',
                   new_callable=AsyncMock, return_value=mock_df):
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json={
                    "dataset_id": "security_test_dataset_2",
                    "transformation_steps": [{
                        "transformation_type": "drop_missing",
                        "parameters": {}
                    }],
                    "preview_rows": 10
                }
            )

        # ASSERT: Should succeed
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert "preview_data" in response_data

    @pytest.mark.asyncio
    async def test_apply_transformation_unauthorized_access(self, async_authorized_client, setup_database):
        """
        Test that user A cannot apply transformations to user B's dataset via API.

        Security requirement: OWASP A01 - Broken Access Control prevention
        Expected: 404 status code
        """
        # ARRANGE: Create dataset owned by different user
        from app.services.dataset_service import DatasetService

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="other_user",  # Different from test_user_123
            dataset_id="security_test_dataset_3",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="datasets/security_test3.csv",
            s3_url="s3://bucket/security_test3.csv",
            num_rows=100,
            num_columns=3,
            columns=["col1", "col2", "col3"],
            data_schema=[
                SchemaField(
                    field_name="col1",
                    field_type="text",
                    inferred_dtype="object",
                    unique_values=50,
                    missing_values=0,
                    example_values=["a", "b", "c"],
                    is_constant=False,
                    is_high_cardinality=False
                )
            ]
        )

        # ACT: Current user attempts to apply transformation to other user's dataset
        response = await async_authorized_client.post(
            "/api/v1/transformations/apply",
            json={
                "dataset_id": "security_test_dataset_3",
                "transformation_type": "drop_missing",
                "parameters": {}
            }
        )

        # ASSERT: Should return 404
        assert response.status_code == 404
        assert "not owned by user" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_dataset_id_enumeration_prevention(self, async_authorized_client, setup_database):
        """
        Test that non-existent and unauthorized datasets return same error.

        Security requirement: Prevent dataset ID enumeration
        Expected: Same 404 error for both cases
        """
        # ACT: Attempt to preview non-existent dataset
        response1 = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json={
                "dataset_id": "nonexistent_dataset_12345",
                "transformation_steps": [{
                    "transformation_type": "drop_missing",
                    "parameters": {}
                }],
                "preview_rows": 10
            }
        )

        # Create dataset owned by different user
        from app.services.dataset_service import DatasetService

        dataset_service = DatasetService()
        dataset = await dataset_service.create_dataset(
            user_id="other_user",
            dataset_id="security_test_dataset_4",
            filename="data.csv",
            original_filename="data.csv",
            file_type="csv",
            file_path="datasets/security_test4.csv",
            s3_url="s3://bucket/security_test4.csv",
            num_rows=100,
            num_columns=3,
            columns=["col1", "col2", "col3"],
            data_schema=[
                SchemaField(
                    field_name="col1",
                    field_type="text",
                    inferred_dtype="object",
                    unique_values=50,
                    missing_values=0,
                    example_values=["a", "b", "c"],
                    is_constant=False,
                    is_high_cardinality=False
                )
            ]
        )

        # Attempt to preview unauthorized dataset
        response2 = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json={
                "dataset_id": "security_test_dataset_4",
                "transformation_steps": [{
                    "transformation_type": "drop_missing",
                    "parameters": {}
                }],
                "preview_rows": 10
            }
        )

        # ASSERT: Both should return 404 with similar error messages
        assert response1.status_code == 404
        assert response2.status_code == 404
        # Error messages should be generic and not reveal ownership
        assert "not found or not owned by user" in response1.json()["detail"]
        assert "not found or not owned by user" in response2.json()["detail"]
