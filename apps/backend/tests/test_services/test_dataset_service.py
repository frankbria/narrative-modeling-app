"""
Tests for Dataset Service.

Following TDD methodology with simplified mocking approach.
Tests cover core business logic without deep Beanie Document mocking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from app.models.dataset import SchemaField, AISummary, PIIReport


@pytest.mark.unit
class TestDatasetService:
    """Unit tests for DatasetService business logic."""

    def setup_method(self):
        """Set up test fixtures."""
        # Lazy import to avoid app initialization
        from app.services.dataset_service import DatasetService
        self.service = DatasetService()

    @pytest.fixture
    def sample_schema_fields(self):
        """Create sample schema fields for testing."""
        return [
            SchemaField(
                field_name="id",
                field_type="numeric",
                data_type="ratio",
                inferred_dtype="int64",
                unique_values=100,
                missing_values=0,
                example_values=[1, 2, 3],
                is_constant=False,
                is_high_cardinality=False
            ),
            SchemaField(
                field_name="name",
                field_type="text",
                data_type="nominal",
                inferred_dtype="object",
                unique_values=95,
                missing_values=5,
                example_values=["Alice", "Bob", "Charlie"],
                is_constant=False,
                is_high_cardinality=False
            )
        ]

    @pytest.mark.asyncio
    async def test_create_dataset_creates_metadata_object(self, sample_schema_fields):
        """Test that create_dataset instantiates DatasetMetadata with correct parameters."""
        # ARRANGE
        user_id = "test_user_123"
        dataset_params = {
            "dataset_id": "dataset_123",
            "filename": "test_data.csv",
            "original_filename": "user_upload.csv",
            "file_type": "csv",
            "file_path": "datasets/test_data.csv",
            "s3_url": "https://s3.amazonaws.com/bucket/test_data.csv",
            "file_size": 1024,
            "num_rows": 100,
            "num_columns": 2,
            "columns": ["id", "name"],
            "data_schema": sample_schema_fields
        }

        # Create mock dataset that will be returned
        mock_dataset = MagicMock()
        mock_dataset.save = AsyncMock()
        mock_dataset.user_id = user_id
        mock_dataset.dataset_id = dataset_params["dataset_id"]

        # Mock UserData creation and save
        mock_userdata = MagicMock()
        mock_userdata.save = AsyncMock()

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass, \
             patch('app.services.dataset_service.UserData') as MockUserDataClass:

            MockDatasetClass.return_value = mock_dataset
            MockUserDataClass.return_value = mock_userdata

            result = await self.service.create_dataset(user_id=user_id, **dataset_params)

            # Verify DatasetMetadata was instantiated with correct params
            MockDatasetClass.assert_called_once()
            call_kwargs = MockDatasetClass.call_args[1]
            assert call_kwargs['user_id'] == user_id
            assert call_kwargs['dataset_id'] == dataset_params['dataset_id']
            assert call_kwargs['filename'] == dataset_params['filename']
            assert call_kwargs['num_rows'] == dataset_params['num_rows']

            # Verify save was called
            mock_dataset.save.assert_called_once()

            # Verify UserData was created (dual-write)
            MockUserDataClass.assert_called_once()
            mock_userdata.save.assert_called_once()

            # Verify return value
            assert result == mock_dataset

    @pytest.mark.asyncio
    async def test_create_dataset_with_ai_summary(self, sample_schema_fields):
        """Test dataset creation includes AI summary when provided."""
        # ARRANGE
        ai_summary = AISummary(
            overview="Test dataset",
            issues=["Missing values"],
            relationships=["id unique"],
            suggestions=["Fill missing"],
            rawMarkdown="# Summary"
        )

        dataset_params = {
            "dataset_id": "dataset_123",
            "filename": "test.csv",
            "original_filename": "test.csv",
            "file_type": "csv",
            "file_path": "datasets/test.csv",
            "s3_url": "https://s3.amazonaws.com/test.csv",
            "num_rows": 100,
            "num_columns": 2,
            "columns": ["id", "name"],
            "data_schema": sample_schema_fields,
            "ai_summary": ai_summary
        }

        mock_dataset = MagicMock()
        mock_dataset.save = AsyncMock()
        mock_userdata = MagicMock()
        mock_userdata.save = AsyncMock()

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass, \
             patch('app.services.dataset_service.UserData') as MockUserDataClass:

            MockDatasetClass.return_value = mock_dataset
            MockUserDataClass.return_value = mock_userdata

            await self.service.create_dataset(user_id="user_123", **dataset_params)

            # Verify AI summary was passed to DatasetMetadata
            call_kwargs = MockDatasetClass.call_args[1]
            assert call_kwargs['ai_summary'] == ai_summary

    @pytest.mark.asyncio
    async def test_create_dataset_with_pii_report(self, sample_schema_fields):
        """Test dataset creation includes PII report when provided."""
        # ARRANGE
        pii_report = PIIReport(
            contains_pii=True,
            pii_fields=["email", "ssn"],
            risk_level="high",
            detection_details={"email": {"count": 50}},
            masked=False
        )

        dataset_params = {
            "dataset_id": "dataset_123",
            "filename": "test.csv",
            "original_filename": "test.csv",
            "file_type": "csv",
            "file_path": "datasets/test.csv",
            "s3_url": "https://s3.amazonaws.com/test.csv",
            "num_rows": 100,
            "num_columns": 2,
            "columns": ["id", "name"],
            "data_schema": sample_schema_fields,
            "pii_report": pii_report
        }

        mock_dataset = MagicMock()
        mock_dataset.save = AsyncMock()
        mock_userdata = MagicMock()
        mock_userdata.save = AsyncMock()

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass, \
             patch('app.services.dataset_service.UserData') as MockUserDataClass:

            MockDatasetClass.return_value = mock_dataset
            MockUserDataClass.return_value = mock_userdata

            await self.service.create_dataset(user_id="user_123", **dataset_params)

            # Verify PII report was passed
            call_kwargs = MockDatasetClass.call_args[1]
            assert call_kwargs['pii_report'] == pii_report

    @pytest.mark.asyncio
    async def test_get_dataset_calls_find_one(self):
        """Test get_dataset uses correct Beanie query."""
        # ARRANGE
        dataset_id = "dataset_123"
        mock_dataset = MagicMock()

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass:
            mock_find_one = AsyncMock(return_value=mock_dataset)
            MockDatasetClass.find_one = mock_find_one

            result = await self.service.get_dataset(dataset_id)

            # Verify find_one was called
            mock_find_one.assert_called_once()
            assert result == mock_dataset

    @pytest.mark.asyncio
    async def test_get_dataset_returns_none_when_not_found(self):
        """Test get_dataset returns None when dataset doesn't exist."""
        # ARRANGE
        dataset_id = "nonexistent"

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass:
            mock_find_one = AsyncMock(return_value=None)
            MockDatasetClass.find_one = mock_find_one

            result = await self.service.get_dataset(dataset_id)

            assert result is None

    @pytest.mark.asyncio
    async def test_list_datasets_returns_all_for_user(self):
        """Test list_datasets returns all datasets for a user."""
        # ARRANGE
        user_id = "test_user_123"
        mock_datasets = [MagicMock(), MagicMock(), MagicMock()]

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass:
            mock_find = MagicMock()
            mock_find.to_list = AsyncMock(return_value=mock_datasets)
            MockDatasetClass.find = MagicMock(return_value=mock_find)

            result = await self.service.list_datasets(user_id)

            # Verify find was called
            MockDatasetClass.find.assert_called_once()
            assert result == mock_datasets
            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_datasets_returns_empty_list(self):
        """Test list_datasets returns empty list when user has no datasets."""
        # ARRANGE
        user_id = "new_user"

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass:
            mock_find = MagicMock()
            mock_find.to_list = AsyncMock(return_value=[])
            MockDatasetClass.find = MagicMock(return_value=mock_find)

            result = await self.service.list_datasets(user_id)

            assert result == []

    @pytest.mark.asyncio
    async def test_update_dataset_modifies_fields(self):
        """Test update_dataset modifies dataset fields and saves."""
        # ARRANGE
        dataset_id = "dataset_123"
        mock_dataset = MagicMock()
        mock_dataset.num_rows = 100
        mock_dataset.update_timestamp = MagicMock()
        mock_dataset.save = AsyncMock()

        update_data = {"num_rows": 150, "statistics": {"mean": 35.5}}

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass:
            mock_find_one = AsyncMock(return_value=mock_dataset)
            MockDatasetClass.find_one = mock_find_one

            result = await self.service.update_dataset(dataset_id, **update_data)

            # Verify update_timestamp was called
            mock_dataset.update_timestamp.assert_called_once()

            # Verify save was called
            mock_dataset.save.assert_called_once()

            assert result == mock_dataset

    @pytest.mark.asyncio
    async def test_update_dataset_returns_none_when_not_found(self):
        """Test update_dataset returns None when dataset doesn't exist."""
        # ARRANGE
        dataset_id = "nonexistent"

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass:
            mock_find_one = AsyncMock(return_value=None)
            MockDatasetClass.find_one = mock_find_one

            result = await self.service.update_dataset(dataset_id, num_rows=150)

            assert result is None

    @pytest.mark.asyncio
    async def test_delete_dataset_calls_delete(self):
        """Test delete_dataset calls delete on dataset."""
        # ARRANGE
        dataset_id = "dataset_123"
        mock_dataset = MagicMock()
        mock_dataset.delete = AsyncMock()

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass:
            mock_find_one = AsyncMock(return_value=mock_dataset)
            MockDatasetClass.find_one = mock_find_one

            result = await self.service.delete_dataset(dataset_id)

            mock_dataset.delete.assert_called_once()
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_dataset_returns_false_when_not_found(self):
        """Test delete_dataset returns False when dataset doesn't exist."""
        # ARRANGE
        dataset_id = "nonexistent"

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass:
            mock_find_one = AsyncMock(return_value=None)
            MockDatasetClass.find_one = mock_find_one

            result = await self.service.delete_dataset(dataset_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_mark_dataset_processed_updates_status(self):
        """Test mark_dataset_processed calls mark_processed and saves."""
        # ARRANGE
        dataset_id = "dataset_123"
        mock_dataset = MagicMock()
        mock_dataset.mark_processed = MagicMock()
        mock_dataset.save = AsyncMock()

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass:
            mock_find_one = AsyncMock(return_value=mock_dataset)
            MockDatasetClass.find_one = mock_find_one

            result = await self.service.mark_dataset_processed(dataset_id)

            mock_dataset.mark_processed.assert_called_once()
            mock_dataset.save.assert_called_once()
            assert result == mock_dataset

    @pytest.mark.asyncio
    async def test_dual_write_creates_both_models(self, sample_schema_fields):
        """Test that create_dataset performs dual-write to both DatasetMetadata and UserData."""
        # ARRANGE
        dataset_params = {
            "dataset_id": "dataset_123",
            "filename": "test.csv",
            "original_filename": "test.csv",
            "file_type": "csv",
            "file_path": "datasets/test.csv",
            "s3_url": "https://s3.amazonaws.com/test.csv",
            "num_rows": 100,
            "num_columns": 2,
            "columns": ["id", "name"],
            "data_schema": sample_schema_fields
        }

        mock_dataset = MagicMock()
        mock_dataset.save = AsyncMock()
        mock_userdata = MagicMock()
        mock_userdata.save = AsyncMock()

        # ACT & ASSERT
        with patch('app.services.dataset_service.DatasetMetadata') as MockDatasetClass, \
             patch('app.services.dataset_service.UserData') as MockUserDataClass:

            MockDatasetClass.return_value = mock_dataset
            MockUserDataClass.return_value = mock_userdata

            result = await self.service.create_dataset(user_id="user_123", **dataset_params)

            # Verify both models were created
            MockDatasetClass.assert_called_once()
            MockUserDataClass.assert_called_once()

            # Verify both were saved
            mock_dataset.save.assert_called_once()
            mock_userdata.save.assert_called_once()

            # Verify DatasetMetadata is returned
            assert result == mock_dataset
