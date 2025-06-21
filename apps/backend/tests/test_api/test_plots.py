import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
from beanie import PydanticObjectId
from app.models.plot import Plot
from app.models.user_data import UserData
from app.main import app
from pydantic import HttpUrl
import json


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


@pytest.fixture
def serializable_plot(mock_plot):
    """Create a JSON-serializable version of the mock plot."""
    plot_dict = mock_plot.model_dump()
    # Convert ObjectId fields to strings
    plot_dict["id"] = str(plot_dict["id"])

    # Handle datasetId properly - extract the ID from the Link object
    if hasattr(plot_dict["datasetId"], "id"):
        # If it's a Link object, extract the ID
        plot_dict["datasetId"] = str(plot_dict["datasetId"].id)
    elif isinstance(plot_dict["datasetId"], PydanticObjectId):
        # If it's already a PydanticObjectId, convert to string
        plot_dict["datasetId"] = str(plot_dict["datasetId"])
    else:
        # If it's already a string or something else, use as is
        plot_dict["datasetId"] = str(plot_dict["datasetId"])

    # Convert datetime to ISO string
    plot_dict["generatedAt"] = plot_dict["generatedAt"].isoformat()
    # Convert HttpUrl to string
    plot_dict["imageUrl"] = str(plot_dict["imageUrl"])
    print(f"DEBUG: serializable_plot: {json.dumps(plot_dict, indent=2)}")
    return plot_dict


@pytest.fixture(autouse=True)
def mock_auth():
    """Mock the authentication dependency."""
    # Save the current override
    original_override = app.dependency_overrides.get(
        "app.api.routes.plot.get_current_user_id"
    )

    # Set up the override
    app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
        lambda: "test_user_123"
    )
    print("DEBUG: Authentication dependency overridden with test_user_123")

    yield

    # Restore the original override
    if original_override is not None:
        app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
            original_override
        )
        print("DEBUG: Original authentication dependency restored")
    else:
        app.dependency_overrides.pop("app.api.routes.plot.get_current_user_id", None)
        print("DEBUG: Authentication dependency removed")


@pytest.mark.asyncio
async def test_create_plot(async_authorized_client, mock_plot, serializable_plot):
    """Test creating a new plot."""
    with patch("app.models.plot.Plot.insert") as mock_insert:
        mock_insert.return_value = None

        # Create a new plot data with proper datasetId
        plot_data = serializable_plot.copy()
        # Ensure datasetId is a string representation of an ObjectId
        if not isinstance(plot_data["datasetId"], str) or not plot_data[
            "datasetId"
        ].startswith("67"):
            plot_data["datasetId"] = str(PydanticObjectId())

        print(
            f"DEBUG: Sending POST request to /api/plots/ with data: {json.dumps(plot_data, indent=2)}"
        )
        response = await async_test_client.post("/api/plots/", json=plot_data)
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert data["userId"] == mock_plot.userId
        assert data["type"] == mock_plot.type
        assert data["imageUrl"] == str(mock_plot.imageUrl)
        assert data["metadata"] == mock_plot.metadata


@pytest.mark.asyncio
async def test_get_plots_for_user(async_authorized_client, mock_plot):
    """Test getting all plots for a user."""
    with patch("app.models.plot.Plot.find") as mock_find:
        # Create an AsyncMock for to_list() that returns a list
        mock_find.return_value.to_list = AsyncMock(return_value=[mock_plot])
        print("DEBUG: Mocked Plot.find().to_list() to return a list with one plot")

        print("DEBUG: Sending GET request to /api/plots/")
        response = await async_test_client.get("/api/plots/")
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["userId"] == mock_plot.userId
        assert data[0]["type"] == mock_plot.type


