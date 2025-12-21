"""
Tests for history API endpoints - Unit tests with mocking.

Tests cover:
- POST /datasets/{dataset_id}/history/undo
- POST /datasets/{dataset_id}/history/redo
- POST /datasets/{dataset_id}/history/jump
- GET /datasets/{dataset_id}/history
- DELETE /datasets/{dataset_id}/history
- Ownership validation
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app
from app.services.exceptions import NotFoundError, ValidationError, PermissionDeniedError


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_history_service():
    """Create mock history service."""
    mock = MagicMock()
    mock.undo = AsyncMock()
    mock.redo = AsyncMock()
    mock.jump_to_position = AsyncMock()
    mock.get_history = AsyncMock()
    mock.clear_history = AsyncMock()
    return mock


class TestUndoEndpoint:
    """Tests for undo endpoint."""

    def test_undo_success(self, client, mock_history_service):
        """Test successful undo operation."""
        # Setup
        mock_history_service.undo.return_value = {
            "success": True,
            "version_id": "v1",
            "current_position": 0,
            "message": "Undone to position 0"
        }

        with patch('app.api.routes.transformations.get_history_service', return_value=mock_history_service):
            with patch('app.auth.nextauth_auth.get_current_user_id', return_value="user1"):
                # Execute
                response = client.post("/api/v1/transformations/datasets/ds1/history/undo")

                # Verify
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["current_position"] == 0
                assert "Undone" in data["message"]

    def test_undo_cannot_undo(self, client, mock_history_service):
        """Test undo when at beginning of history."""
        # Setup
        mock_history_service.undo.side_effect = ValidationError(
            message="Cannot undo: already at the beginning of history"
        )

        with patch('app.api.routes.transformations.get_history_service', return_value=mock_history_service):
            with patch('app.auth.nextauth_auth.get_current_user_id', return_value="user1"):
                # Execute
                response = client.post("/api/v1/transformations/datasets/ds1/history/undo")

                # Verify
                assert response.status_code == 400


class TestRedoEndpoint:
    """Tests for redo endpoint."""

    def test_redo_success(self, client, mock_history_service):
        """Test successful redo operation."""
        # Setup
        mock_history_service.redo.return_value = {
            "success": True,
            "version_id": "v2",
            "current_position": 1,
            "message": "Redone to position 1"
        }

        with patch('app.api.routes.transformations.get_history_service', return_value=mock_history_service):
            with patch('app.auth.nextauth_auth.get_current_user_id', return_value="user1"):
                # Execute
                response = client.post("/api/v1/transformations/datasets/ds1/history/redo")

                # Verify
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["current_position"] == 1


class TestJumpToPositionEndpoint:
    """Tests for jump_to_position endpoint."""

    def test_jump_to_position_success(self, client, mock_history_service):
        """Test successful jump operation."""
        # Setup
        mock_history_service.jump_to_position.return_value = {
            "success": True,
            "version_id": "v0",
            "current_position": 0,
            "message": "Jumped to position 0"
        }

        with patch('app.api.routes.transformations.get_history_service', return_value=mock_history_service):
            with patch('app.auth.nextauth_auth.get_current_user_id', return_value="user1"):
                # Execute
                response = client.post("/api/v1/transformations/datasets/ds1/history/jump", json={"position": 0})

                # Verify
                assert response.status_code == 200
                data = response.json()
                assert data["current_position"] == 0

    def test_jump_to_invalid_position(self, client, mock_history_service):
        """Test jump to invalid position."""
        # Setup
        mock_history_service.jump_to_position.side_effect = ValidationError(
            message="Invalid position 5"
        )

        with patch('app.api.routes.transformations.get_history_service', return_value=mock_history_service):
            with patch('app.auth.nextauth_auth.get_current_user_id', return_value="user1"):
                # Execute
                response = client.post("/api/v1/transformations/datasets/ds1/history/jump", json={"position": 5})

                # Verify
                assert response.status_code == 400


class TestGetHistoryEndpoint:
    """Tests for get_history endpoint."""

    def test_get_history_success(self, client, mock_history_service):
        """Test successful get history operation."""
        # Setup
        mock_history_service.get_history.return_value = {
            "dataset_id": "ds1",
            "current_position": 1,
            "transformation_steps": [
                {"transformation_type": "encode", "column": "col1"},
                {"transformation_type": "scale", "column": "col2"}
            ],
            "can_undo": True,
            "can_redo": False
        }

        with patch('app.api.routes.transformations.get_history_service', return_value=mock_history_service):
            with patch('app.auth.nextauth_auth.get_current_user_id', return_value="user1"):
                # Execute
                response = client.get("/api/v1/transformations/datasets/ds1/history")

                # Verify
                assert response.status_code == 200
                data = response.json()
                assert data["dataset_id"] == "ds1"
                assert data["current_position"] == 1
                assert len(data["transformation_steps"]) == 2


class TestClearHistoryEndpoint:
    """Tests for clear_history endpoint."""

    def test_clear_history_success(self, client, mock_history_service):
        """Test successful clear history operation."""
        # Setup
        mock_history_service.clear_history.return_value = True

        with patch('app.api.routes.transformations.get_history_service', return_value=mock_history_service):
            with patch('app.auth.nextauth_auth.get_current_user_id', return_value="user1"):
                # Execute
                response = client.delete("/api/v1/transformations/datasets/ds1/history")

                # Verify
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
