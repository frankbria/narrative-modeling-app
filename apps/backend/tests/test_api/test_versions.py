"""
Test suite for Data Versioning API endpoints.

Following TDD methodology - these tests are written BEFORE implementation.
Tests cover all version API endpoints with various scenarios and edge cases.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone
import uuid
from typing import List, Dict, Any

from app.models.version import DatasetVersion, TransformationLineage, TransformationStep
from app.models.dataset import DatasetMetadata, SchemaField
from app.services.versioning_service import versioning_service


@pytest.mark.integration
class TestVersionsAPI:
    """Test suite for versioning API endpoints."""

    @pytest.fixture
    async def sample_dataset_metadata(self, setup_database, mock_user_id: str) -> DatasetMetadata:
        """Create a sample dataset metadata for testing."""
        dataset_id = str(uuid.uuid4())
        metadata = DatasetMetadata(
            user_id=mock_user_id,
            dataset_id=dataset_id,
            filename="test_dataset.csv",
            original_filename="test_dataset.csv",
            file_type="csv",
            file_path=f"datasets/{mock_user_id}/{dataset_id}/test_dataset.csv",
            s3_url=f"s3://test-bucket/datasets/{mock_user_id}/{dataset_id}/test_dataset.csv",
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
                    unique_values=100,
                    missing_values=0
                ),
                SchemaField(
                    field_name="category",
                    field_type="categorical",
                    inferred_dtype="object",
                    unique_values=3,
                    missing_values=0
                ),
            ]
        )
        await metadata.insert()
        return metadata

    @pytest.fixture
    async def base_version(
        self,
        setup_database,
        sample_dataset_metadata: DatasetMetadata,
        mock_user_id: str
    ) -> DatasetVersion:
        """Create a base version for testing."""
        file_content = b"id,value,category\n1,10.5,A\n2,20.3,B"
        version = await versioning_service.create_base_version(
            dataset_metadata=sample_dataset_metadata,
            file_content=file_content,
            user_id=mock_user_id,
            description="Initial upload"
        )
        return version

    @pytest.fixture
    async def child_version(
        self,
        setup_database,
        base_version: DatasetVersion,
        sample_dataset_metadata: DatasetMetadata,
        mock_user_id: str
    ) -> DatasetVersion:
        """Create a child version (transformation) for testing."""
        transformed_content = b"id,value,category\n1,10.5,A\n2,20.3,B\n3,30.1,C"
        transformation_steps = [
            {
                "step_type": "feature_engineering",
                "parameters": {"method": "add_row"},
                "affected_columns": ["id", "value", "category"],
                "rows_affected": 1,
                "execution_time": 0.5
            }
        ]

        # Update metadata for transformed dataset
        sample_dataset_metadata.num_rows = 101

        version, lineage = await versioning_service.create_transformation_version(
            parent_version_id=base_version.version_id,
            transformed_content=transformed_content,
            transformation_steps=transformation_steps,
            dataset_metadata=sample_dataset_metadata,
            user_id=mock_user_id,
            description="Added new row"
        )
        return version

    # Test GET /datasets/{id}/versions - List all versions
    @pytest.mark.asyncio
    async def test_list_versions_success(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        child_version: DatasetVersion
    ):
        """Test listing all versions for a dataset."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{base_version.dataset_id}/versions"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["versions"]) == 2

        # Verify versions are sorted by version_number (descending)
        assert data["versions"][0]["version_number"] > data["versions"][1]["version_number"]

    @pytest.mark.asyncio
    async def test_list_versions_with_pagination(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        child_version: DatasetVersion
    ):
        """Test listing versions with pagination parameters."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{base_version.dataset_id}/versions?limit=1&skip=0"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert len(data["versions"]) == 1
        assert data["total"] == 2
        assert data["limit"] == 1
        assert data["skip"] == 0

    @pytest.mark.asyncio
    async def test_list_versions_nonexistent_dataset(
        self,
        async_authorized_client: AsyncClient
    ):
        """Test listing versions for nonexistent dataset returns empty list."""
        # ACT
        nonexistent_id = str(uuid.uuid4())
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{nonexistent_id}/versions"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["versions"]) == 0

    # Test POST /datasets/{id}/versions - Create new version
    @pytest.mark.asyncio
    async def test_create_version_success(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        mock_user_id: str
    ):
        """Test creating a new version successfully."""
        # ARRANGE
        request_data = {
            "description": "Test transformation",
            "tags": ["test", "transformation"],
            "transformation_steps": [
                {
                    "step_type": "scale",
                    "parameters": {"method": "standard"},
                    "affected_columns": ["value"],
                    "execution_time": 0.3
                }
            ]
        }

        # ACT
        response = await async_authorized_client.post(
            f"/api/v1/datasets/{base_version.dataset_id}/versions",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 201
        data = response.json()
        assert "version" in data
        assert "lineage" in data
        assert data["version"]["description"] == "Test transformation"
        assert data["version"]["version_number"] == 2
        assert len(data["version"]["tags"]) == 2

    @pytest.mark.asyncio
    async def test_create_version_without_transformation_steps(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion
    ):
        """Test creating version without transformation steps."""
        # ARRANGE
        request_data = {
            "description": "Manual version save"
        }

        # ACT
        response = await async_authorized_client.post(
            f"/api/v1/datasets/{base_version.dataset_id}/versions",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 201
        data = response.json()
        assert data["version"]["description"] == "Manual version save"

    @pytest.mark.asyncio
    async def test_create_version_nonexistent_dataset(
        self,
        async_authorized_client: AsyncClient
    ):
        """Test creating version for nonexistent dataset fails."""
        # ACT
        nonexistent_id = str(uuid.uuid4())
        response = await async_authorized_client.post(
            f"/api/v1/datasets/{nonexistent_id}/versions",
            json={"description": "Test"}
        )

        # ASSERT
        assert response.status_code == 404

    # Test GET /versions/{version_id} - Retrieve specific version
    @pytest.mark.asyncio
    async def test_get_version_success(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion
    ):
        """Test retrieving a specific version by ID."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/versions/{base_version.version_id}"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["version_id"] == base_version.version_id
        assert data["version_number"] == 1
        assert data["is_base_version"] is True
        # Access count should be incremented
        assert data["access_count"] >= 1

    @pytest.mark.asyncio
    async def test_get_version_increments_access_count(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion
    ):
        """Test that retrieving a version increments access count."""
        # ARRANGE
        initial_count = base_version.access_count

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/versions/{base_version.version_id}"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["access_count"] > initial_count

    @pytest.mark.asyncio
    async def test_get_version_not_found(
        self,
        async_authorized_client: AsyncClient
    ):
        """Test retrieving nonexistent version returns 404."""
        # ACT
        nonexistent_id = str(uuid.uuid4())
        response = await async_authorized_client.get(
            f"/api/v1/versions/{nonexistent_id}"
        )

        # ASSERT
        assert response.status_code == 404

    # Test GET /versions/{version_id}/lineage - Get lineage chain
    @pytest.mark.asyncio
    async def test_get_lineage_success(
        self,
        async_authorized_client: AsyncClient,
        child_version: DatasetVersion
    ):
        """Test retrieving lineage chain for a version."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/versions/{child_version.version_id}/lineage"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert "lineage_chain" in data
        assert len(data["lineage_chain"]) == 1
        assert data["lineage_chain"][0]["child_version_id"] == child_version.version_id

    @pytest.mark.asyncio
    async def test_get_lineage_base_version(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion
    ):
        """Test retrieving lineage for base version returns empty list."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/versions/{base_version.version_id}/lineage"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert len(data["lineage_chain"]) == 0

    @pytest.mark.asyncio
    async def test_get_lineage_not_found(
        self,
        async_authorized_client: AsyncClient
    ):
        """Test retrieving lineage for nonexistent version returns 404."""
        # ACT
        nonexistent_id = str(uuid.uuid4())
        response = await async_authorized_client.get(
            f"/api/v1/versions/{nonexistent_id}/lineage"
        )

        # ASSERT
        assert response.status_code == 404

    # Test POST /versions/compare - Compare two versions
    @pytest.mark.asyncio
    async def test_compare_versions_success(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        child_version: DatasetVersion
    ):
        """Test comparing two versions successfully."""
        # ARRANGE
        request_data = {
            "version1_id": base_version.version_id,
            "version2_id": child_version.version_id
        }

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/versions/compare",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["version1_id"] == base_version.version_id
        assert data["version2_id"] == child_version.version_id
        assert "rows_diff" in data
        assert "columns_diff" in data
        assert "transformation_count" in data

    @pytest.mark.asyncio
    async def test_compare_versions_same_version(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion
    ):
        """Test comparing version with itself."""
        # ARRANGE
        request_data = {
            "version1_id": base_version.version_id,
            "version2_id": base_version.version_id
        }

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/versions/compare",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["rows_diff"] == 0
        assert data["columns_diff"] == 0
        assert data["content_similarity"] == 100.0

    @pytest.mark.asyncio
    async def test_compare_versions_different_datasets(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        sample_dataset_metadata: DatasetMetadata,
        mock_user_id: str
    ):
        """Test comparing versions from different datasets fails."""
        # ARRANGE - create another dataset and version
        other_metadata = DatasetMetadata(
            user_id=mock_user_id,
            dataset_id=str(uuid.uuid4()),
            filename="other.csv",
            original_filename="other.csv",
            file_type="csv",
            file_path="other.csv",
            s3_url="s3://test/other.csv",
            num_rows=50,
            num_columns=2,
            columns=["a", "b"],
            data_schema=[
                SchemaField(
                    field_name="a",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=50,
                    missing_values=0
                ),
                SchemaField(
                    field_name="b",
                    field_type="numeric",
                    inferred_dtype="float64",
                    unique_values=50,
                    missing_values=0
                ),
            ]
        )
        await other_metadata.insert()

        other_version = await versioning_service.create_base_version(
            dataset_metadata=other_metadata,
            file_content=b"a,b\n1,2",
            user_id=mock_user_id
        )

        request_data = {
            "version1_id": base_version.version_id,
            "version2_id": other_version.version_id
        }

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/versions/compare",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_compare_versions_not_found(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion
    ):
        """Test comparing with nonexistent version returns 404."""
        # ARRANGE
        request_data = {
            "version1_id": base_version.version_id,
            "version2_id": str(uuid.uuid4())
        }

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/versions/compare",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 404

    # Test DELETE /versions/{version_id} - Soft delete version
    @pytest.mark.asyncio
    async def test_delete_version_success(
        self,
        async_authorized_client: AsyncClient,
        child_version: DatasetVersion
    ):
        """Test soft deleting a version."""
        # ACT
        response = await async_authorized_client.delete(
            f"/api/v1/versions/{child_version.version_id}"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Version deleted successfully"

        # Verify version is actually deleted
        verify_response = await async_authorized_client.get(
            f"/api/v1/versions/{child_version.version_id}"
        )
        assert verify_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_base_version_fails(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion
    ):
        """Test that deleting base version is not allowed."""
        # ACT
        response = await async_authorized_client.delete(
            f"/api/v1/versions/{base_version.version_id}"
        )

        # ASSERT
        assert response.status_code == 400
        data = response.json()
        assert "base version" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_pinned_version_fails(
        self,
        async_authorized_client: AsyncClient,
        child_version: DatasetVersion
    ):
        """Test that deleting pinned version is not allowed."""
        # ARRANGE - Pin the version
        await versioning_service.pin_version(child_version.version_id)

        # ACT
        response = await async_authorized_client.delete(
            f"/api/v1/versions/{child_version.version_id}"
        )

        # ASSERT
        assert response.status_code == 400
        data = response.json()
        assert "pinned" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_version_not_found(
        self,
        async_authorized_client: AsyncClient
    ):
        """Test deleting nonexistent version returns 404."""
        # ACT
        nonexistent_id = str(uuid.uuid4())
        response = await async_authorized_client.delete(
            f"/api/v1/versions/{nonexistent_id}"
        )

        # ASSERT
        assert response.status_code == 404

    # Test PATCH /versions/{version_id}/pin - Pin/Unpin version
    @pytest.mark.asyncio
    async def test_pin_version_success(
        self,
        async_authorized_client: AsyncClient,
        child_version: DatasetVersion
    ):
        """Test pinning a version."""
        # ACT
        response = await async_authorized_client.patch(
            f"/api/v1/versions/{child_version.version_id}/pin",
            json={"pinned": True}
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["is_pinned"] is True

    @pytest.mark.asyncio
    async def test_unpin_version_success(
        self,
        async_authorized_client: AsyncClient,
        child_version: DatasetVersion
    ):
        """Test unpinning a version."""
        # ARRANGE - First pin the version
        await versioning_service.pin_version(child_version.version_id)

        # ACT
        response = await async_authorized_client.patch(
            f"/api/v1/versions/{child_version.version_id}/pin",
            json={"pinned": False}
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["is_pinned"] is False

    @pytest.mark.asyncio
    async def test_pin_version_not_found(
        self,
        async_authorized_client: AsyncClient
    ):
        """Test pinning nonexistent version returns 404."""
        # ACT
        nonexistent_id = str(uuid.uuid4())
        response = await async_authorized_client.patch(
            f"/api/v1/versions/{nonexistent_id}/pin",
            json={"pinned": True}
        )

        # ASSERT
        assert response.status_code == 404
