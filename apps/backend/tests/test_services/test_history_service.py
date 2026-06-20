"""
Tests for HistoryService - Unit tests with mocking (no database required).

Tests cover:
- undo() operation
- redo() operation
- jump_to_position() operation
- get_history() retrieval
- clear_history() operation
- Branching scenarios
- Error handling (invalid position, no history, unauthorized access)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.services.history_service import HistoryService


@pytest.fixture
def mock_versioning_service():
    """Create mock versioning service."""
    mock = MagicMock()
    mock.get_version = AsyncMock()
    mock.get_version_content = AsyncMock()
    mock.create_transformation_version = AsyncMock()
    return mock


@pytest.fixture
def mock_transformation_service():
    """Create mock transformation service."""
    mock = MagicMock()
    mock.get_transformation_config = AsyncMock()
    return mock


@pytest.fixture
def history_service(mock_versioning_service, mock_transformation_service):
    """Create HistoryService with mocked dependencies."""
    return HistoryService(
        versioning_service=mock_versioning_service,
        transformation_service=mock_transformation_service
    )


@pytest.fixture
def mock_transformation_config():
    """Create mock transformation config with history."""
    config = MagicMock()
    config.config_id = "config1"
    config.dataset_id = "ds1"
    config.user_id = "user1"
    config.current_position = 2
    config.transformation_steps = [
        MagicMock(transformation_type="encode", version_id="v1",
                  column="col1", columns=None, rows_affected=10,
                  applied_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)),
        MagicMock(transformation_type="scale", version_id="v2",
                  column="col2", columns=None, rows_affected=10,
                  applied_at=datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC)),
        MagicMock(transformation_type="remove_duplicates", version_id="v3",
                  column=None, columns=None, rows_affected=5,
                  applied_at=datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC))
    ]
    config.can_undo = MagicMock(return_value=True)
    config.can_redo = MagicMock(return_value=False)
    config.save = AsyncMock()
    return config


@pytest.fixture
def mock_dataset():
    """Create mock dataset metadata."""
    dataset = MagicMock()
    dataset.dataset_id = "ds1"
    dataset.user_id = "user1"
    dataset.file_path = "datasets/user1/ds1/current.parquet"
    dataset.save = AsyncMock()
    return dataset


@pytest.mark.unit
class TestHistoryServiceUndo:
    """Tests for undo() operation."""

    @pytest.mark.asyncio
    async def test_undo_success(
        self,
        history_service,
        mock_versioning_service,
        mock_transformation_service,
        mock_transformation_config,
        mock_dataset
    ):
        """Test successful undo operation."""
        # Setup
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        with patch('app.services.history_service.DatasetMetadata') as MockDataset:
            MockDataset.find_one = AsyncMock(return_value=mock_dataset)

            mock_version_content = b"test data"
            mock_versioning_service.get_version_content.return_value = mock_version_content

            # Execute
            result = await history_service.undo("ds1", "user1")

            # Verify
            assert result["success"] is True
            assert result["current_position"] == 1  # Decremented from 2 to 1
            assert result["version_id"] == "v2"  # Version at position 1
            assert "Undone to" in result["message"]

            # Verify config was updated
            assert mock_transformation_config.current_position == 1
            mock_transformation_config.save.assert_called_once()

            # Verify dataset file_path was updated
            assert mock_dataset.save.called

    @pytest.mark.asyncio
    async def test_undo_when_cannot_undo(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test undo when at beginning of history."""
        # Setup: position at 0 (can't undo)
        mock_transformation_config.current_position = 0
        mock_transformation_config.can_undo.return_value = False
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute & Verify
        with pytest.raises(ValidationError, match="Cannot undo"):
            await history_service.undo("ds1", "user1")

    @pytest.mark.asyncio
    async def test_undo_config_not_found(
        self,
        history_service,
        mock_transformation_service
    ):
        """Test undo when transformation config not found."""
        # Setup
        mock_transformation_service.get_transformation_config.return_value = None

        # Execute & Verify
        with pytest.raises(NotFoundError, match="Transformation config"):
            await history_service.undo("ds1", "user1")

    @pytest.mark.asyncio
    async def test_undo_unauthorized_access(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test undo with unauthorized user."""
        # Setup: config belongs to user1, but user2 is trying to undo
        mock_transformation_config.user_id = "user1"
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute & Verify
        with pytest.raises(PermissionDeniedError):
            await history_service.undo("ds1", "user2")


@pytest.mark.unit
class TestHistoryServiceRedo:
    """Tests for redo() operation."""

    @pytest.mark.asyncio
    async def test_redo_success(
        self,
        history_service,
        mock_versioning_service,
        mock_transformation_service,
        mock_transformation_config,
        mock_dataset
    ):
        """Test successful redo operation."""
        # Setup: position at 1, can redo to 2
        mock_transformation_config.current_position = 1
        mock_transformation_config.can_redo.return_value = True
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        with patch('app.services.history_service.DatasetMetadata') as MockDataset:
            MockDataset.find_one = AsyncMock(return_value=mock_dataset)

            mock_version_content = b"test data"
            mock_versioning_service.get_version_content.return_value = mock_version_content

            # Execute
            result = await history_service.redo("ds1", "user1")

            # Verify
            assert result["success"] is True
            assert result["current_position"] == 2  # Incremented from 1 to 2
            assert result["version_id"] == "v3"  # Version at position 2
            assert "Redone to" in result["message"]

    @pytest.mark.asyncio
    async def test_redo_when_cannot_redo(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test redo when at end of history."""
        # Setup: at the end, can't redo
        mock_transformation_config.can_redo.return_value = False
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute & Verify
        with pytest.raises(ValidationError, match="Cannot redo"):
            await history_service.redo("ds1", "user1")

    @pytest.mark.asyncio
    async def test_redo_unauthorized(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test redo with unauthorized user."""
        # Setup: config belongs to user1, but user2 is trying to redo
        mock_transformation_config.user_id = "user1"
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute & Verify
        with pytest.raises(PermissionDeniedError):
            await history_service.redo("ds1", "user2")


@pytest.mark.unit
class TestHistoryServiceJumpToPosition:
    """Tests for jump_to_position() operation."""

    @pytest.mark.asyncio
    async def test_jump_to_position_success(
        self,
        history_service,
        mock_versioning_service,
        mock_transformation_service,
        mock_transformation_config,
        mock_dataset
    ):
        """Test successful jump to specific position."""
        # Setup
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        with patch('app.services.history_service.DatasetMetadata') as MockDataset:
            MockDataset.find_one = AsyncMock(return_value=mock_dataset)

            mock_version_content = b"test data"
            mock_versioning_service.get_version_content.return_value = mock_version_content

            # Execute: jump from position 2 to position 0
            result = await history_service.jump_to_position("ds1", 0, "user1")

            # Verify
            assert result["success"] is True
            assert result["current_position"] == 0
            assert result["version_id"] == "v1"  # Version at position 0
            assert "Jumped to position 0" in result["message"]

    @pytest.mark.asyncio
    async def test_jump_to_invalid_position(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test jump to invalid position."""
        # Setup
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute & Verify: try to jump to position 5 (out of bounds)
        with pytest.raises(ValidationError, match="Invalid position"):
            await history_service.jump_to_position("ds1", 5, "user1")

    @pytest.mark.asyncio
    async def test_jump_to_negative_position(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test jump to negative position."""
        # Setup
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute & Verify
        with pytest.raises(ValidationError, match="Invalid position"):
            await history_service.jump_to_position("ds1", -2, "user1")

    @pytest.mark.asyncio
    async def test_jump_to_position_unauthorized(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test jump_to_position with unauthorized user."""
        # Setup: config belongs to user1, but user2 is trying to jump
        mock_transformation_config.user_id = "user1"
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute & Verify
        with pytest.raises(PermissionDeniedError):
            await history_service.jump_to_position("ds1", 0, "user2")


@pytest.mark.unit
class TestHistoryServiceGetHistory:
    """Tests for get_history() operation."""

    @pytest.mark.asyncio
    async def test_get_history_success(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test successful get_history operation."""
        # Setup
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute
        result = await history_service.get_history("ds1", "user1")

        # Verify (API contract shape — schemas.HistoryDataResponse)
        assert result["dataset_id"] == "ds1"
        assert result["current_position"] == 2
        assert len(result["history"]) == 3
        assert result["history"][0]["position"] == 0
        assert result["history"][0]["transformation_type"] == "encode"
        assert result["can_undo"] is True
        assert result["can_redo"] is False

    def test_describe_step_with_enum_member(self):
        """Descriptions stay human-readable when transformation_type surfaces
        as a TransformationType enum member rather than a plain string
        (str(member) on a str-Enum yields 'TransformationType.X', not the value).
        """
        from app.models.transformation import TransformationType

        step = MagicMock(
            transformation_type=TransformationType.REMOVE_DUPLICATES,
            column=None, columns=None,
        )

        assert HistoryService._describe_step(step) == "Applied remove duplicates"

    @pytest.mark.asyncio
    async def test_get_history_empty(
        self,
        history_service,
        mock_transformation_service
    ):
        """Test get_history with no transformation history."""
        # Setup: empty config
        empty_config = MagicMock()
        empty_config.dataset_id = "ds1"
        empty_config.user_id = "user1"
        empty_config.current_position = -1
        empty_config.transformation_steps = []
        empty_config.can_undo = MagicMock(return_value=False)
        empty_config.can_redo = MagicMock(return_value=False)

        mock_transformation_service.get_transformation_config.return_value = empty_config

        # Execute
        result = await history_service.get_history("ds1", "user1")

        # Verify
        assert result["current_position"] == -1
        assert len(result["history"]) == 0
        assert result["can_undo"] is False
        assert result["can_redo"] is False

    @pytest.mark.asyncio
    async def test_get_history_unauthorized(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test get_history with unauthorized user."""
        # Setup: config belongs to user1, but user2 is trying to get history
        mock_transformation_config.user_id = "user1"
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute & Verify
        with pytest.raises(PermissionDeniedError):
            await history_service.get_history("ds1", "user2")


@pytest.mark.unit
class TestHistoryServiceClearHistory:
    """Tests for clear_history() operation."""

    @pytest.mark.asyncio
    async def test_clear_history_success(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test successful clear_history operation."""
        # Setup
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute
        result = await history_service.clear_history("ds1", "user1")

        # Verify
        assert result is True
        assert mock_transformation_config.transformation_steps == []
        assert mock_transformation_config.current_position == -1
        mock_transformation_config.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_history_unauthorized(
        self,
        history_service,
        mock_transformation_service,
        mock_transformation_config
    ):
        """Test clear_history with unauthorized user."""
        # Setup
        mock_transformation_config.user_id = "user1"
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        # Execute & Verify
        with pytest.raises(PermissionDeniedError):
            await history_service.clear_history("ds1", "user2")


@pytest.mark.unit
class TestHistoryServiceBranching:
    """Tests for branching scenarios."""

    @pytest.mark.asyncio
    async def test_branching_scenario(
        self,
        history_service,
        mock_versioning_service,
        mock_transformation_service,
        mock_transformation_config,
        mock_dataset
    ):
        """Test undo then apply new transformation creates branch."""
        # Setup
        mock_transformation_service.get_transformation_config.return_value = mock_transformation_config

        with patch('app.services.history_service.DatasetMetadata') as MockDataset:
            MockDataset.find_one = AsyncMock(return_value=mock_dataset)

            mock_version_content = b"test data"
            mock_versioning_service.get_version_content.return_value = mock_version_content

            # Execute: undo once
            result1 = await history_service.undo("ds1", "user1")
            assert result1["current_position"] == 1

            # At this point, if a new transformation is applied, it should
            # truncate the history (tested in transformation_service tests)
            # The history service just navigates existing history
