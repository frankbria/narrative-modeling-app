"""
Tests for versioning service.

Tests version creation, retrieval, lineage tracking, and version management.
Uses proper mocking to avoid Beanie initialization requirements.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
import io

from app.services.versioning_service import VersioningService
from app.services.exceptions import (
    NotFoundError,
    ConflictError,
    OperationError,
    ValidationError
)


@pytest.fixture
def versioning_service():
    """Create versioning service instance with mocked S3 client."""
    with patch('app.services.versioning_service.boto3') as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.client.return_value = mock_s3
        service = VersioningService()
        service.s3_client = mock_s3
        return service


@pytest.fixture
def mock_dataset_metadata():
    """Create mock dataset metadata without Beanie initialization."""
    mock = MagicMock()
    mock.user_id = "user1"
    mock.dataset_id = "ds1"
    mock.filename = "test.csv"
    mock.original_filename = "test.csv"
    mock.file_type = "csv"
    mock.file_path = "datasets/user1/ds1/test.csv"
    mock.s3_url = "s3://bucket/datasets/user1/ds1/test.csv"
    mock.file_size = 1024
    mock.num_rows = 100
    mock.num_columns = 5
    mock.columns = ["col1", "col2", "col3", "col4", "col5"]

    # Create mock schema fields
    mock_schema = []
    schema_data = [
        ("col1", "numeric", "int64", 50, 0),
        ("col2", "numeric", "float64", 80, 5),
        ("col3", "text", "object", 100, 0),
        ("col4", "categorical", "object", 3, 0),
        ("col5", "boolean", "bool", 2, 0),
    ]
    for field_name, field_type, inferred_dtype, unique_values, missing_values in schema_data:
        field_mock = MagicMock()
        field_mock.field_name = field_name
        field_mock.field_type = field_type
        field_mock.inferred_dtype = inferred_dtype
        field_mock.unique_values = unique_values
        field_mock.missing_values = missing_values
        mock_schema.append(field_mock)

    mock.data_schema = mock_schema
    return mock


@pytest.mark.unit
class TestVersionCreation:
    """Tests for version creation."""

    @pytest.mark.asyncio
    async def test_create_base_version(self, versioning_service, mock_dataset_metadata):
        """Test creating base version for new dataset."""
        file_content = b"test,data,content"

        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            # Mock find_one to return None (no existing base version)
            MockDatasetVersion.find_one = AsyncMock(return_value=None)

            # Mock static methods
            MockDatasetVersion.compute_content_hash = Mock(return_value="abc123hash")
            MockDatasetVersion.compute_schema_hash = Mock(return_value="schema123hash")

            # Create mock version instance
            mock_version = MagicMock()
            mock_version.dataset_id = "ds1"
            mock_version.version_number = 1
            mock_version.user_id = "user1"
            mock_version.is_base_version = True
            mock_version.num_rows = 100
            mock_version.num_columns = 5
            mock_version.columns = ["col1", "col2", "col3", "col4", "col5"]
            mock_version.description = "Initial upload"
            mock_version.file_size = len(file_content)
            mock_version.insert = AsyncMock()

            MockDatasetVersion.return_value = mock_version

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
            mock_version.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_base_version_duplicate_error(self, versioning_service, mock_dataset_metadata):
        """Test creating base version when one already exists raises ConflictError."""
        file_content = b"test,data,content"

        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            # Mock existing base version
            existing_version = MagicMock()
            existing_version.dataset_id = "ds1"
            existing_version.version_id = "existing_v1"
            existing_version.is_base_version = True

            MockDatasetVersion.find_one = AsyncMock(return_value=existing_version)

            with pytest.raises(ConflictError, match="Base version already exists"):
                await versioning_service.create_base_version(
                    dataset_metadata=mock_dataset_metadata,
                    file_content=file_content,
                    user_id="user1"
                )

    @pytest.mark.asyncio
    async def test_create_transformation_version_parent_not_found(self, versioning_service, mock_dataset_metadata):
        """Test error when parent version not found raises NotFoundError."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            MockDatasetVersion.find_one = AsyncMock(return_value=None)

            with pytest.raises(NotFoundError) as exc_info:
                await versioning_service.create_transformation_version(
                    parent_version_id="nonexistent",
                    transformed_content=b"data",
                    transformation_steps=[],
                    dataset_metadata=mock_dataset_metadata,
                    user_id="user1"
                )

            assert "DatasetVersion" in str(exc_info.value.message)
            assert "nonexistent" in str(exc_info.value.message)