@pytest.mark.asyncio
async def test_get_plot_by_id(async_authorized_client, mock_plot):
    """Test getting a plot by ID."""
    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = mock_plot
        print(f"DEBUG: Mocked Plot.get() to return a plot with ID: {mock_plot.id}")

        print(f"DEBUG: Sending GET request to /api/plots/{mock_plot.id}")
        response = await async_test_client.get(f"/api/plots/{mock_plot.id}")
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert data["userId"] == mock_plot.userId
        assert data["type"] == mock_plot.type
        assert data["imageUrl"] == str(mock_plot.imageUrl)


@pytest.mark.asyncio
async def test_get_plot_by_id_not_found(async_authorized_client):
    """Test getting a non-existent plot by ID."""
    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = None
        non_existent_id = PydanticObjectId()
        print(f"DEBUG: Mocked Plot.get() to return None for ID: {non_existent_id}")

        # Override the authentication for this test
        original_override = app.dependency_overrides.get(
            "app.api.routes.plot.get_current_user_id"
        )
        app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
            lambda: "test_user_123"
        )

        try:
            print(f"DEBUG: Sending GET request to /api/plots/{non_existent_id}")
            response = await async_test_client.get(f"/api/plots/{non_existent_id}")
            print(f"DEBUG: Response status code: {response.status_code}")
            print(f"DEBUG: Response body: {response.text}")

            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"
        finally:
            # Restore the original override
            if original_override is not None:
                app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
                    original_override
                )
            else:
                app.dependency_overrides.pop(
                    "app.api.routes.plot.get_current_user_id", None
                )


@pytest.mark.asyncio
async def test_update_plot(async_authorized_client, mock_plot, serializable_plot):
    """Test updating a plot."""
    with patch("app.models.plot.Plot.get") as mock_get, patch(
        "app.models.plot.Plot.save"
    ) as mock_save:
        mock_get.return_value = mock_plot
        mock_save.return_value = None
        print(f"DEBUG: Mocked Plot.get() to return a plot with ID: {mock_plot.id}")

        # Create updated data with proper datasetId
        updated_data = serializable_plot.copy()
        # Ensure datasetId is a string representation of an ObjectId
        if not isinstance(updated_data["datasetId"], str) or not updated_data[
            "datasetId"
        ].startswith("67"):
            updated_data["datasetId"] = str(PydanticObjectId())

        updated_data["type"] = "scatter"
        updated_data["metadata"] = {"title": "Updated Plot"}
        print(
            f"DEBUG: Sending PUT request to /api/plots/{mock_plot.id} with data: {json.dumps(updated_data, indent=2)}"
        )

        response = await async_test_client.put(
            f"/api/plots/{mock_plot.id}", json=updated_data
        )
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "scatter"
        assert data["metadata"]["title"] == "Updated Plot"


@pytest.mark.asyncio
async def test_update_plot_not_found(async_authorized_client, mock_plot, serializable_plot):
    """Test updating a non-existent plot."""
    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = None
        print(f"DEBUG: Mocked Plot.get() to return None for ID: {mock_plot.id}")

        # Override the authentication for this test
        original_override = app.dependency_overrides.get(
            "app.api.routes.plot.get_current_user_id"
        )
        app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
            lambda: "test_user_123"
        )

        try:
            # Create updated data with proper datasetId
            updated_data = serializable_plot.copy()
            # Ensure datasetId is a string representation of an ObjectId
            if not isinstance(updated_data["datasetId"], str) or not updated_data[
                "datasetId"
            ].startswith("67"):
                updated_data["datasetId"] = str(PydanticObjectId())

            print(
                f"DEBUG: Sending PUT request to /api/plots/{mock_plot.id} with data: {json.dumps(updated_data, indent=2)}"
            )
            response = await async_test_client.put(
                f"/api/plots/{mock_plot.id}", json=updated_data
            )
            print(f"DEBUG: Response status code: {response.status_code}")
            print(f"DEBUG: Response body: {response.text}")

            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"
        finally:
            # Restore the original override
            if original_override is not None:
                app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
                    original_override
                )
            else:
                app.dependency_overrides.pop(
                    "app.api.routes.plot.get_current_user_id", None
                )


