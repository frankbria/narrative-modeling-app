import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from beanie import PydanticObjectId
from app.models.plot import Plot
from app.models.user_data import UserData


@pytest.fixture
def mock_plot():
    """Create a mock Plot object for testing."""
    return Plot(
        id=PydanticObjectId(),
        userId="test_user_123",
        datasetId=PydanticObjectId(),
        type="histogram",
        imageUrl="https://example.com/plot.png",
        metadata={"title": "Test Plot", "description": "A test plot"},
        generatedAt=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_plot(test_client: TestClient, mock_plot):
    """Test creating a new plot."""
    with patch("app.models.plot.Plot.insert") as mock_insert:
        mock_insert.return_value = None

        response = test_client.post("/api/v1/plots/", json=mock_plot.dict())

        assert response.status_code == 200
        data = response.json()
        assert data["userId"] == mock_plot.userId
        assert data["type"] == mock_plot.type
        assert data["imageUrl"] == mock_plot.imageUrl
        assert data["metadata"] == mock_plot.metadata


@pytest.mark.asyncio
async def test_get_plots_for_user(test_client: TestClient, mock_plot):
    """Test getting all plots for a user."""
    with patch("app.models.plot.Plot.find") as mock_find:
        mock_find.return_value.to_list.return_value = [mock_plot]

        response = test_client.get("/api/v1/plots/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["userId"] == mock_plot.userId
        assert data[0]["type"] == mock_plot.type


@pytest.mark.asyncio
async def test_get_plot_by_id(test_client: TestClient, mock_plot):
    """Test getting a specific plot by ID."""
    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = mock_plot

        response = test_client.get(f"/api/v1/plots/{mock_plot.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(mock_plot.id)
        assert data["userId"] == mock_plot.userId
        assert data["type"] == mock_plot.type


@pytest.mark.asyncio
async def test_get_plot_by_id_not_found(test_client: TestClient):
    """Test getting a non-existent plot."""
    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = None

        response = test_client.get(f"/api/v1/plots/{PydanticObjectId()}")

        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"


@pytest.mark.asyncio
async def test_update_plot(test_client: TestClient, mock_plot):
    """Test updating a plot."""
    with patch("app.models.plot.Plot.get") as mock_get, patch(
        "app.models.plot.Plot.save"
    ) as mock_save:
        mock_get.return_value = mock_plot
        mock_save.return_value = None

        updated_data = mock_plot.dict()
        updated_data["type"] = "scatter"
        updated_data["metadata"] = {
            "title": "Updated Plot",
            "description": "An updated test plot",
        }

        response = test_client.put(f"/api/v1/plots/{mock_plot.id}", json=updated_data)

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "scatter"
        assert data["metadata"]["title"] == "Updated Plot"


@pytest.mark.asyncio
async def test_update_plot_not_found(test_client: TestClient, mock_plot):
    """Test updating a non-existent plot."""
    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = None

        response = test_client.put(
            f"/api/v1/plots/{PydanticObjectId()}", json=mock_plot.dict()
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"


@pytest.mark.asyncio
async def test_delete_plot(test_client: TestClient, mock_plot):
    """Test deleting a plot."""
    with patch("app.models.plot.Plot.get") as mock_get, patch(
        "app.models.plot.Plot.delete"
    ) as mock_delete:
        mock_get.return_value = mock_plot
        mock_delete.return_value = None

        response = test_client.delete(f"/api/v1/plots/{mock_plot.id}")

        assert response.status_code == 200
        assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_plot_not_found(test_client: TestClient):
    """Test deleting a non-existent plot."""
    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = None

        response = test_client.delete(f"/api/v1/plots/{PydanticObjectId()}")

        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"


@pytest.mark.asyncio
async def test_get_plot_with_different_user(test_client: TestClient, mock_plot):
    """Test getting a plot with a different user ID."""
    # Change the user ID to simulate a different user
    different_user_id = "different_user_123"
    mock_plot.userId = different_user_id

    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = mock_plot

        response = test_client.get(f"/api/v1/plots/{mock_plot.id}")

        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"


@pytest.mark.asyncio
async def test_create_plot_with_dataset_link(test_client: TestClient, mock_plot):
    """Test creating a plot with a dataset link."""
    # Create a mock dataset ID
    dataset_id = PydanticObjectId()
    mock_plot.datasetId = dataset_id

    with patch("app.models.plot.Plot.insert") as mock_insert:
        mock_insert.return_value = None

        response = test_client.post("/api/v1/plots/", json=mock_plot.dict())

        assert response.status_code == 200
        data = response.json()
        assert data["datasetId"] == str(dataset_id)
        assert data["type"] == mock_plot.type
        assert data["imageUrl"] == mock_plot.imageUrl