@pytest.mark.unit
class TestVersionRetrieval:
    """Tests for version retrieval."""

    @pytest.mark.asyncio
    async def test_get_version(self, versioning_service):
        """Test retrieving a version."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            mock_version = MagicMock()
            mock_version.version_id = "v1"
            mock_version.access_count = 0
            mock_version.mark_accessed = MagicMock()
            mock_version.save = AsyncMock()

            MockDatasetVersion.find_one = AsyncMock(return_value=mock_version)

            version = await versioning_service.get_version("v1", mark_accessed=True)

            assert version.version_id == "v1"
            mock_version.mark_accessed.assert_called_once()
            mock_version.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_version_not_found(self, versioning_service):
        """Test retrieving nonexistent version returns None."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            MockDatasetVersion.find_one = AsyncMock(return_value=None)

            version = await versioning_service.get_version("nonexistent")
            assert version is None

    @pytest.mark.asyncio
    async def test_get_version_without_marking_accessed(self, versioning_service):
        """Test retrieving version without marking as accessed."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            mock_version = MagicMock()
            mock_version.version_id = "v1"
            mock_version.access_count = 0

            MockDatasetVersion.find_one = AsyncMock(return_value=mock_version)

            version = await versioning_service.get_version("v1", mark_accessed=False)

            assert version.version_id == "v1"
            mock_version.mark_accessed.assert_not_called()
            mock_version.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_version_content(self, versioning_service):
        """Test retrieving version file content."""
        file_content = b"test,data,content"
        mock_response = {'Body': io.BytesIO(file_content)}
        versioning_service.s3_client.get_object.return_value = mock_response

        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            mock_version = MagicMock()
            mock_version.version_id = "v1"
            mock_version.file_path = "path/to/file"
            mock_version.mark_accessed = MagicMock()
            mock_version.save = AsyncMock()

            MockDatasetVersion.find_one = AsyncMock(return_value=mock_version)

            content = await versioning_service.get_version_content("v1")

            assert content == file_content
            versioning_service.s3_client.get_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_version_content_not_found(self, versioning_service):
        """Test error when version not found raises NotFoundError."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            MockDatasetVersion.find_one = AsyncMock(return_value=None)

            with pytest.raises(NotFoundError) as exc_info:
                await versioning_service.get_version_content("nonexistent")

            assert "nonexistent" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_list_versions(self, versioning_service):
        """Test listing versions for a dataset."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            versions = [
                MagicMock(version_id="v3", version_number=3),
                MagicMock(version_id="v2", version_number=2),
                MagicMock(version_id="v1", version_number=1),
            ]

            # Mock the chain: find().find().sort().skip().limit().to_list()
            mock_query = MagicMock()
            mock_query.find = MagicMock(return_value=mock_query)
            mock_query.sort = MagicMock(return_value=mock_query)
            mock_query.skip = MagicMock(return_value=mock_query)
            mock_query.limit = MagicMock(return_value=mock_query)
            mock_query.to_list = AsyncMock(return_value=versions)

            MockDatasetVersion.find = MagicMock(return_value=mock_query)

            result = await versioning_service.list_versions(
                dataset_id="ds1",
                user_id="user1",
                limit=50,
                skip=0
            )

            assert len(result) == 3
            assert result[0].version_id == "v3"


@pytest.mark.unit
class TestLineageTracking:
    """Tests for lineage tracking."""

    @pytest.mark.asyncio
    async def test_get_lineage_chain(self, versioning_service):
        """Test retrieving complete lineage chain."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            with patch('app.services.versioning_service.TransformationLineage') as MockLineage:
                # Create version chain: v1 -> v2 -> v3
                v1 = MagicMock()
                v1.version_id = "v1"
                v1.parent_version_id = None
                v1.transformation_lineage_id = None
                v1.is_base_version = True

                v2 = MagicMock()
                v2.version_id = "v2"
                v2.parent_version_id = "v1"
                v2.transformation_lineage_id = "lin1"

                v3 = MagicMock()
                v3.version_id = "v3"
                v3.parent_version_id = "v2"
                v3.transformation_lineage_id = "lin2"

                lin1 = MagicMock()
                lin1.lineage_id = "lin1"
                lin1.parent_version_id = "v1"
                lin1.child_version_id = "v2"

                lin2 = MagicMock()
                lin2.lineage_id = "lin2"
                lin2.parent_version_id = "v2"
                lin2.child_version_id = "v3"

                # Set up find_one to return correct versions
                async def mock_dv_find_one(*args, **kwargs):
                    # Called for get_version - returns based on call order
                    return v3

                call_count = [0]
                async def version_find_one(*args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return v3
                    elif call_count[0] == 2:
                        return v2
                    elif call_count[0] == 3:
                        return v1
                    return None

                lineage_call_count = [0]
                async def lineage_find_one(*args, **kwargs):
                    lineage_call_count[0] += 1
                    if lineage_call_count[0] == 1:
                        return lin2
                    elif lineage_call_count[0] == 2:
                        return lin1
                    return None

                MockDatasetVersion.find_one = AsyncMock(side_effect=version_find_one)
                MockLineage.find_one = AsyncMock(side_effect=lineage_find_one)

                chain = await versioning_service.get_lineage_chain("v3")

                assert len(chain) == 2
                assert chain[0].lineage_id == "lin1"
                assert chain[1].lineage_id == "lin2"


@pytest.mark.unit
class TestVersionComparison:
    """Tests for version comparison."""

    @pytest.mark.asyncio
    async def test_compare_versions(self, versioning_service):
        """Test comparing two versions."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            v1 = MagicMock()
            v1.version_id = "v1"
            v1.dataset_id = "ds1"
            v1.num_rows = 100
            v1.num_columns = 5
            v1.columns = ["col1", "col2", "col3", "col4", "col5"]
            v1.schema_hash = "schema1"
            v1.content_hash = "hash1"

            v2 = MagicMock()
            v2.version_id = "v2"
            v2.dataset_id = "ds1"
            v2.num_rows = 95
            v2.num_columns = 6
            v2.columns = ["col1", "col2", "col3", "col4", "col5", "col6"]
            v2.schema_hash = "schema2"
            v2.content_hash = "hash2"
            v2.parent_version_id = "v1"

            MockDatasetVersion.find_one = AsyncMock(side_effect=[v1, v2])

            # Mock _find_lineage_path
            with patch.object(versioning_service, '_find_lineage_path', new_callable=AsyncMock) as mock_path:
                mock_path.return_value = []

                comparison = await versioning_service.compare_versions("v1", "v2")

                assert comparison.version1_id == "v1"
                assert comparison.version2_id == "v2"
                assert comparison.rows_diff == -5  # 95 - 100
                assert comparison.columns_diff == 1  # 6 - 5
                assert "col6" in comparison.columns_added
                assert len(comparison.columns_removed) == 0
                assert comparison.content_similarity == 0.0

    @pytest.mark.asyncio
    async def test_compare_versions_different_datasets(self, versioning_service):
        """Test error when comparing versions from different datasets raises ValidationError."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            v1 = MagicMock()
            v1.dataset_id = "ds1"
            v2 = MagicMock()
            v2.dataset_id = "ds2"

            MockDatasetVersion.find_one = AsyncMock(side_effect=[v1, v2])

            with pytest.raises(ValidationError, match="must be from the same dataset"):
                await versioning_service.compare_versions("v1", "v2")


@pytest.mark.unit
class TestVersionManagement:
    """Tests for version management operations."""

    @pytest.mark.asyncio
    async def test_pin_version(self, versioning_service):
        """Test pinning a version."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            mock_version = MagicMock()
            mock_version.is_pinned = False
            mock_version.pin_version = MagicMock()
            mock_version.save = AsyncMock()

            MockDatasetVersion.find_one = AsyncMock(return_value=mock_version)

            version = await versioning_service.pin_version("v1")

            mock_version.pin_version.assert_called_once()
            mock_version.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_pin_version_not_found(self, versioning_service):
        """Test pinning nonexistent version raises NotFoundError."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            MockDatasetVersion.find_one = AsyncMock(return_value=None)

            with pytest.raises(NotFoundError):
                await versioning_service.pin_version("nonexistent")

    @pytest.mark.asyncio
    async def test_unpin_version(self, versioning_service):
        """Test unpinning a version."""
        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            mock_version = MagicMock()
            mock_version.is_pinned = True
            mock_version.unpin_version = MagicMock()
            mock_version.save = AsyncMock()

            MockDatasetVersion.find_one = AsyncMock(return_value=mock_version)

            version = await versioning_service.unpin_version("v1")

            mock_version.unpin_version.assert_called_once()
            mock_version.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_versions(self, versioning_service):
        """Test cleaning up old versions."""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        now = datetime.now(timezone.utc)

        with patch('app.services.versioning_service.DatasetVersion') as MockDatasetVersion:
            versions = [
                # Keep: recent (index 0, 1, 2 - within keep_count=3)
                MagicMock(
                    version_id="v10",
                    is_pinned=False,
                    is_base_version=False,
                    created_at=now,
                    used_in_training=[],
                    file_path="path10",
                    delete=AsyncMock()
                ),
                MagicMock(
                    version_id="v9",
                    is_pinned=True,
                    is_base_version=False,
                    created_at=old_date,
                    used_in_training=[],
                    file_path="path9",
                    delete=AsyncMock()
                ),
                MagicMock(
                    version_id="v1",
                    is_pinned=False,
                    is_base_version=True,
                    created_at=old_date,
                    used_in_training=[],
                    file_path="path1",
                    delete=AsyncMock()
                ),
                # Delete: old and unpinned (index 3 - outside keep_count)
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
            mock_query.sort = MagicMock(return_value=mock_query)
            mock_query.to_list = AsyncMock(return_value=versions)

            MockDatasetVersion.find = MagicMock(return_value=mock_query)

            deleted_count = await versioning_service.cleanup_old_versions(
                dataset_id="ds1",
                retention_days=30,
                keep_count=3
            )

            assert deleted_count == 1
            versions[3].delete.assert_called_once()
            versioning_service.s3_client.delete_object.assert_called_once()
