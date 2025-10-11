"""
Tests for versioning service.

Tests version creation, retrieval, lineage tracking, and version management.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
import io

from app.services.versioning_service import VersioningService
from app.models.version import (
    DatasetVersion,
    TransformationLineage,
    TransformationStep
)
from app.models.dataset import DatasetMetadata, SchemaField


@pytest.fixture
def versioning_service():
    """Create versioning service instance."""
    service = VersioningService()
    return service


@pytest.fixture
def mock_dataset_metadata():
    """Create mock dataset metadata."""
    return DatasetMetadata(
        user_id="user1",
        dataset_id="ds1",
        filename="test.csv",
        original_filename="test.csv",
        file_type="csv",
        file_path="datasets/user1/ds1/test.csv",
        s3_url="s3://bucket/datasets/user1/ds1/test.csv",
        file_size=1024,
        num_rows=100,
        num_columns=5,
        columns=["col1", "col2", "col3", "col4", "col5"],
        data_schema=[
            SchemaField(
                field_name="col1",
                field_type="numeric",
                inferred_dtype="int64",
                unique_values=50,
                missing_values=0
            ),
            SchemaField(
                field_name="col2",
                field_type="numeric",
                inferred_dtype="float64",
                unique_values=80,
                missing_values=5
            ),
            SchemaField(
                field_name="col3",
                field_type="text",
                inferred_dtype="object",
                unique_values=100,
                missing_values=0
            ),
            SchemaField(
                field_name="col4",
                field_type="categorical",
                inferred_dtype="object",
                unique_values=3,
                missing_values=0
            ),
            SchemaField(
                field_name="col5",
                field_type="boolean",
                inferred_dtype="bool",
                unique_values=2,
                missing_values=0
            )
        ]
    )


@pytest.fixture
def mock_s3_client():
    """Create mock S3 client."""
    client = MagicMock()
    client.put_object = MagicMock()
    client.get_object = MagicMock()
    client.delete_object = MagicMock()
    return client


class TestVersionCreation:
    """Tests for version creation."""

    @pytest.mark.asyncio
    async def test_create_base_version(self, versioning_service, mock_dataset_metadata, mock_s3_client):
        """Test creating base version for new dataset."""
        versioning_service.s3_client = mock_s3_client
        file_content = b"test,data,content"

        # Mock database queries
        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None  # No existing base version

            with patch.object(DatasetVersion, 'insert', new_callable=AsyncMock) as mock_insert:
                version = await versioning_service.create_base_version(
                    dataset_metadata=mock_dataset_metadata,
                    file_content=file_content,
                    user_id="user1",
                    description="Initial upload"
                )

                assert version.dataset_id == "ds1"
                assert version.version_number == 1
                assert version.user_id == "user1"
                assert version.is_base_version is True
                assert version.num_rows == 100
                assert version.num_columns == 5
                assert len(version.columns) == 5
                assert version.description == "Initial upload"
                assert version.file_size == len(file_content)
                mock_insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_base_version_duplicate_error(self, versioning_service, mock_dataset_metadata):
        """Test creating base version when one already exists."""
        file_content = b"test,data,content"

        # Mock existing base version
        existing_version = MagicMock()
        existing_version.dataset_id = "ds1"
        existing_version.is_base_version = True

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = existing_version

            with pytest.raises(ValueError, match="Base version already exists"):
                await versioning_service.create_base_version(
                    dataset_metadata=mock_dataset_metadata,
                    file_content=file_content,
                    user_id="user1"
                )

    @pytest.mark.asyncio
    async def test_create_transformation_version(
        self,
        versioning_service,
        mock_dataset_metadata,
        mock_s3_client
    ):
        """Test creating version after transformation."""
        versioning_service.s3_client = mock_s3_client
        transformed_content = b"transformed,data"

        # Create parent version
        parent_version = DatasetVersion(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="parent_hash",
            file_size=1024,
            file_path="path/v1",
            s3_url="s3://bucket/path/v1",
            num_rows=100,
            num_columns=5,
            columns=["col1", "col2", "col3", "col4", "col5"],
            schema_hash="schema_hash",
            is_base_version=True,
            created_by="user1"
        )

        transformation_steps = [
            {
                "step_type": "drop_missing",
                "parameters": {"threshold": 0.5},
                "affected_columns": ["col2"],
                "rows_affected": 5,
                "execution_time": 0.5
            }
        ]

        # Update metadata for transformed dataset
        mock_dataset_metadata.num_rows = 95  # 5 rows dropped

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.side_effect = [parent_version, None]  # Parent exists, no duplicate

            with patch.object(DatasetVersion, 'insert', new_callable=AsyncMock):
                with patch.object(DatasetVersion, 'save', new_callable=AsyncMock):
                    with patch.object(TransformationLineage, 'insert', new_callable=AsyncMock):
                        with patch.object(DatasetVersion, 'find') as mock_find_versions:
                            mock_find_versions.return_value.sort.return_value.first_or_none = AsyncMock(
                                return_value=parent_version
                            )

                            version, lineage = await versioning_service.create_transformation_version(
                                parent_version_id="v1",
                                transformed_content=transformed_content,
                                transformation_steps=transformation_steps,
                                dataset_metadata=mock_dataset_metadata,
                                user_id="user1",
                                description="After drop_missing"
                            )

                            assert version.dataset_id == "ds1"
                            assert version.version_number == 2
                            assert version.parent_version_id == "v1"
                            assert version.is_base_version is False
                            assert version.num_rows == 95
                            assert lineage.parent_version_id == "v1"
                            assert lineage.child_version_id == version.version_id
                            assert len(lineage.transformation_steps) == 1

    @pytest.mark.asyncio
    async def test_create_transformation_version_deduplication(
        self,
        versioning_service,
        mock_dataset_metadata,
        mock_s3_client
    ):
        """Test that duplicate content reuses existing version."""
        versioning_service.s3_client = mock_s3_client
        transformed_content = b"transformed,data"

        parent_version = DatasetVersion(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="parent_hash",
            file_size=1024,
            file_path="path/v1",
            s3_url="s3://bucket/path/v1",
            num_rows=100,
            num_columns=5,
            columns=["col1", "col2", "col3", "col4", "col5"],
            schema_hash="schema_hash",
            is_base_version=True,
            created_by="user1"
        )

        # Create existing version with same content
        existing_version = DatasetVersion(
            version_id="v2",
            dataset_id="ds1",
            version_number=2,
            user_id="user1",
            content_hash=DatasetVersion.compute_content_hash(transformed_content),
            file_size=len(transformed_content),
            file_path="path/v2",
            s3_url="s3://bucket/path/v2",
            num_rows=95,
            num_columns=5,
            columns=["col1", "col2", "col3", "col4", "col5"],
            schema_hash="schema_hash",
            created_by="user1"
        )

        transformation_steps = [{"step_type": "drop_missing", "parameters": {}}]

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.side_effect = [parent_version, existing_version]  # Parent + duplicate

            with patch.object(TransformationLineage, 'insert', new_callable=AsyncMock):
                version, lineage = await versioning_service.create_transformation_version(
                    parent_version_id="v1",
                    transformed_content=transformed_content,
                    transformation_steps=transformation_steps,
                    dataset_metadata=mock_dataset_metadata,
                    user_id="user1"
                )

                # Should return existing version
                assert version.version_id == "v2"
                assert lineage.child_version_id == "v2"

    @pytest.mark.asyncio
    async def test_create_transformation_version_parent_not_found(self, versioning_service):
        """Test error when parent version not found."""
        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            with pytest.raises(ValueError, match="Parent version .* not found"):
                await versioning_service.create_transformation_version(
                    parent_version_id="nonexistent",
                    transformed_content=b"data",
                    transformation_steps=[],
                    dataset_metadata=MagicMock(),
                    user_id="user1"
                )


class TestVersionRetrieval:
    """Tests for version retrieval."""

    @pytest.mark.asyncio
    async def test_get_version(self, versioning_service):
        """Test retrieving a version."""
        mock_version = DatasetVersion(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="hash",
            file_size=1024,
            file_path="path",
            s3_url="s3://bucket/path",
            num_rows=100,
            num_columns=5,
            schema_hash="schema",
            created_by="user1"
        )

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_version

            with patch.object(DatasetVersion, 'save', new_callable=AsyncMock):
                version = await versioning_service.get_version("v1", mark_accessed=True)

                assert version.version_id == "v1"
                assert version.access_count == 1  # Should be incremented
                mock_find.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_version_not_found(self, versioning_service):
        """Test retrieving nonexistent version."""
        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            version = await versioning_service.get_version("nonexistent")
            assert version is None

    @pytest.mark.asyncio
    async def test_get_version_without_marking_accessed(self, versioning_service):
        """Test retrieving version without marking as accessed."""
        mock_version = MagicMock()
        mock_version.version_id = "v1"
        mock_version.access_count = 0

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_version

            version = await versioning_service.get_version("v1", mark_accessed=False)

            assert version.access_count == 0  # Should not be incremented
            mock_version.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_version_content(self, versioning_service, mock_s3_client):
        """Test retrieving version file content."""
        versioning_service.s3_client = mock_s3_client

        mock_version = DatasetVersion(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="hash",
            file_size=1024,
            file_path="path/to/file",
            s3_url="s3://bucket/path",
            num_rows=100,
            num_columns=5,
            schema_hash="schema",
            created_by="user1"
        )

        file_content = b"test,data,content"
        mock_response = {'Body': io.BytesIO(file_content)}
        mock_s3_client.get_object.return_value = mock_response

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_version

            with patch.object(DatasetVersion, 'save', new_callable=AsyncMock):
                content = await versioning_service.get_version_content("v1")

                assert content == file_content
                mock_s3_client.get_object.assert_called_once_with(
                    Bucket=versioning_service.bucket_name,
                    Key="path/to/file"
                )

    @pytest.mark.asyncio
    async def test_get_version_content_not_found(self, versioning_service):
        """Test error when version not found."""
        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            with pytest.raises(ValueError, match="Version .* not found"):
                await versioning_service.get_version_content("nonexistent")

    @pytest.mark.asyncio
    async def test_list_versions(self, versioning_service):
        """Test listing versions for a dataset."""
        versions = [
            MagicMock(version_id="v3", version_number=3),
            MagicMock(version_id="v2", version_number=2),
            MagicMock(version_id="v1", version_number=1),
        ]

        mock_query = MagicMock()
        mock_query.find.return_value = mock_query
        mock_query.sort.return_value = mock_query
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=versions)

        with patch.object(DatasetVersion, 'find', return_value=mock_query):
            result = await versioning_service.list_versions(
                dataset_id="ds1",
                user_id="user1",
                limit=50,
                skip=0
            )

            assert len(result) == 3
            assert result[0].version_id == "v3"  # Most recent first


class TestLineageTracking:
    """Tests for lineage tracking."""

    @pytest.mark.asyncio
    async def test_get_lineage_chain(self, versioning_service):
        """Test retrieving complete lineage chain."""
        # Create version chain: v1 -> v2 -> v3
        v1 = DatasetVersion(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="hash1",
            file_size=1024,
            file_path="path1",
            s3_url="s3://bucket/path1",
            num_rows=100,
            num_columns=5,
            schema_hash="schema",
            is_base_version=True,
            created_by="user1"
        )

        v2 = DatasetVersion(
            version_id="v2",
            dataset_id="ds1",
            version_number=2,
            user_id="user1",
            content_hash="hash2",
            file_size=1024,
            file_path="path2",
            s3_url="s3://bucket/path2",
            num_rows=95,
            num_columns=5,
            schema_hash="schema",
            parent_version_id="v1",
            transformation_lineage_id="lin1",
            created_by="user1"
        )

        v3 = DatasetVersion(
            version_id="v3",
            dataset_id="ds1",
            version_number=3,
            user_id="user1",
            content_hash="hash3",
            file_size=1024,
            file_path="path3",
            s3_url="s3://bucket/path3",
            num_rows=90,
            num_columns=5,
            schema_hash="schema",
            parent_version_id="v2",
            transformation_lineage_id="lin2",
            created_by="user1"
        )

        lin1 = TransformationLineage(
            lineage_id="lin1",
            parent_version_id="v1",
            child_version_id="v2",
            dataset_id="ds1",
            user_id="user1",
            rows_before=100,
            rows_after=95,
            columns_before=5,
            columns_after=5
        )

        lin2 = TransformationLineage(
            lineage_id="lin2",
            parent_version_id="v2",
            child_version_id="v3",
            dataset_id="ds1",
            user_id="user1",
            rows_before=95,
            rows_after=90,
            columns_before=5,
            columns_after=5
        )

        async def mock_find_one(query):
            # Simplified mock - in real code would check query conditions
            if hasattr(query, 'version_id'):
                vid = query.version_id
                if vid == "v3":
                    return v3
                elif vid == "v2":
                    return v2
                elif vid == "v1":
                    return v1
            elif hasattr(query, 'lineage_id'):
                lid = query.lineage_id
                if lid == "lin2":
                    return lin2
                elif lid == "lin1":
                    return lin1
            return None

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_dv_find:
            with patch.object(TransformationLineage, 'find_one', new_callable=AsyncMock) as mock_tl_find:
                mock_dv_find.side_effect = lambda *args, **kwargs: mock_find_one(args[0] if args else None)
                mock_tl_find.side_effect = lambda *args, **kwargs: mock_find_one(args[0] if args else None)

                chain = await versioning_service.get_lineage_chain("v3")

                assert len(chain) == 2
                assert chain[0].lineage_id == "lin1"
                assert chain[1].lineage_id == "lin2"


class TestVersionComparison:
    """Tests for version comparison."""

    @pytest.mark.asyncio
    async def test_compare_versions(self, versioning_service):
        """Test comparing two versions."""
        v1 = DatasetVersion(
            version_id="v1",
            dataset_id="ds1",
            version_number=1,
            user_id="user1",
            content_hash="hash1",
            file_size=1024,
            file_path="path1",
            s3_url="s3://bucket/path1",
            num_rows=100,
            num_columns=5,
            columns=["col1", "col2", "col3", "col4", "col5"],
            schema_hash="schema1",
            created_by="user1"
        )

        v2 = DatasetVersion(
            version_id="v2",
            dataset_id="ds1",
            version_number=2,
            user_id="user1",
            content_hash="hash2",
            file_size=1024,
            file_path="path2",
            s3_url="s3://bucket/path2",
            num_rows=95,
            num_columns=6,
            columns=["col1", "col2", "col3", "col4", "col5", "col6"],
            schema_hash="schema2",
            parent_version_id="v1",
            created_by="user1"
        )

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.side_effect = [v1, v2]

            with patch.object(versioning_service, '_find_lineage_path', new_callable=AsyncMock) as mock_path:
                mock_path.return_value = []

                comparison = await versioning_service.compare_versions("v1", "v2")

                assert comparison.version1_id == "v1"
                assert comparison.version2_id == "v2"
                assert comparison.rows_diff == -5  # 95 - 100
                assert comparison.columns_diff == 1  # 6 - 5
                assert "col6" in comparison.columns_added
                assert len(comparison.columns_removed) == 0
                assert comparison.content_similarity == 0.0  # Different hashes

    @pytest.mark.asyncio
    async def test_compare_versions_different_datasets(self, versioning_service):
        """Test error when comparing versions from different datasets."""
        v1 = MagicMock(dataset_id="ds1")
        v2 = MagicMock(dataset_id="ds2")

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.side_effect = [v1, v2]

            with pytest.raises(ValueError, match="must be from the same dataset"):
                await versioning_service.compare_versions("v1", "v2")


class TestVersionManagement:
    """Tests for version management operations."""

    @pytest.mark.asyncio
    async def test_pin_version(self, versioning_service):
        """Test pinning a version."""
        mock_version = MagicMock()
        mock_version.is_pinned = False
        mock_version.save = AsyncMock()

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_version

            version = await versioning_service.pin_version("v1")

            mock_version.pin_version.assert_called_once()
            mock_version.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_unpin_version(self, versioning_service):
        """Test unpinning a version."""
        mock_version = MagicMock()
        mock_version.is_pinned = True
        mock_version.save = AsyncMock()

        with patch.object(DatasetVersion, 'find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_version

            version = await versioning_service.unpin_version("v1")

            mock_version.unpin_version.assert_called_once()
            mock_version.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_versions(self, versioning_service, mock_s3_client):
        """Test cleaning up old versions."""
        versioning_service.s3_client = mock_s3_client

        old_date = datetime.now(timezone.utc) - timedelta(days=60)

        versions = [
            # Keep: recent
            MagicMock(
                version_id="v10",
                is_pinned=False,
                is_base_version=False,
                created_at=datetime.now(timezone.utc),
                used_in_training=[],
                file_path="path10",
                delete=AsyncMock()
            ),
            # Keep: pinned
            MagicMock(
                version_id="v9",
                is_pinned=True,
                is_base_version=False,
                created_at=old_date,
                used_in_training=[],
                file_path="path9",
                delete=AsyncMock()
            ),
            # Keep: base version
            MagicMock(
                version_id="v1",
                is_pinned=False,
                is_base_version=True,
                created_at=old_date,
                used_in_training=[],
                file_path="path1",
                delete=AsyncMock()
            ),
            # Delete: old and unpinned
            MagicMock(
                version_id="v5",
                is_pinned=False,
                is_base_version=False,
                created_at=old_date,
                used_in_training=[],
                file_path="path5",
                delete=AsyncMock()
            ),
        ]

        mock_query = MagicMock()
        mock_query.sort.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=versions)

        with patch.object(DatasetVersion, 'find', return_value=mock_query):
            deleted_count = await versioning_service.cleanup_old_versions(
                dataset_id="ds1",
                retention_days=30,
                keep_count=3
            )

            assert deleted_count == 1
            versions[3].delete.assert_called_once()
            mock_s3_client.delete_object.assert_called_once()
