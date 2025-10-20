"""
TDD Tests for Dataset API Routes (Story 12.1)

Following strict TDD methodology:
1. RED: Write failing test
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve code quality
4. COMMIT: Save progress

Tests cover all 8 endpoints with success/error cases and backward compatibility.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from fastapi import UploadFile
import io

from app.schemas.dataset import (
    DatasetListResponse,
    DatasetDetailResponse,
    DatasetUploadResponse,
    DatasetUpdateRequest,
    DatasetDeleteResponse,
    DatasetProcessingRequest,
    DatasetProcessingResponse
)
from app.models.dataset import DatasetMetadata, SchemaField


@pytest.mark.integration
class TestDatasetRoutes:
    """Integration tests for Dataset API routes using DatasetService."""

    # =====================================================================
    # GET /api/v1/datasets - List Datasets
    # =====================================================================

    @pytest.mark.asyncio
    async def test_list_datasets_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test listing all datasets for authenticated user.
        Should return 200 with list of datasets.
        """
        # ARRANGE: Create test datasets for the user
        from app.services.dataset_service import DatasetService
        service = DatasetService()

        # Create two datasets
        await service.create_dataset(
            user_id="test_user_123",
            dataset_id="dataset_1",
            filename="test1.csv",
            original_filename="test1.csv",
            file_type="csv",
            file_path="datasets/test1.csv",
            s3_url="s3://bucket/test1.csv",
            num_rows=100,
            num_columns=3,
            columns=["id", "value", "category"],
            data_schema=[
                SchemaField(
                    field_name="id",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=100,
                    missing_values=0
                )
            ]
        )

        await service.create_dataset(
            user_id="test_user_123",
            dataset_id="dataset_2",
            filename="test2.csv",
            original_filename="test2.csv",
            file_type="csv",
            file_path="datasets/test2.csv",
            s3_url="s3://bucket/test2.csv",
            num_rows=50,
            num_columns=2,
            columns=["name", "age"],
            data_schema=[
                SchemaField(
                    field_name="name",
                    field_type="categorical",
                    inferred_dtype="object",
                    unique_values=50,
                    missing_values=5
                )
            ]
        )

        # ACT: Call the list endpoint
        response = await async_authorized_client.get("/api/v1/datasets")

        # ASSERT: Verify response
        assert response.status_code == 200
        data = response.json()
        assert "datasets" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["datasets"]) == 2

        # Verify dataset structure
        dataset = data["datasets"][0]
        assert "dataset_id" in dataset
        assert "filename" in dataset
        assert "num_rows" in dataset
        assert "num_columns" in dataset
        assert "is_processed" in dataset
        assert "created_at" in dataset

    @pytest.mark.asyncio
    async def test_list_datasets_empty(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test listing datasets when user has no datasets.
        Should return 200 with empty list.
        """
        # ACT: Call endpoint with no datasets
        response = await async_authorized_client.get("/api/v1/datasets")

        # ASSERT: Verify empty response
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["datasets"]) == 0

    @pytest.mark.asyncio
    async def test_list_datasets_unauthorized(self, async_test_client, setup_database):
        """
        🔴 RED: Test listing datasets without authentication.
        Should return 403 Forbidden (FastAPI HTTPBearer dependency behavior).
        """
        # ACT: Call endpoint without auth
        response = await async_test_client.get("/api/v1/datasets")

        # ASSERT: Verify unauthorized (403 is returned by HTTPBearer when credentials missing)
        assert response.status_code == 403

    # =====================================================================
    # POST /api/v1/datasets/upload - Upload Dataset
    # =====================================================================

    @pytest.mark.asyncio
    async def test_upload_dataset_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test successful dataset upload with CSV file.
        Should return 200 with dataset metadata.
        """
        # ARRANGE: Create CSV file content
        csv_content = b"id,value,category\n1,10.5,A\n2,20.3,B\n3,30.1,C"

        files = {
            'file': ('test.csv', io.BytesIO(csv_content), 'text/csv')
        }

        # Mock S3 upload
        with patch('app.utils.s3.upload_file_to_s3', return_value=(True, 's3://bucket/test.csv')):
            # ACT: Upload file
            response = await async_authorized_client.post(
                "/api/v1/datasets/upload",
                files=files
            )

        # ASSERT: Verify success response
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["status"] == "success"
        assert "dataset_id" in data
        assert data["filename"] == "test.csv"
        assert data["num_rows"] == 3
        assert data["num_columns"] == 3
        assert "preview" in data
        assert "headers" in data
        assert "s3_url" in data

        # Verify backward compatibility fields
        assert "file_id" in data  # Legacy field
        assert data["file_id"] == data["dataset_id"]

    @pytest.mark.asyncio
    async def test_upload_dataset_invalid_file_type(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test upload with invalid file type.
        Should return 400 Bad Request.
        """
        # ARRANGE: Create invalid file
        files = {
            'file': ('test.xyz', io.BytesIO(b"invalid content"), 'application/octet-stream')
        }

        # ACT: Try to upload
        response = await async_authorized_client.post(
            "/api/v1/datasets/upload",
            files=files
        )

        # ASSERT: Verify error
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_dataset_no_file(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test upload without file.
        Should return 422 Unprocessable Entity.
        """
        # ACT: Call upload without file
        response = await async_authorized_client.post("/api/v1/datasets/upload")

        # ASSERT: Verify error
        assert response.status_code == 422

    # =====================================================================
    # GET /api/v1/datasets/{id} - Get Dataset Detail
    # =====================================================================

    @pytest.mark.asyncio
    async def test_get_dataset_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test retrieving specific dataset by ID.
        Should return 200 with full dataset details.
        """
        # ARRANGE: Create dataset
        from app.services.dataset_service import DatasetService
        service = DatasetService()

        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="test_dataset_123",
            filename="detail_test.csv",
            original_filename="detail_test.csv",
            file_type="csv",
            file_path="datasets/detail_test.csv",
            s3_url="s3://bucket/detail_test.csv",
            num_rows=100,
            num_columns=3,
            columns=["id", "value", "category"],
            data_schema=[
                SchemaField(
                    field_name="id",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=100,
                    missing_values=0
                )
            ],
            statistics={"id": {"mean": 50.5}},
            quality_report={"completeness": 1.0}
        )

        # ACT: Get dataset by ID
        response = await async_authorized_client.get(f"/api/v1/datasets/{dataset.dataset_id}")

        # ASSERT: Verify response
        assert response.status_code == 200
        data = response.json()

        assert data["dataset_id"] == "test_dataset_123"
        assert data["filename"] == "detail_test.csv"
        assert data["num_rows"] == 100
        assert data["num_columns"] == 3
        assert data["columns"] == ["id", "value", "category"]
        assert "statistics" in data
        assert "quality_report" in data
        assert "data_schema" in data
        assert "is_processed" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_get_dataset_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test retrieving non-existent dataset.
        Should return 404 Not Found.
        """
        # ACT: Try to get non-existent dataset
        response = await async_authorized_client.get("/api/v1/datasets/nonexistent_id")

        # ASSERT: Verify 404
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_dataset_wrong_user(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test accessing dataset owned by different user.
        Should return 403 Forbidden.
        """
        # ARRANGE: Create dataset for different user
        from app.services.dataset_service import DatasetService
        service = DatasetService()

        dataset = await service.create_dataset(
            user_id="other_user_456",
            dataset_id="other_dataset",
            filename="other.csv",
            original_filename="other.csv",
            file_type="csv",
            file_path="datasets/other.csv",
            s3_url="s3://bucket/other.csv",
            num_rows=10,
            num_columns=2,
            columns=["a", "b"],
            data_schema=[]
        )

        # ACT: Try to access as test_user_123
        response = await async_authorized_client.get(f"/api/v1/datasets/{dataset.dataset_id}")

        # ASSERT: Verify forbidden
        assert response.status_code == 403

    # =====================================================================
    # PUT /api/v1/datasets/{id} - Update Dataset
    # =====================================================================

    @pytest.mark.asyncio
    async def test_update_dataset_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test updating dataset metadata.
        Should return 200 with updated dataset.
        """
        # ARRANGE: Create dataset
        from app.services.dataset_service import DatasetService
        service = DatasetService()

        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="update_test",
            filename="update.csv",
            original_filename="update.csv",
            file_type="csv",
            file_path="datasets/update.csv",
            s3_url="s3://bucket/update.csv",
            num_rows=50,
            num_columns=2,
            columns=["x", "y"],
            data_schema=[]
        )

        # ACT: Update dataset
        update_data = {
            "statistics": {"x": {"mean": 25.5, "std": 10.2}},
            "quality_report": {"completeness": 0.95},
            "ai_summary": {
                "overview": "Test dataset overview",
                "issues": [],
                "relationships": [],
                "suggestions": [],
                "rawMarkdown": "# Summary\nTest dataset overview"
            }
        }

        response = await async_authorized_client.put(
            f"/api/v1/datasets/{dataset.dataset_id}",
            json=update_data
        )

        # ASSERT: Verify update
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "update_test"
        assert "statistics" in data
        assert data["statistics"]["x"]["mean"] == 25.5

    @pytest.mark.asyncio
    async def test_update_dataset_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test updating non-existent dataset.
        Should return 404 Not Found.
        """
        # ACT: Try to update non-existent dataset
        response = await async_authorized_client.put(
            "/api/v1/datasets/nonexistent",
            json={"statistics": {}}
        )

        # ASSERT: Verify 404
        assert response.status_code == 404

    # =====================================================================
    # DELETE /api/v1/datasets/{id} - Delete Dataset
    # =====================================================================

    @pytest.mark.asyncio
    async def test_delete_dataset_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test deleting dataset.
        Should return 200 with success message.
        """
        # ARRANGE: Create dataset
        from app.services.dataset_service import DatasetService
        service = DatasetService()

        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="delete_test",
            filename="delete.csv",
            original_filename="delete.csv",
            file_type="csv",
            file_path="datasets/delete.csv",
            s3_url="s3://bucket/delete.csv",
            num_rows=10,
            num_columns=1,
            columns=["data"],
            data_schema=[]
        )

        # ACT: Delete dataset
        response = await async_authorized_client.delete(f"/api/v1/datasets/{dataset.dataset_id}")

        # ASSERT: Verify deletion
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["dataset_id"] == "delete_test"

        # Verify dataset is actually deleted
        get_response = await async_authorized_client.get(f"/api/v1/datasets/{dataset.dataset_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_dataset_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test deleting non-existent dataset.
        Should return 404 Not Found.
        """
        # ACT: Try to delete non-existent dataset
        response = await async_authorized_client.delete("/api/v1/datasets/nonexistent")

        # ASSERT: Verify 404
        assert response.status_code == 404

    # =====================================================================
    # GET /api/v1/datasets/{id}/schema - Get Dataset Schema
    # =====================================================================

    @pytest.mark.asyncio
    async def test_get_dataset_schema_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test retrieving dataset schema.
        Should return 200 with schema fields.
        """
        # ARRANGE: Create dataset with schema
        from app.services.dataset_service import DatasetService
        service = DatasetService()

        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="schema_test",
            filename="schema.csv",
            original_filename="schema.csv",
            file_type="csv",
            file_path="datasets/schema.csv",
            s3_url="s3://bucket/schema.csv",
            num_rows=100,
            num_columns=3,
            columns=["id", "value", "category"],
            data_schema=[
                SchemaField(
                    field_name="id",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=100,
                    missing_values=0
                ),
                SchemaField(
                    field_name="value",
                    field_type="numeric",
                    inferred_dtype="float64",
                    unique_values=50,
                    missing_values=5
                ),
                SchemaField(
                    field_name="category",
                    field_type="categorical",
                    inferred_dtype="object",
                    unique_values=3,
                    missing_values=0
                )
            ]
        )

        # ACT: Get schema
        response = await async_authorized_client.get(f"/api/v1/datasets/{dataset.dataset_id}/schema")

        # ASSERT: Verify schema
        assert response.status_code == 200
        data = response.json()
        assert "schema" in data
        assert len(data["schema"]) == 3

        # Verify first field
        field = data["schema"][0]
        assert field["field_name"] == "id"
        assert field["field_type"] == "numeric"
        assert field["inferred_dtype"] == "int64"

    @pytest.mark.asyncio
    async def test_get_dataset_schema_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test getting schema for non-existent dataset.
        Should return 404 Not Found.
        """
        # ACT: Try to get schema for non-existent dataset
        response = await async_authorized_client.get("/api/v1/datasets/nonexistent/schema")

        # ASSERT: Verify 404
        assert response.status_code == 404

    # =====================================================================
    # GET /api/v1/datasets/{id}/preview - Get Data Preview
    # =====================================================================

    @pytest.mark.asyncio
    async def test_get_dataset_preview_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test retrieving dataset preview.
        Should return 200 with preview rows.
        """
        # ARRANGE: Create dataset with preview data
        from app.services.dataset_service import DatasetService
        service = DatasetService()

        preview_rows = [
            {"id": 1, "value": 10.5, "category": "A"},
            {"id": 2, "value": 20.3, "category": "B"},
            {"id": 3, "value": 30.1, "category": "C"}
        ]

        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="preview_test",
            filename="preview.csv",
            original_filename="preview.csv",
            file_type="csv",
            file_path="datasets/preview.csv",
            s3_url="s3://bucket/preview.csv",
            num_rows=100,
            num_columns=3,
            columns=["id", "value", "category"],
            data_schema=[],
            data_preview=preview_rows
        )

        # ACT: Get preview
        response = await async_authorized_client.get(f"/api/v1/datasets/{dataset.dataset_id}/preview")

        # ASSERT: Verify preview
        assert response.status_code == 200
        data = response.json()
        assert "preview" in data
        assert len(data["preview"]) == 3
        assert data["preview"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_get_dataset_preview_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test getting preview for non-existent dataset.
        Should return 404 Not Found.
        """
        # ACT: Try to get preview for non-existent dataset
        response = await async_authorized_client.get("/api/v1/datasets/nonexistent/preview")

        # ASSERT: Verify 404
        assert response.status_code == 404

    # =====================================================================
    # POST /api/v1/datasets/{id}/process - Mark Dataset as Processed
    # =====================================================================

    @pytest.mark.asyncio
    async def test_mark_dataset_processed_success(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test marking dataset as processed.
        Should return 200 with updated processing status.
        """
        # ARRANGE: Create unprocessed dataset
        from app.services.dataset_service import DatasetService
        service = DatasetService()

        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="process_test",
            filename="process.csv",
            original_filename="process.csv",
            file_type="csv",
            file_path="datasets/process.csv",
            s3_url="s3://bucket/process.csv",
            num_rows=50,
            num_columns=2,
            columns=["x", "y"],
            data_schema=[]
        )

        # Verify initially not processed
        assert dataset.is_processed is False

        # ACT: Mark as processed
        process_data = {
            "statistics": {"x": {"mean": 25.0}},
            "quality_report": {"completeness": 1.0},
            "inferred_schema": {"x": "numeric", "y": "numeric"}
        }

        response = await async_authorized_client.post(
            f"/api/v1/datasets/{dataset.dataset_id}/process",
            json=process_data
        )

        # ASSERT: Verify processing
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "process_test"
        assert data["is_processed"] is True
        assert "processed_at" in data

    @pytest.mark.asyncio
    async def test_mark_dataset_processed_not_found(self, async_authorized_client, setup_database):
        """
        🔴 RED: Test marking non-existent dataset as processed.
        Should return 404 Not Found.
        """
        # ACT: Try to mark non-existent dataset as processed
        response = await async_authorized_client.post(
            "/api/v1/datasets/nonexistent/process",
            json={}
        )

        # ASSERT: Verify 404
        assert response.status_code == 404
