"""
Test suite for Data Versioning API endpoints.

Following TDD methodology - these tests are written BEFORE implementation.
Tests cover all version API endpoints with various scenarios and edge cases.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.dataset import DatasetMetadata, SchemaField
from app.models.version import (
    DatasetVersion,
    TransformationLineage,
    TransformationStep,
)
from app.services.exceptions import NotFoundError
from app.services.versioning_service import versioning_service

OTHER_USER = "other_user_446"


def make_version(dataset_id: str, version_number: int, user_id: str) -> DatasetVersion:
    """Build an unsaved DatasetVersion — enough fields to insert, nothing more."""
    return DatasetVersion(
        version_id=str(uuid.uuid4()),
        dataset_id=dataset_id,
        version_number=version_number,
        user_id=user_id,
        content_hash=f"hash-{user_id}-{version_number}",
        file_size=123,
        file_path=f"datasets/{user_id}/{dataset_id}/v{version_number}.csv",
        s3_url=f"s3://test-bucket/datasets/{user_id}/{dataset_id}/v{version_number}.csv",
        num_rows=10,
        num_columns=1,
        columns=["id"],
        schema_hash=f"schema-{version_number}",
        created_by=user_id,
    )


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
        mock_user_id: str,
        mock_s3_client
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
        mock_user_id: str,
        mock_s3_client
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

    # Test GET /datasets/{id}/quality-trend (issue #102, AC3)
    @pytest.mark.asyncio
    async def test_quality_trend_with_lineage(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        sample_dataset_metadata: DatasetMetadata,
        mock_user_id: str,
        mock_s3_client,
    ):
        """Trend endpoint projects per-version 0-100 quality scores."""
        steps = [{
            "step_type": "fill_missing", "parameters": {}, "affected_columns": ["value"],
            "rows_affected": 0, "execution_time": 0.1
        }]
        sample_dataset_metadata.num_rows = 102
        await versioning_service.create_transformation_version(
            parent_version_id=base_version.version_id,
            transformed_content=b"id,value,category\n1,10.5,A\n2,20.3,B\n3,5,C",
            transformation_steps=steps,
            dataset_metadata=sample_dataset_metadata,
            user_id=mock_user_id,
            description="Filled missing",
            quality_before={"score_0_100": 60.0},
            quality_after={"score_0_100": 80.0},
        )

        response = await async_authorized_client.get(
            f"/api/v1/datasets/{base_version.dataset_id}/quality-trend"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == base_version.dataset_id
        assert len(data["points"]) == 1
        point = data["points"][0]
        assert point["score_before"] == 60.0
        assert point["score_after"] == 80.0
        assert point["improvement"] == 20.0
        assert "fill_missing" in point["transformation"]
        assert data["overall_improvement"] == 20.0
        assert data["best_score"] == 80.0
        assert data["worst_score"] == 60.0

    @pytest.mark.asyncio
    async def test_quality_trend_empty_when_no_transformations(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
    ):
        """A dataset with only a base version has an empty trend, not a 500."""
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{base_version.dataset_id}/quality-trend"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["points"] == []
        assert data["overall_improvement"] is None

    @pytest.mark.asyncio
    async def test_quality_trend_unknown_dataset_404(
        self,
        async_authorized_client: AsyncClient,
    ):
        """Unknown/foreign dataset -> 404."""
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{uuid.uuid4()}/quality-trend"
        )
        assert response.status_code == 404

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
        """Test listing versions for nonexistent dataset returns 404.

        Same answer as a dataset owned by another tenant, so the pair is not an
        existence oracle (issue #446).
        """
        # ACT
        nonexistent_id = str(uuid.uuid4())
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{nonexistent_id}/versions"
        )

        # ASSERT
        assert response.status_code == 404

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
        # Note: Due to content deduplication, this returns the existing version (v1)
        # with updated description rather than creating a new version (v2)
        assert data["version"]["version_number"] == 1
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

    # Test GET /datasets/{id}/versions - Tenant isolation (issue #446, P0.3)
    #
    # The endpoint used to accept a client-supplied `user_id` query parameter and
    # hand it straight to the service, while the authenticated `current_user_id`
    # went unused; omitting it applied no owner filter at all.

    @pytest.fixture
    async def foreign_dataset_with_versions(self, setup_database) -> DatasetMetadata:
        """A dataset plus two versions owned by someone other than the test user."""
        dataset_id = str(uuid.uuid4())
        metadata = DatasetMetadata(
            user_id=OTHER_USER,
            dataset_id=dataset_id,
            filename="foreign.csv",
            original_filename="foreign.csv",
            file_type="csv",
            file_path=f"datasets/{OTHER_USER}/{dataset_id}/foreign.csv",
            s3_url=f"s3://test-bucket/datasets/{OTHER_USER}/{dataset_id}/foreign.csv",
            num_rows=10,
            num_columns=1,
            columns=["id"],
            data_schema=[],
        )
        await metadata.insert()

        for version_number in (1, 2):
            await make_version(dataset_id, version_number, OTHER_USER).insert()

        return metadata

    @pytest.mark.asyncio
    async def test_list_versions_of_another_tenant_returns_404(
        self,
        async_authorized_client: AsyncClient,
        foreign_dataset_with_versions: DatasetMetadata,
    ):
        """Tenant A gets 404 — not 403, which would confirm the dataset exists."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{foreign_dataset_with_versions.dataset_id}/versions"
        )

        # ASSERT
        assert response.status_code == 404
        assert OTHER_USER not in response.text

    @pytest.mark.asyncio
    async def test_list_versions_user_id_param_cannot_widen_access(
        self,
        async_authorized_client: AsyncClient,
        foreign_dataset_with_versions: DatasetMetadata,
    ):
        """Passing ?user_id=<victim> does not change the result."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{foreign_dataset_with_versions.dataset_id}/versions",
            params={"user_id": OTHER_USER},
        )

        # ASSERT
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_versions_user_id_param_is_inert_on_own_dataset(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
    ):
        """The parameter is gone from the signature, so supplying it is a no-op."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{base_version.dataset_id}/versions",
            params={"user_id": OTHER_USER},
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert [v["user_id"] for v in data["versions"]] == ["test_user_123"]

    @pytest.mark.asyncio
    async def test_list_versions_total_count_is_scoped_to_session_user(
        self,
        async_authorized_client: AsyncClient,
        sample_dataset_metadata: DatasetMetadata,
        base_version: DatasetVersion,
    ):
        """A foreign version sharing the dataset_id must not inflate `total`."""
        # ARRANGE
        await make_version(
            sample_dataset_metadata.dataset_id, 99, OTHER_USER
        ).insert()

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{sample_dataset_metadata.dataset_id}/versions"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["versions"]) == 1

    @pytest.mark.asyncio
    async def test_list_versions_unknown_dataset_matches_foreign_dataset(
        self,
        async_authorized_client: AsyncClient,
        foreign_dataset_with_versions: DatasetMetadata,
    ):
        """No existence oracle: unknown and foreign answer identically."""
        # ACT
        unknown = await async_authorized_client.get(
            f"/api/v1/datasets/{uuid.uuid4()}/versions"
        )
        foreign = await async_authorized_client.get(
            f"/api/v1/datasets/{foreign_dataset_with_versions.dataset_id}/versions"
        )

        # ASSERT
        assert unknown.status_code == 404
        assert foreign.status_code == 404
        assert unknown.json()["detail"].endswith("not found")
        assert foreign.json()["detail"].endswith("not found")

    # Test POST /datasets/{id}/versions - Tenant isolation (issue #447, P0.4)
    #
    # The handler read `DatasetMetadata` and the latest `DatasetVersion` on
    # `dataset_id` alone, then wrote the copied content into a version owned by
    # `current_user_id` — exfiltrating the victim's data into the attacker's
    # account, where legitimately-scoped endpoints would then serve it back.

    @pytest.mark.asyncio
    async def test_create_version_against_another_tenant_returns_404(
        self,
        async_authorized_client: AsyncClient,
        foreign_dataset_with_versions: DatasetMetadata,
        mock_s3_client,
    ):
        """Tenant A cannot create a version against tenant B's dataset."""
        # ACT
        response = await async_authorized_client.post(
            f"/api/v1/datasets/{foreign_dataset_with_versions.dataset_id}/versions",
            json={"description": "exfiltration attempt", "transformation_steps": []},
        )

        # ASSERT
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_version_against_another_tenant_writes_nothing(
        self,
        async_authorized_client: AsyncClient,
        foreign_dataset_with_versions: DatasetMetadata,
        mock_user_id: str,
        mock_s3_client,
    ):
        """The copy must not happen — a status-only check would pass against a
        variant that exfiltrates and then 500s."""
        # ARRANGE
        dataset_id = foreign_dataset_with_versions.dataset_id
        before = await DatasetVersion.find(
            DatasetVersion.dataset_id == dataset_id
        ).count()

        # ACT
        await async_authorized_client.post(
            f"/api/v1/datasets/{dataset_id}/versions",
            json={"description": "exfiltration attempt", "transformation_steps": []},
        )

        # ASSERT — nothing created, and nothing landed in the caller's name
        assert await DatasetVersion.find(
            DatasetVersion.dataset_id == dataset_id
        ).count() == before
        assert await DatasetVersion.find(
            DatasetVersion.user_id == mock_user_id
        ).count() == 0

    @pytest.mark.asyncio
    async def test_create_version_dedup_never_matches_another_tenants_row(
        self,
        async_authorized_client: AsyncClient,
        sample_dataset_metadata: DatasetMetadata,
        mock_user_id: str,
        mock_s3_client,
    ):
        """Content dedup must not reach across tenants (found reviewing #447).

        `create_transformation_version` looked up an existing version by
        `(dataset_id, content_hash)` with no owner predicate. A foreign row
        matching both would be returned in the 201 body — leaking the victim's
        `user_id`, `file_path` and `s3_url` — and have the caller's description
        written onto it.
        """
        # ARRANGE: the caller's own base version holds content that does NOT
        # hash to what the transformation will produce, so the planted foreign
        # row is the only dedup candidate. That makes the match deterministic.
        base = await versioning_service.create_base_version(
            dataset_metadata=sample_dataset_metadata,
            file_content=b"col\n1",
            user_id=mock_user_id,
            description="Initial upload",
        )
        transformed_hash = DatasetVersion.compute_content_hash(
            mock_s3_client.get_object()["Body"].read()
        )
        assert base.content_hash != transformed_hash

        foreign = make_version(sample_dataset_metadata.dataset_id, 50, OTHER_USER)
        foreign.content_hash = transformed_hash
        foreign.description = "victim's own description"
        await foreign.insert()

        # ACT
        response = await async_authorized_client.post(
            f"/api/v1/datasets/{sample_dataset_metadata.dataset_id}/versions",
            json={"description": "attacker text", "transformation_steps": []},
        )

        # ASSERT: the foreign row is neither returned nor written to
        assert response.status_code == 201
        assert response.json()["version"]["user_id"] == mock_user_id
        assert response.json()["version"]["version_id"] != foreign.version_id

        reloaded = await DatasetVersion.find_one(
            DatasetVersion.version_id == foreign.version_id
        )
        assert reloaded.description == "victim's own description"

    # Test DELETE /versions/{id} - Tenant isolation (issue #448, P0.5)
    #
    # The handler looked the version up by id alone and called `version.delete()`
    # — a permanent Beanie delete — with `current_user_id` present only in the
    # signature. Any authenticated user could destroy any tenant's version.

    @pytest.mark.asyncio
    async def test_delete_version_of_another_tenant_returns_404(
        self,
        async_authorized_client: AsyncClient,
        foreign_dataset_with_versions: DatasetMetadata,
    ):
        """Tenant A cannot delete tenant B's version, and B's row survives."""
        # ARRANGE
        victim = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id,
            DatasetVersion.version_number == 2,
        )

        # ACT
        response = await async_authorized_client.delete(
            f"/api/v1/versions/{victim.version_id}"
        )

        # ASSERT — refused, and the document is still there
        assert response.status_code == 404
        assert await DatasetVersion.find_one(
            DatasetVersion.version_id == victim.version_id
        ) is not None

    @pytest.mark.asyncio
    async def test_delete_version_of_another_tenant_is_not_an_existence_oracle(
        self,
        async_authorized_client: AsyncClient,
        foreign_dataset_with_versions: DatasetMetadata,
    ):
        """A foreign *base* version answers 404, not the 400 from the guard below
        the lookup — otherwise 'Cannot delete base version' confirms it exists."""
        # ARRANGE
        victim = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id,
            DatasetVersion.version_number == 1,
        )
        victim.is_base_version = True
        await victim.save()

        # ACT
        response = await async_authorized_client.delete(
            f"/api/v1/versions/{victim.version_id}"
        )

        # ASSERT
        assert response.status_code == 404
        assert "base version" not in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_pinned_version_of_another_tenant_is_not_an_oracle(
        self,
        async_authorized_client: AsyncClient,
        foreign_dataset_with_versions: DatasetMetadata,
    ):
        """Same oracle, other guard: 'Cannot delete pinned version' would also
        confirm the foreign version exists. Symmetric with the base-version case."""
        # ARRANGE
        victim = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id,
            DatasetVersion.version_number == 2,
        )
        victim.is_pinned = True
        await victim.save()

        # ACT
        response = await async_authorized_client.delete(
            f"/api/v1/versions/{victim.version_id}"
        )

        # ASSERT
        assert response.status_code == 404
        assert "pinned" not in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_own_version_still_works(
        self,
        async_authorized_client: AsyncClient,
        sample_dataset_metadata: DatasetMetadata,
        mock_user_id: str,
    ):
        """Regression guard on the owner path."""
        # ARRANGE
        mine = make_version(sample_dataset_metadata.dataset_id, 7, mock_user_id)
        await mine.insert()

        # ACT
        response = await async_authorized_client.delete(
            f"/api/v1/versions/{mine.version_id}"
        )

        # ASSERT
        assert response.status_code == 200
        assert await DatasetVersion.find_one(
            DatasetVersion.version_id == mine.version_id
        ) is None

    # Test GET /versions/{id}/lineage and POST /versions/compare -
    # Tenant isolation (issue #453, P0.10)
    #
    # Both handlers took `current_user_id` as a dependency and used it nowhere but
    # the signature. `get_version_lineage` looked the version up by id alone and
    # returned the whole transformation history; `compare_versions` handed two
    # arbitrary ids straight to the service, leaking two tenants' schemas at once
    # and requiring the caller to own neither.

    @pytest.fixture
    async def foreign_version_with_lineage(
        self,
        foreign_dataset_with_versions: DatasetMetadata,
    ) -> DatasetVersion:
        """Tenant B's v2, carrying a real transformation lineage record.

        The lineage row holds B's column names and row counts — the payload the
        unscoped handler served to anyone who could guess a version id.
        """
        dataset_id = foreign_dataset_with_versions.dataset_id
        parent = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version_number == 1,
        )
        child = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version_number == 2,
        )

        lineage = TransformationLineage(
            lineage_id=str(uuid.uuid4()),
            parent_version_id=parent.version_id,
            child_version_id=child.version_id,
            dataset_id=dataset_id,
            user_id=OTHER_USER,
            transformation_steps=[
                TransformationStep(
                    step_type="filter",
                    parameters={"column": "victim_salary"},
                    affected_columns=["victim_salary"],
                    rows_affected=10,
                )
            ],
            rows_before=10,
            rows_after=10,
            columns_before=2,
            columns_after=1,
        )
        await lineage.insert()

        child.parent_version_id = parent.version_id
        child.transformation_lineage_id = lineage.lineage_id
        await child.save()
        return child

    @pytest.mark.asyncio
    async def test_get_lineage_of_another_tenant_returns_404(
        self,
        async_authorized_client: AsyncClient,
        foreign_version_with_lineage: DatasetVersion,
    ):
        """Tenant A cannot read tenant B's transformation history."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/versions/{foreign_version_with_lineage.version_id}/lineage"
        )

        # ASSERT — refused, and none of B's data appears in the body
        assert response.status_code == 404
        assert OTHER_USER not in response.text
        assert "victim_salary" not in response.text

    @pytest.mark.asyncio
    async def test_get_lineage_unknown_version_matches_foreign_version(
        self,
        async_authorized_client: AsyncClient,
        foreign_version_with_lineage: DatasetVersion,
    ):
        """No existence oracle: unknown and foreign answer identically."""
        # ACT
        unknown = await async_authorized_client.get(
            f"/api/v1/versions/{uuid.uuid4()}/lineage"
        )
        foreign = await async_authorized_client.get(
            f"/api/v1/versions/{foreign_version_with_lineage.version_id}/lineage"
        )

        # ASSERT
        assert unknown.status_code == 404
        assert foreign.status_code == 404
        assert unknown.json()["detail"].endswith("not found")
        assert foreign.json()["detail"].endswith("not found")

    @pytest.mark.asyncio
    async def test_compare_two_of_another_tenants_versions_returns_404(
        self,
        async_authorized_client: AsyncClient,
        foreign_dataset_with_versions: DatasetMetadata,
    ):
        """Tenant A cannot compare two versions it does not own."""
        # ARRANGE
        versions = await DatasetVersion.find(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id
        ).sort("+version_number").to_list()

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/versions/compare",
            json={
                "version1_id": versions[0].version_id,
                "version2_id": versions[1].version_id,
            },
        )

        # ASSERT
        assert response.status_code == 404
        assert "hash-" not in response.text

    @pytest.mark.asyncio
    async def test_compare_own_version_against_another_tenants_returns_404(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        foreign_dataset_with_versions: DatasetMetadata,
    ):
        """Owning one side is not enough — the other side is still a foreign read."""
        # ARRANGE
        foreign = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id,
            DatasetVersion.version_number == 1,
        )

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/versions/compare",
            json={
                "version1_id": base_version.version_id,
                "version2_id": foreign.version_id,
            },
        )

        # ASSERT — 404, not the 400 "must be from the same dataset" the service
        # would raise after loading both, which would confirm the foreign version
        # exists and belongs to a different dataset.
        assert response.status_code == 404
        assert "same dataset" not in response.text

    @pytest.mark.asyncio
    async def test_compare_checks_version1_independently_of_version2(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        foreign_dataset_with_versions: DatasetMetadata,
    ):
        """Same pair, swapped: checking only one id still leaks the other."""
        # ARRANGE
        foreign = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id,
            DatasetVersion.version_number == 1,
        )

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/versions/compare",
            json={
                "version1_id": foreign.version_id,
                "version2_id": base_version.version_id,
            },
        )

        # ASSERT
        assert response.status_code == 404
        assert "same dataset" not in response.text

    @pytest.mark.asyncio
    async def test_lineage_chain_never_crosses_into_another_tenant(
        self,
        async_authorized_client: AsyncClient,
        child_version: DatasetVersion,
        foreign_dataset_with_versions: DatasetMetadata,
        mock_user_id: str,
    ):
        """The chain walk follows `parent_version_id` — it must stay in-tenant.

        Owning the entry version only proves the first hop; the walk itself has
        to be scoped or a parent pointing at another tenant's version drags that
        tenant's lineage into the response.
        """
        # ARRANGE — the caller's own version is made to point at B's version as
        # its parent, and B's version carries a lineage record of its own.
        foreign_parent = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id,
            DatasetVersion.version_number == 1,
        )
        foreign_lineage = TransformationLineage(
            lineage_id=str(uuid.uuid4()),
            parent_version_id=str(uuid.uuid4()),
            child_version_id=foreign_parent.version_id,
            dataset_id=foreign_dataset_with_versions.dataset_id,
            user_id=OTHER_USER,
            transformation_steps=[],
            rows_before=10,
            rows_after=10,
            columns_before=1,
            columns_after=1,
        )
        await foreign_lineage.insert()
        foreign_parent.transformation_lineage_id = foreign_lineage.lineage_id
        await foreign_parent.save()

        mine = await DatasetVersion.find_one(
            DatasetVersion.version_id == child_version.version_id
        )
        mine.parent_version_id = foreign_parent.version_id
        await mine.save()

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/versions/{child_version.version_id}/lineage"
        )

        # ASSERT — the caller's own transformation, and nothing of B's
        assert response.status_code == 200
        returned = response.json()["lineage_chain"]
        assert [entry["lineage_id"] for entry in returned] != []
        assert foreign_lineage.lineage_id not in [
            entry["lineage_id"] for entry in returned
        ]
        assert OTHER_USER not in response.text

    @pytest.mark.asyncio
    async def test_lineage_and_compare_still_work_for_the_owner(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        child_version: DatasetVersion,
    ):
        """Regression guard: the owner path is untouched by the scoping."""
        # ACT
        lineage = await async_authorized_client.get(
            f"/api/v1/versions/{child_version.version_id}/lineage"
        )
        compare = await async_authorized_client.post(
            "/api/v1/versions/compare",
            json={
                "version1_id": base_version.version_id,
                "version2_id": child_version.version_id,
            },
        )

        # ASSERT
        assert lineage.status_code == 200
        assert len(lineage.json()["lineage_chain"]) == 1
        assert compare.status_code == 200
        assert compare.json()["version1_id"] == base_version.version_id

    # Cross-tenant leaks in the lineage *walk* itself (issue #453, found in the
    # pre-PR cross-family review of the first fix).
    #
    # Scoping the walk through `versioning_service.get_version(user_id=...)` was
    # not enough: that check joins to `DatasetMetadata` and reads
    # `if dataset and dataset.user_id != user_id`, so a version whose dataset row
    # is gone passes it. And `compare_versions` never threaded the caller down to
    # `_find_lineage_path`, leaving both of its walks unscoped.

    @pytest.fixture
    async def foreign_parent_of_my_version(
        self,
        child_version: DatasetVersion,
        foreign_dataset_with_versions: DatasetMetadata,
    ) -> TransformationLineage:
        """Point the caller's own version at an *orphaned* foreign parent.

        The foreign dataset row is deleted, so an ownership check that joins
        through `DatasetMetadata` finds nothing and lets the version through.
        Returns tenant B's lineage record — the payload that must not appear.
        """
        foreign_parent = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id,
            DatasetVersion.version_number == 1,
        )
        foreign_lineage = TransformationLineage(
            lineage_id=str(uuid.uuid4()),
            parent_version_id=str(uuid.uuid4()),
            child_version_id=foreign_parent.version_id,
            dataset_id=foreign_dataset_with_versions.dataset_id,
            user_id=OTHER_USER,
            transformation_steps=[
                TransformationStep(
                    step_type="filter",
                    parameters={"column": "victim_salary"},
                    affected_columns=["victim_salary"],
                    rows_affected=10,
                )
            ],
            rows_before=10,
            rows_after=10,
            columns_before=1,
            columns_after=1,
        )
        await foreign_lineage.insert()
        foreign_parent.transformation_lineage_id = foreign_lineage.lineage_id
        await foreign_parent.save()

        mine = await DatasetVersion.find_one(
            DatasetVersion.version_id == child_version.version_id
        )
        mine.parent_version_id = foreign_parent.version_id
        await mine.save()

        # The orphan state: B's version survives, B's dataset row does not.
        await foreign_dataset_with_versions.delete()
        return foreign_lineage

    @pytest.mark.asyncio
    async def test_lineage_walk_does_not_fall_open_on_an_orphaned_version(
        self,
        async_authorized_client: AsyncClient,
        child_version: DatasetVersion,
        foreign_parent_of_my_version: TransformationLineage,
    ):
        """A missing dataset row must not turn the per-hop check into a no-op."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/versions/{child_version.version_id}/lineage"
        )

        # ASSERT
        assert response.status_code == 200
        assert foreign_parent_of_my_version.lineage_id not in [
            entry["lineage_id"] for entry in response.json()["lineage_chain"]
        ]
        assert "victim_salary" not in response.text

    @pytest.mark.asyncio
    async def test_compare_lineage_path_does_not_cross_tenants(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        child_version: DatasetVersion,
        foreign_parent_of_my_version: TransformationLineage,
    ):
        """Both compare endpoints are owned, but its walks were still unscoped.

        `compare_versions` -> `_find_lineage_path` -> `get_lineage_chain` ran with
        no caller, so B's lineage ids reached `lineage_path` and B's
        transformations were counted in `transformation_count`.
        """
        # ACT
        response = await async_authorized_client.post(
            "/api/v1/versions/compare",
            json={
                "version1_id": base_version.version_id,
                "version2_id": child_version.version_id,
            },
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert foreign_parent_of_my_version.lineage_id not in data["lineage_path"]
        assert OTHER_USER not in response.text

    @pytest.mark.asyncio
    async def test_lineage_is_not_truncated_when_the_dataset_row_is_gone(
        self,
        async_authorized_client: AsyncClient,
        child_version: DatasetVersion,
        sample_dataset_metadata: DatasetMetadata,
    ):
        """The mirror of the leak: the owner must still get their own chain.

        Authorizing the walk on `DatasetMetadata` rather than on the version's
        own `user_id` answers 200 with an empty chain — a silent wrong answer —
        whenever the dataset row is missing or its owner has drifted.
        """
        # ARRANGE
        await sample_dataset_metadata.delete()

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/versions/{child_version.version_id}/lineage"
        )

        # ASSERT
        assert response.status_code == 200
        assert len(response.json()["lineage_chain"]) == 1

    @pytest.mark.asyncio
    async def test_service_compare_versions_refuses_a_foreign_version(
        self,
        setup_database,
        base_version: DatasetVersion,
        foreign_dataset_with_versions: DatasetMetadata,
        mock_user_id: str,
    ):
        """`compare_versions` defends itself, not just via the route.

        The route's two `require_owned_version` calls are what protect the API
        today, but the dimensional and schema fields in the response come from
        versions the service resolved on its own. Called with a `user_id` from
        anywhere else, it must refuse rather than trust its caller to have
        checked (raised in review of this fix).
        """
        # ARRANGE
        foreign = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id,
            DatasetVersion.version_number == 1,
        )

        # ACT / ASSERT
        with pytest.raises(NotFoundError):
            await versioning_service.compare_versions(
                version1_id=base_version.version_id,
                version2_id=foreign.version_id,
                user_id=mock_user_id,
            )

    # The same fall-open predicate on the sibling routes (issue #453, raised by
    # the post-PR bot review).
    #
    # `GET /versions/{id}` and `PATCH /versions/{id}/pin` authorize through
    # `versioning_service.get_version(user_id=...)`, whose check reads
    # `if dataset and dataset.user_id != user_id` — so a version whose dataset
    # row is gone skipped the check entirely. On the pin route that is a
    # *mutation* of another tenant's row, not just a read. The orphan state is
    # ordinary: deleting a dataset produces it.

    @pytest.fixture
    async def orphaned_foreign_version(
        self,
        foreign_dataset_with_versions: DatasetMetadata,
    ) -> DatasetVersion:
        """Tenant B's version, with tenant B's dataset row deleted."""
        version = await DatasetVersion.find_one(
            DatasetVersion.dataset_id == foreign_dataset_with_versions.dataset_id,
            DatasetVersion.version_number == 2,
        )
        await foreign_dataset_with_versions.delete()
        return version

    @pytest.mark.asyncio
    async def test_get_orphaned_version_of_another_tenant_returns_404(
        self,
        async_authorized_client: AsyncClient,
        orphaned_foreign_version: DatasetVersion,
    ):
        """A missing dataset row must not open up the single-version read."""
        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/versions/{orphaned_foreign_version.version_id}"
        )

        # ASSERT
        assert response.status_code == 404
        assert OTHER_USER not in response.text

    @pytest.mark.asyncio
    async def test_pinning_an_orphaned_version_of_another_tenant_is_refused(
        self,
        async_authorized_client: AsyncClient,
        orphaned_foreign_version: DatasetVersion,
    ):
        """The mutation case: refused, and tenant B's row is left untouched."""
        # ACT
        response = await async_authorized_client.patch(
            f"/api/v1/versions/{orphaned_foreign_version.version_id}/pin",
            json={"pinned": True},
        )

        # ASSERT
        assert response.status_code == 404
        reloaded = await DatasetVersion.find_one(
            DatasetVersion.version_id == orphaned_foreign_version.version_id
        )
        assert reloaded.is_pinned is False

    @pytest.mark.asyncio
    async def test_unpinning_an_orphaned_version_of_another_tenant_is_refused(
        self,
        async_authorized_client: AsyncClient,
        orphaned_foreign_version: DatasetVersion,
    ):
        """Symmetric with pin — unpin runs through the same check."""
        # ARRANGE
        orphaned_foreign_version.is_pinned = True
        await orphaned_foreign_version.save()

        # ACT
        response = await async_authorized_client.patch(
            f"/api/v1/versions/{orphaned_foreign_version.version_id}/pin",
            json={"pinned": False},
        )

        # ASSERT
        assert response.status_code == 404
        reloaded = await DatasetVersion.find_one(
            DatasetVersion.version_id == orphaned_foreign_version.version_id
        )
        assert reloaded.is_pinned is True

    @pytest.mark.asyncio
    async def test_owner_can_still_read_and_pin_a_version_with_no_dataset_row(
        self,
        async_authorized_client: AsyncClient,
        base_version: DatasetVersion,
        sample_dataset_metadata: DatasetMetadata,
    ):
        """The mirror: authorizing on the version's own owner must not lock the
        rightful owner out when their dataset row is missing."""
        # ARRANGE
        await sample_dataset_metadata.delete()

        # ACT
        read = await async_authorized_client.get(
            f"/api/v1/versions/{base_version.version_id}"
        )
        pin = await async_authorized_client.patch(
            f"/api/v1/versions/{base_version.version_id}/pin",
            json={"pinned": True},
        )

        # ASSERT
        assert read.status_code == 200
        assert pin.status_code == 200
        assert pin.json()["is_pinned"] is True
