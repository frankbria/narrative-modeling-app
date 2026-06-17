"""
Tests for history API endpoints - Unit tests with mocking.

Tests cover:
- POST /datasets/{dataset_id}/history/undo
- POST /datasets/{dataset_id}/history/redo
- POST /datasets/{dataset_id}/history/jump
- GET /datasets/{dataset_id}/history
- DELETE /datasets/{dataset_id}/history

Auth and the history service are injected via app.dependency_overrides —
patching module attributes does not affect FastAPI's resolved dependency
graph (the routes hold direct references via Depends).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.routes.transformations import get_history_service
from app.auth.nextauth_auth import get_current_user_id
from app.main import app
from app.services.exceptions import ValidationError

pytestmark = pytest.mark.unit


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


@pytest.fixture
def client(mock_history_service):
    """Test client with auth and history service dependencies overridden."""
    app.dependency_overrides[get_current_user_id] = lambda: "user1"
    app.dependency_overrides[get_history_service] = lambda: mock_history_service

    # No context manager: these endpoints don't need the app lifespan (DB),
    # the service layer is fully mocked
    yield TestClient(app)

    app.dependency_overrides.clear()


class TestUndoEndpoint:
    """Tests for undo endpoint."""

    def test_undo_success(self, client, mock_history_service):
        """Test successful undo operation."""
        mock_history_service.undo.return_value = {
            "success": True,
            "version_id": "v1",
            "current_position": 0,
            "message": "Undone to position 0"
        }

        response = client.post("/api/v1/transformations/datasets/ds1/history/undo")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["current_position"] == 0
        assert "Undone" in data["message"]
        mock_history_service.undo.assert_awaited_once_with("ds1", "user1")

    def test_undo_cannot_undo(self, client, mock_history_service):
        """Test undo when at beginning of history."""
        mock_history_service.undo.side_effect = ValidationError(
            message="Cannot undo: already at the beginning of history"
        )

        response = client.post("/api/v1/transformations/datasets/ds1/history/undo")

        assert response.status_code == 400


class TestRedoEndpoint:
    """Tests for redo endpoint."""

    def test_redo_success(self, client, mock_history_service):
        """Test successful redo operation."""
        mock_history_service.redo.return_value = {
            "success": True,
            "version_id": "v2",
            "current_position": 1,
            "message": "Redone to position 1"
        }

        response = client.post("/api/v1/transformations/datasets/ds1/history/redo")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["current_position"] == 1


class TestJumpToPositionEndpoint:
    """Tests for jump_to_position endpoint."""

    def test_jump_to_position_success(self, client, mock_history_service):
        """Test successful jump operation (position is a query parameter)."""
        mock_history_service.jump_to_position.return_value = {
            "success": True,
            "version_id": "v0",
            "current_position": 0,
            "message": "Jumped to position 0"
        }

        response = client.post(
            "/api/v1/transformations/datasets/ds1/history/jump",
            params={"position": 0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["current_position"] == 0
        mock_history_service.jump_to_position.assert_awaited_once_with("ds1", 0, "user1")

    def test_jump_to_invalid_position(self, client, mock_history_service):
        """Test jump to invalid position."""
        mock_history_service.jump_to_position.side_effect = ValidationError(
            message="Invalid position 5"
        )

        response = client.post(
            "/api/v1/transformations/datasets/ds1/history/jump",
            params={"position": 5},
        )

        assert response.status_code == 400

    def test_jump_without_position_is_validation_error(self, client, mock_history_service):
        """Omitting the required position query parameter yields 422."""
        response = client.post("/api/v1/transformations/datasets/ds1/history/jump")

        assert response.status_code == 422
        mock_history_service.jump_to_position.assert_not_awaited()


class TestGetHistoryEndpoint:
    """Tests for get_history endpoint."""

    def test_get_history_success(self, client, mock_history_service):
        """Test successful get history operation."""
        mock_history_service.get_history.return_value = {
            "dataset_id": "ds1",
            "current_position": 1,
            "history": [
                {
                    "position": 0,
                    "transformation_type": "encode",
                    "description": "Applied encode to col1",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "affected_columns": ["col1"],
                },
                {
                    "position": 1,
                    "transformation_type": "scale",
                    "description": "Applied scale to col2",
                    "timestamp": "2026-01-01T00:01:00+00:00",
                    "affected_columns": ["col2"],
                },
            ],
            "can_undo": True,
            "can_redo": False
        }

        response = client.get("/api/v1/transformations/datasets/ds1/history")

        assert response.status_code == 200
        data = response.json()
        assert data["current_position"] == 1
        assert len(data["history"]) == 2


class TestClearHistoryEndpoint:
    """Tests for clear_history endpoint."""

    def test_clear_history_success(self, client, mock_history_service):
        """Test successful clear history operation."""
        mock_history_service.clear_history.return_value = True

        response = client.delete("/api/v1/transformations/datasets/ds1/history")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