@pytest.mark.asyncio
async def test_delete_plot(async_authorized_client, mock_plot):
    """Test deleting a plot."""
    with patch("app.models.plot.Plot.get") as mock_get, patch(
        "app.models.plot.Plot.delete"
    ) as mock_delete:
        mock_get.return_value = mock_plot
        mock_delete.return_value = None
        print(f"DEBUG: Mocked Plot.get() to return a plot with ID: {mock_plot.id}")

        print(f"DEBUG: Sending DELETE request to /api/plots/{mock_plot.id}")
        response = await async_test_client.delete(f"/api/plots/{mock_plot.id}")
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 200
        assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_plot_not_found(async_authorized_client):
    """Test deleting a non-existent plot."""
    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = None
        non_existent_id = PydanticObjectId()
        print(f"DEBUG: Mocked Plot.get() to return None for ID: {non_existent_id}")

        # Override the authentication for this test
        original_override = app.dependency_overrides.get(
            "app.api.routes.plot.get_current_user_id"
        )
        app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
            lambda: "test_user_123"
        )

        try:
            print(f"DEBUG: Sending DELETE request to /api/plots/{non_existent_id}")
            response = await async_test_client.delete(f"/api/plots/{non_existent_id}")
            print(f"DEBUG: Response status code: {response.status_code}")
            print(f"DEBUG: Response body: {response.text}")

            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"
        finally:
            # Restore the original override
            if original_override is not None:
                app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
                    original_override
                )
            else:
                app.dependency_overrides.pop(
                    "app.api.routes.plot.get_current_user_id", None
                )


@pytest.mark.asyncio
async def test_get_plot_with_different_user(async_authorized_client, mock_plot):
    """Test getting a plot with a different user ID."""
    with patch("app.models.plot.Plot.get") as mock_get:
        mock_get.return_value = mock_plot
        print(f"DEBUG: Mocked Plot.get() to return a plot with ID: {mock_plot.id}")

        # Save the current override and replace it temporarily
        original_override = app.dependency_overrides.get(
            "app.api.routes.plot.get_current_user_id"
        )
        app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
            lambda: "different_user_123"
        )
        print("DEBUG: Authentication dependency overridden with different_user_123")

        try:
            print(f"DEBUG: Sending GET request to /api/plots/{mock_plot.id}")
            response = await async_test_client.get(f"/api/plots/{mock_plot.id}")
            print(f"DEBUG: Response status code: {response.status_code}")
            print(f"DEBUG: Response body: {response.text}")

            assert response.status_code == 200
            data = response.json()
            assert data["userId"] == mock_plot.userId
        finally:
            # Restore the original override
            if original_override is not None:
                app.dependency_overrides["app.api.routes.plot.get_current_user_id"] = (
                    original_override
                )
                print("DEBUG: Original authentication dependency restored")
            else:
                app.dependency_overrides.pop(
                    "app.api.routes.plot.get_current_user_id", None
                )
                print("DEBUG: Authentication dependency removed")


@pytest.mark.asyncio
async def test_create_plot_with_dataset_link(
    async_authorized_client, mock_plot, serializable_plot
):
    """Test creating a plot with a dataset link."""
    with patch("app.models.plot.Plot.insert") as mock_insert:
        mock_insert.return_value = None

        # Create a plot with a dataset link
        plot_data = serializable_plot.copy()
        # Ensure datasetId is a string representation of an ObjectId
        plot_data["datasetId"] = str(PydanticObjectId())
        print(
            f"DEBUG: Sending POST request to /api/plots/ with data: {json.dumps(plot_data, indent=2)}"
        )

        response = await async_test_client.post("/api/plots/", json=plot_data)
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert data["userId"] == mock_plot.userId
        assert data["type"] == mock_plot.type
        assert "datasetId" in data
