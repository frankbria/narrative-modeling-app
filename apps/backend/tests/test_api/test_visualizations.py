import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import numpy as np
from app.models.visualization_cache import (
    HistogramData,
    BoxplotData,
    CorrelationMatrixData,
)


@pytest.fixture
def mock_histogram_data():
    """Create mock histogram data for testing."""
    return HistogramData(
        bins=[0, 1, 2, 3, 4, 5], counts=[1, 2, 3, 2, 1], bin_edges=[0, 1, 2, 3, 4, 5, 6]
    )


@pytest.fixture
def mock_boxplot_data():
    """Create mock boxplot data for testing."""
    return BoxplotData(min=0, q1=1, median=2, q3=3, max=4, outliers=[5, 6, 7])


@pytest.fixture
def mock_correlation_data():
    """Create mock correlation matrix data for testing."""
    return CorrelationMatrixData(
        matrix=[[1.0, 0.5], [0.5, 1.0]], columns=["col1", "col2"]
    )


@pytest.mark.asyncio
async def test_get_histogram(test_client: TestClient, mock_histogram_data):
    """Test getting histogram data for a numeric column."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"
    num_bins = 50

    with patch(
        "app.services.visualization_cache.generate_and_cache_histogram"
    ) as mock_generate:
        mock_generate.return_value = mock_histogram_data.dict()

        response = test_client.get(
            f"/api/v1/visualizations/histogram/{dataset_id}/{column_name}",
            params={"num_bins": num_bins},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["bins"] == mock_histogram_data.bins
        assert data["counts"] == mock_histogram_data.counts
        assert data["bin_edges"] == mock_histogram_data.bin_edges


@pytest.mark.asyncio
async def test_get_histogram_error(test_client: TestClient):
    """Test error handling when getting histogram data."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"

    with patch(
        "app.services.visualization_cache.generate_and_cache_histogram"
    ) as mock_generate:
        mock_generate.side_effect = ValueError("Invalid column")

        response = test_client.get(
            f"/api/v1/visualizations/histogram/{dataset_id}/{column_name}"
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid column"


@pytest.mark.asyncio
async def test_get_boxplot(test_client: TestClient, mock_boxplot_data):
    """Test getting boxplot data for a numeric column."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"

    with patch(
        "app.services.visualization_cache.generate_and_cache_boxplot"
    ) as mock_generate:
        mock_generate.return_value = mock_boxplot_data.dict()

        response = test_client.get(
            f"/api/v1/visualizations/boxplot/{dataset_id}/{column_name}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["min"] == mock_boxplot_data.min
        assert data["q1"] == mock_boxplot_data.q1
        assert data["median"] == mock_boxplot_data.median
        assert data["q3"] == mock_boxplot_data.q3
        assert data["max"] == mock_boxplot_data.max
        assert data["outliers"] == mock_boxplot_data.outliers


@pytest.mark.asyncio
async def test_get_boxplot_error(test_client: TestClient):
    """Test error handling when getting boxplot data."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"

    with patch(
        "app.services.visualization_cache.generate_and_cache_boxplot"
    ) as mock_generate:
        mock_generate.side_effect = ValueError("Invalid column")

        response = test_client.get(
            f"/api/v1/visualizations/boxplot/{dataset_id}/{column_name}"
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid column"


@pytest.mark.asyncio
async def test_get_correlation_matrix(test_client: TestClient, mock_correlation_data):
    """Test getting correlation matrix for numeric columns."""
    dataset_id = "test_dataset_123"

    with patch(
        "app.services.visualization_cache.generate_and_cache_correlation_matrix"
    ) as mock_generate:
        mock_generate.return_value = mock_correlation_data.dict()

        response = test_client.get(f"/api/v1/visualizations/correlation/{dataset_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["columns"] == mock_correlation_data.columns
        assert np.array_equal(
            np.array(data["matrix"]), np.array(mock_correlation_data.matrix)
        )


@pytest.mark.asyncio
async def test_get_correlation_matrix_error(test_client: TestClient):
    """Test error handling when getting correlation matrix."""
    dataset_id = "test_dataset_123"

    with patch(
        "app.services.visualization_cache.generate_and_cache_correlation_matrix"
    ) as mock_generate:
        mock_generate.side_effect = ValueError("No numeric columns found")

        response = test_client.get(f"/api/v1/visualizations/correlation/{dataset_id}")

        assert response.status_code == 400
        assert response.json()["detail"] == "No numeric columns found"


@pytest.mark.asyncio
async def test_get_histogram_server_error(test_client: TestClient):
    """Test server error handling when getting histogram data."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"

    with patch(
        "app.services.visualization_cache.generate_and_cache_histogram"
    ) as mock_generate:
        mock_generate.side_effect = Exception("Internal server error")

        response = test_client.get(
            f"/api/v1/visualizations/histogram/{dataset_id}/{column_name}"
        )

        assert response.status_code == 500
        assert "Error generating histogram" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_boxplot_server_error(test_client: TestClient):
    """Test server error handling when getting boxplot data."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"

    with patch(
        "app.services.visualization_cache.generate_and_cache_boxplot"
    ) as mock_generate:
        mock_generate.side_effect = Exception("Internal server error")

        response = test_client.get(
            f"/api/v1/visualizations/boxplot/{dataset_id}/{column_name}"
        )

        assert response.status_code == 500
        assert "Error generating boxplot" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_correlation_matrix_server_error(test_client: TestClient):
    """Test server error handling when getting correlation matrix."""
    dataset_id = "test_dataset_123"

    with patch(
        "app.services.visualization_cache.generate_and_cache_correlation_matrix"
    ) as mock_generate:
        mock_generate.side_effect = Exception("Internal server error")

        response = test_client.get(f"/api/v1/visualizations/correlation/{dataset_id}")

        assert response.status_code == 500
        assert "Error generating correlation matrix" in response.json()["detail"]
