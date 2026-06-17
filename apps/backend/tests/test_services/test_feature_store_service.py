"""
Tests for FeatureStoreService.

Following TDD methodology:
1. RED: Write failing tests
2. GREEN: Implement service to pass tests
3. REFACTOR: Improve code quality

Tests cover CRUD operations, feature application, compatibility checking,
sharing, collections, and version management.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestFeatureStoreServiceCRUD:
    """Unit tests for FeatureStoreService CRUD operations."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.services.feature_store_service import FeatureStoreService
        self.service = FeatureStoreService()

    @pytest.mark.asyncio
    async def test_save_feature_creates_feature_and_version(self):
        """🔴 RED: Test saving a new feature creates StoredFeature and FeatureVersion."""
        # ARRANGE
        feature_data = {
            "name": "Test Feature",
            "description": "A test feature",
            "category": "transformation",
            "tags": ["test"],
            "definition_type": "transformation",
            "definition_code": (
                '{"node_id": "n1", "node_type": "operation", "value": "multiply", "children": ['
                '{"node_id": "n2", "node_type": "column", "value": "old", "children": []},'
                '{"node_id": "n3", "node_type": "constant", "value": 2, "children": []}]}'
            ),
            "input_requirements": {"old": "numeric"},
            "output_type": "numeric",
            "output_column_name": "new",
        }
        user_id = "user_123"

        mock_feature = MagicMock()
        mock_feature.feature_id = "feat_generated_id"
        mock_feature.version = 1
        mock_feature.save = AsyncMock()

        mock_version = MagicMock()
        mock_version.save = AsyncMock()

        # ACT & ASSERT
        with patch('app.services.feature_store_service.StoredFeature') as MockFeature, \
             patch('app.services.feature_store_service.FeatureVersion') as MockVersion, \
             patch('uuid.uuid4') as mock_uuid:

            mock_uuid.return_value.hex = "generated_id"
            MockFeature.return_value = mock_feature
            MockVersion.return_value = mock_version

            result = await self.service.save_feature(feature_data, user_id)

            # Verify feature was created with generated ID
            MockFeature.assert_called_once()
            call_kwargs = MockFeature.call_args[1]
            assert call_kwargs['feature_id'].startswith('feat_')
            assert call_kwargs['user_id'] == user_id
            assert call_kwargs['created_by'] == user_id
            assert call_kwargs['version'] == 1

            # Verify feature was saved
            mock_feature.save.assert_called_once()

            # Verify initial version was created
            MockVersion.assert_called_once()
            version_kwargs = MockVersion.call_args[1]
            assert version_kwargs['feature_id'] == mock_feature.feature_id
            assert version_kwargs['version_number'] == 1
            mock_version.save.assert_called_once()

            # Verify return
            assert result == mock_feature

    @pytest.mark.asyncio
    async def test_get_feature_by_id_owner(self):
        """🔴 RED: Test retrieving feature by ID for owner."""
        # ARRANGE
        feature_id = "feat_123"
        user_id = "user_456"

        mock_feature = MagicMock()
        mock_feature.feature_id = feature_id
        mock_feature.user_id = user_id
        mock_feature.is_public = False
        mock_feature.shared_with = []

        # ACT & ASSERT
        with patch.object(self.service, 'get_by_id_or_raise', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_feature

            result = await self.service.get_feature(feature_id, user_id)

            mock_get.assert_called_once_with(feature_id)
            assert result == mock_feature

    @pytest.mark.asyncio
    async def test_get_feature_public(self):
        """🔴 RED: Test retrieving public feature by non-owner."""
        # ARRANGE
        feature_id = "feat_public"
        owner_id = "user_owner"
        requester_id = "user_other"

        mock_feature = MagicMock()
        mock_feature.feature_id = feature_id
        mock_feature.user_id = owner_id
        mock_feature.is_public = True
        mock_feature.shared_with = []

        # ACT & ASSERT
        with patch.object(self.service, 'get_by_id_or_raise', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_feature

            result = await self.service.get_feature(feature_id, requester_id)

            assert result == mock_feature

    @pytest.mark.asyncio
    async def test_get_feature_shared(self):
        """🔴 RED: Test retrieving shared feature."""
        # ARRANGE
        feature_id = "feat_shared"
        owner_id = "user_owner"
        shared_user_id = "user_shared"

        mock_feature = MagicMock()
        mock_feature.feature_id = feature_id
        mock_feature.user_id = owner_id
        mock_feature.is_public = False
        mock_feature.shared_with = [shared_user_id]

        # ACT & ASSERT
        with patch.object(self.service, 'get_by_id_or_raise', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_feature

            result = await self.service.get_feature(feature_id, shared_user_id)

            assert result == mock_feature

    @pytest.mark.asyncio
    async def test_get_feature_permission_denied(self):
        """🔴 RED: Test retrieving private feature raises PermissionDeniedError."""
        # ARRANGE
        from app.services.exceptions import PermissionDeniedError

        feature_id = "feat_private"
        owner_id = "user_owner"
        other_user_id = "user_other"

        mock_feature = MagicMock()
        mock_feature.feature_id = feature_id
        mock_feature.user_id = owner_id
        mock_feature.is_public = False
        mock_feature.shared_with = []

        # ACT & ASSERT
        with patch.object(self.service, 'get_by_id_or_raise', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_feature

            with pytest.raises(PermissionDeniedError):
                await self.service.get_feature(feature_id, other_user_id)

    @pytest.mark.asyncio
    async def test_get_feature_with_version(self):
        """🔴 RED: Test retrieving specific version of feature."""
        # ARRANGE
        feature_id = "feat_versioned"
        user_id = "user_123"
        version_number = 2

        mock_version = MagicMock()
        mock_version.feature_id = feature_id
        mock_version.version_number = version_number
        mock_version.definition_code = "old code"

        mock_feature = MagicMock()
        mock_feature.feature_id = feature_id
        mock_feature.user_id = user_id
        mock_feature.is_public = False
        mock_feature.version = 3

        # ACT & ASSERT
        with patch('app.services.feature_store_service.FeatureVersion') as MockVersion, \
             patch.object(self.service, 'get_by_id_or_raise', new_callable=AsyncMock) as mock_get:

            mock_get.return_value = mock_feature
            MockVersion.find_one = AsyncMock(return_value=mock_version)

            await self.service.get_feature(feature_id, user_id, version=version_number)

            # Verify version was queried
            MockVersion.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_features_by_query(self):
        """🔴 RED: Test searching features with text query."""
        # ARRANGE
        user_id = "user_123"
        query = "transformation"

        mock_features = [MagicMock(), MagicMock()]
        mock_count = 2

        # ACT & ASSERT
        with patch('app.services.feature_store_service.StoredFeature') as MockFeature:
            mock_find = MagicMock()
            mock_find.skip = MagicMock(return_value=mock_find)
            mock_find.limit = MagicMock(return_value=mock_find)
            mock_find.to_list = AsyncMock(return_value=mock_features)

            MockFeature.find = MagicMock(return_value=mock_find)
            MockFeature.find.return_value.count = AsyncMock(return_value=mock_count)

            result = await self.service.search_features(user_id, query=query)

            assert result['items'] == mock_features
            assert result['total'] == mock_count
            assert result['skip'] == 0
            assert result['limit'] == 20

    @pytest.mark.asyncio
    async def test_search_features_with_filters(self):
        """🔴 RED: Test searching features with category and tag filters."""
        # ARRANGE
        user_id = "user_123"
        filters = {"category": "transformation", "tags": ["numeric"]}

        mock_features = [MagicMock()]
        mock_count = 1

        # ACT & ASSERT
        with patch('app.services.feature_store_service.StoredFeature') as MockFeature:
            mock_find = MagicMock()
            mock_find.skip = MagicMock(return_value=mock_find)
            mock_find.limit = MagicMock(return_value=mock_find)
            mock_find.to_list = AsyncMock(return_value=mock_features)

            MockFeature.find = MagicMock(return_value=mock_find)
            MockFeature.find.return_value.count = AsyncMock(return_value=mock_count)

            result = await self.service.search_features(user_id, filters=filters)

            assert result['total'] == mock_count

    @pytest.mark.asyncio
    async def test_update_feature_creates_new_version(self):
        """🔴 RED: Test updating feature creates new version."""
        # ARRANGE
        feature_id = "feat_update"
        user_id = "user_123"
        updates = {
            "definition_code": (
                '{"node_id": "n1", "node_type": "operation", "value": "multiply", "children": ['
                '{"node_id": "n2", "node_type": "column", "value": "old", "children": []},'
                '{"node_id": "n3", "node_type": "constant", "value": 3, "children": []}]}'
            )
        }

        mock_feature = MagicMock()
        mock_feature.feature_id = feature_id
        mock_feature.user_id = user_id
        mock_feature.version = 1
        mock_feature.definition_code = "df['new'] = df['old'] * 2"
        mock_feature.save = AsyncMock()

        mock_version = MagicMock()
        mock_version.save = AsyncMock()

        # ACT & ASSERT
        with patch.object(self.service, 'get_by_id_or_raise', new_callable=AsyncMock) as mock_get, \
             patch('app.services.feature_store_service.FeatureVersion') as MockVersion:

            mock_get.return_value = mock_feature
            MockVersion.return_value = mock_version

            await self.service.update_feature(feature_id, user_id, updates)

            # Verify version was incremented
            assert mock_feature.version == 2

            # Verify new version was created
            MockVersion.assert_called_once()
            version_kwargs = MockVersion.call_args[1]
            assert version_kwargs['version_number'] == 2

            # Verify feature was saved
            mock_feature.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_feature_soft_delete(self):
        """🔴 RED: Test soft deleting a feature."""
        # ARRANGE
        feature_id = "feat_delete"
        user_id = "user_123"

        # ACT & ASSERT
        with patch.object(self.service, 'delete', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True

            result = await self.service.delete_feature(feature_id, user_id, soft_delete=True)

            mock_delete.assert_called_once_with(feature_id, user_id, soft_delete=True)
            assert result is True


@pytest.mark.unit
class TestFeatureStoreServiceApplication:
    """Unit tests for feature application functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.services.feature_store_service import FeatureStoreService
        self.service = FeatureStoreService()

    @pytest.mark.asyncio
    async def test_check_compatibility_compatible(self):
        """🔴 RED: Test compatibility check with compatible dataset."""
        # ARRANGE
        feature_id = "feat_compat"
        dataset_id = "dataset_123"
        user_id = "user_123"

        mock_feature = MagicMock()
        mock_feature.input_requirements = {"age": "numeric", "name": "text"}
        mock_feature.check_compatibility = MagicMock(return_value=(True, [], {}))

        mock_dataset = MagicMock()
        mock_dataset.data_schema = [
            {"field_name": "age", "field_type": "numeric"},
            {"field_name": "name", "field_type": "text"},
        ]

        # ACT & ASSERT
        with patch.object(self.service, 'get_feature', new_callable=AsyncMock) as mock_get_feature, \
             patch('app.services.feature_store_service.DatasetMetadata') as MockDataset:

            mock_get_feature.return_value = mock_feature
            MockDataset.find_one = AsyncMock(return_value=mock_dataset)

            result = await self.service.check_compatibility(feature_id, dataset_id, user_id)

            assert result['is_compatible'] is True
            assert result['missing_columns'] == []
            assert result['type_mismatches'] == {}

    @pytest.mark.asyncio
    async def test_check_compatibility_missing_columns(self):
        """🔴 RED: Test compatibility check with missing columns."""
        # ARRANGE
        feature_id = "feat_missing"
        dataset_id = "dataset_123"
        user_id = "user_123"

        mock_feature = MagicMock()
        mock_feature.input_requirements = {"age": "numeric", "salary": "numeric"}
        mock_feature.check_compatibility = MagicMock(return_value=(False, ["salary"], {}))

        mock_dataset = MagicMock()
        mock_dataset.data_schema = [
            {"field_name": "age", "field_type": "numeric"},
        ]

        # ACT & ASSERT
        with patch.object(self.service, 'get_feature', new_callable=AsyncMock) as mock_get_feature, \
             patch('app.services.feature_store_service.DatasetMetadata') as MockDataset:

            mock_get_feature.return_value = mock_feature
            MockDataset.find_one = AsyncMock(return_value=mock_dataset)

            result = await self.service.check_compatibility(feature_id, dataset_id, user_id)

            assert result['is_compatible'] is False
            assert "salary" in result['missing_columns']

    @pytest.mark.asyncio
    async def test_apply_feature_increments_usage(self):
        """🔴 RED: Test applying feature increments usage count."""
        # ARRANGE
        feature_id = "feat_apply"
        dataset_id = "dataset_123"
        user_id = "user_123"

        mock_feature = MagicMock()
        mock_feature.feature_id = feature_id
        mock_feature.usage_count = 0
        mock_feature.increment_usage = MagicMock()
        mock_feature.save = AsyncMock()
        mock_feature.applied_to_datasets = []
        mock_feature.output_column_name = "new_column"

        # ACT & ASSERT
        with patch.object(self.service, 'get_feature', new_callable=AsyncMock) as mock_get_feature, \
             patch.object(self.service, 'check_compatibility', new_callable=AsyncMock) as mock_check_compat, \
             patch('app.services.feature_store_service.DatasetMetadata') as MockDataset, \
             patch('app.services.feature_store_service.FeatureEngineer') as MockEngineer, \
             patch('app.services.feature_store_service.get_file_from_s3', new_callable=AsyncMock) as mock_get_file, \
             patch('app.services.feature_store_service.pd') as mock_pd:

            mock_get_feature.return_value = mock_feature
            mock_check_compat.return_value = {"is_compatible": True}
            mock_dataset = MagicMock()
            mock_dataset.file_path = "path/to/file.csv"
            mock_dataset.file_type = "csv"
            MockDataset.find_one = AsyncMock(return_value=mock_dataset)
            mock_get_file.return_value = b"data"
            mock_pd.read_csv.return_value = MagicMock()  # Mock DataFrame

            mock_engineer = MagicMock()
            mock_engineer.apply_stored_feature = AsyncMock(return_value=MagicMock())
            MockEngineer.return_value = mock_engineer

            await self.service.apply_feature(feature_id, dataset_id, user_id)

            # Verify usage was incremented
            mock_feature.increment_usage.assert_called_once()
            mock_feature.save.assert_called_once()


@pytest.mark.unit
class TestFeatureStoreServiceSharing:
    """Unit tests for feature sharing functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.services.feature_store_service import FeatureStoreService
        self.service = FeatureStoreService()

    @pytest.mark.asyncio
    async def test_share_feature(self):
        """🔴 RED: Test sharing feature with users."""
        # ARRANGE
        feature_id = "feat_share"
        user_id = "user_owner"
        share_with = ["user_1", "user_2"]

        mock_feature = MagicMock()
        mock_feature.feature_id = feature_id
        mock_feature.user_id = user_id
        mock_feature.shared_with = []
        mock_feature.save = AsyncMock()

        # ACT & ASSERT
        with patch.object(self.service, 'get_by_id_or_raise', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_feature

            await self.service.share_feature(feature_id, user_id, share_with)

            # Verify users were added to shared_with
            assert "user_1" in mock_feature.shared_with
            assert "user_2" in mock_feature.shared_with
            mock_feature.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_public(self):
        """🔴 RED: Test making feature public."""
        # ARRANGE
        feature_id = "feat_public"
        user_id = "user_owner"

        mock_feature = MagicMock()
        mock_feature.feature_id = feature_id
        mock_feature.user_id = user_id
        mock_feature.is_public = False
        mock_feature.save = AsyncMock()

        # ACT & ASSERT
        with patch.object(self.service, 'get_by_id_or_raise', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_feature

            await self.service.make_public(feature_id, user_id)

            assert mock_feature.is_public is True
            mock_feature.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_feature(self):
        """🔴 RED: Test exporting feature to JSON."""
        # ARRANGE
        feature_id = "feat_export"
        user_id = "user_123"

        mock_feature = MagicMock()
        mock_feature.to_dict = MagicMock(return_value={"feature_id": feature_id})

        mock_versions = [MagicMock(), MagicMock()]

        # ACT & ASSERT
        with patch.object(self.service, 'get_feature', new_callable=AsyncMock) as mock_get, \
             patch.object(self.service, 'get_version_history', new_callable=AsyncMock) as mock_history:

            mock_get.return_value = mock_feature
            mock_history.return_value = mock_versions

            result = await self.service.export_feature(feature_id, user_id, format="json")

            assert "feature" in result
            assert "versions" in result
            assert result["feature"]["feature_id"] == feature_id

    @pytest.mark.asyncio
    async def test_import_feature(self):
        """🔴 RED: Test importing feature from JSON."""
        # ARRANGE
        feature_data = {
            "feature": {
                "name": "Imported Feature",
                "description": "Test import",
                "definition_type": "transformation",
                "definition_code": "code",
                "input_requirements": {},
                "output_type": "numeric",
                "output_column_name": "output",
                "category": "test",
                "tags": []
            },
            "versions": []
        }
        user_id = "user_123"

        # ACT & ASSERT
        with patch.object(self.service, 'save_feature', new_callable=AsyncMock) as mock_save:
            mock_save.return_value = MagicMock()

            await self.service.import_feature(feature_data, user_id)

            mock_save.assert_called_once()


@pytest.mark.unit
class TestFeatureStoreServiceCollections:
    """Unit tests for feature collection management."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.services.feature_store_service import FeatureStoreService
        self.service = FeatureStoreService()

    @pytest.mark.asyncio
    async def test_create_collection(self):
        """🔴 RED: Test creating a feature collection."""
        # ARRANGE
        collection_data = {
            "name": "Test Collection",
            "description": "A test collection",
            "domain": "finance",
            "feature_ids": [],
            "tags": []
        }
        user_id = "user_123"

        mock_collection = MagicMock()
        mock_collection.collection_id = "coll_generated"
        mock_collection.save = AsyncMock()

        # ACT & ASSERT
        with patch('app.services.feature_store_service.FeatureCollection') as MockCollection, \
             patch('uuid.uuid4') as mock_uuid:

            mock_uuid.return_value.hex = "generated"
            MockCollection.return_value = mock_collection

            await self.service.create_collection(collection_data, user_id)

            MockCollection.assert_called_once()
            call_kwargs = MockCollection.call_args[1]
            assert call_kwargs['collection_id'].startswith('coll_')
            assert call_kwargs['user_id'] == user_id
            mock_collection.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_collection(self):
        """🔴 RED: Test adding feature to collection."""
        # ARRANGE
        collection_id = "coll_123"
        feature_id = "feat_456"
        user_id = "user_123"

        mock_collection = MagicMock()
        mock_collection.collection_id = collection_id
        mock_collection.user_id = user_id
        mock_collection.feature_ids = []
        mock_collection.add_feature = MagicMock()
        mock_collection.save = AsyncMock()

        mock_feature = MagicMock()

        # ACT & ASSERT
        with patch('app.services.feature_store_service.FeatureCollection') as MockCollection, \
             patch.object(self.service, 'get_feature', new_callable=AsyncMock) as mock_get_feature:

            MockCollection.find_one = AsyncMock(return_value=mock_collection)
            mock_get_feature.return_value = mock_feature

            await self.service.add_to_collection(collection_id, feature_id, user_id)

            mock_collection.add_feature.assert_called_once_with(feature_id)
            mock_collection.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_version_history(self):
        """🔴 RED: Test retrieving feature version history."""
        # ARRANGE
        feature_id = "feat_history"
        user_id = "user_123"

        mock_feature = MagicMock()
        mock_versions = [MagicMock(), MagicMock()]

        # ACT & ASSERT
        with patch.object(self.service, 'get_feature', new_callable=AsyncMock) as mock_get, \
             patch('app.services.feature_store_service.FeatureVersion') as MockVersion:

            mock_get.return_value = mock_feature

            mock_find = MagicMock()
            mock_find.sort = MagicMock(return_value=mock_find)
            mock_find.to_list = AsyncMock(return_value=mock_versions)
            MockVersion.find = MagicMock(return_value=mock_find)

            result = await self.service.get_version_history(feature_id, user_id)

            assert result == mock_versions


@pytest.mark.unit
class TestFeatureDefinitionValidation:
    """Security (GH-132): definition_code must be a safe expression tree at save/update time."""

    VALID_TREE = (
        '{"node_id": "n1", "node_type": "operation", "value": "multiply", "children": ['
        '{"node_id": "n2", "node_type": "column", "value": "old", "children": []},'
        '{"node_id": "n3", "node_type": "constant", "value": 2, "children": []}]}'
    )

    def setup_method(self):
        """Set up test fixtures."""
        from app.services.feature_store_service import FeatureStoreService
        self.service = FeatureStoreService()

    def _feature_data(self, definition_code):
        return {
            "name": "Test Feature",
            "description": "A test feature",
            "category": "transformation",
            "tags": ["test"],
            "definition_type": "transformation",
            "definition_code": definition_code,
            "input_requirements": {"old": "numeric"},
            "output_type": "numeric",
            "output_column_name": "new",
        }

    @pytest.mark.asyncio
    async def test_save_feature_rejects_raw_python_code(self):
        """Raw Python code must be rejected at creation time, before persisting."""
        from app.services.exceptions import UnsafeFeatureDefinitionError

        with patch('app.services.feature_store_service.StoredFeature') as MockFeature:
            with pytest.raises(UnsafeFeatureDefinitionError):
                await self.service.save_feature(
                    self._feature_data("df['new'] = __import__('os').system('id')"),
                    "user_123",
                )
            MockFeature.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_feature_accepts_expression_tree(self):
        """A valid serialized expression tree is accepted."""
        mock_feature = MagicMock()
        mock_feature.feature_id = "feat_x"
        mock_feature.save = AsyncMock()
        mock_version = MagicMock()
        mock_version.save = AsyncMock()

        with patch('app.services.feature_store_service.StoredFeature') as MockFeature, \
             patch('app.services.feature_store_service.FeatureVersion') as MockVersion:
            MockFeature.return_value = mock_feature
            MockVersion.return_value = mock_version

            result = await self.service.save_feature(
                self._feature_data(self.VALID_TREE), "user_123"
            )

            assert result == mock_feature
            mock_feature.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_feature_rejects_raw_python_code(self):
        """Raw Python code must be rejected at update time, before persisting."""
        from app.services.exceptions import UnsafeFeatureDefinitionError

        mock_feature = MagicMock()
        mock_feature.user_id = "user_123"
        mock_feature.version = 1
        mock_feature.save = AsyncMock()

        with patch.object(self.service, 'get_by_id_or_raise', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_feature

            with pytest.raises(UnsafeFeatureDefinitionError):
                await self.service.update_feature(
                    "feat_x", "user_123",
                    {"definition_code": "import os; os.system('id')"},
                )

            mock_feature.save.assert_not_called()
