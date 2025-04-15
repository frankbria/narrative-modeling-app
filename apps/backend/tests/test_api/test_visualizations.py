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
async def test_get_histogram(async_test_client, mock_histogram_data):
    """Test getting histogram data for a numeric column."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"
    num_bins = 50

    with patch(
        "app.services.visualization_cache.generate_and_cache_histogram"
    ) as mock_generate:
        mock_generate.return_value = mock_histogram_data.dict()

        response = await async_test_client.get(
            f"/api/visualizations/histogram/{dataset_id}/{column_name}",
            params={"num_bins": num_bins},
        )

        assert response.status_code == 200
        data = response.json()
        assert "bins" in data
        assert "counts" in data
        assert "bin_edges" in data
        assert len(data["bins"]) == len(mock_histogram_data.bins)
        assert len(data["counts"]) == len(mock_histogram_data.counts)


@pytest.mark.asyncio
async def test_get_histogram_error(async_test_client):
    """Test getting histogram data with invalid parameters."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"
    num_bins = -1  # Invalid number of bins

    with patch(
        "app.services.visualization_cache.generate_and_cache_histogram"
    ) as mock_generate:
        mock_generate.side_effect = ValueError("Invalid number of bins")

        response = await async_test_client.get(
            f"/api/visualizations/histogram/{dataset_id}/{column_name}",
            params={"num_bins": num_bins},
        )

        assert response.status_code == 400
        assert "error" in response.json()


@pytest.mark.asyncio
async def test_get_boxplot(async_test_client, mock_boxplot_data):
    """Test getting boxplot data for a numeric column."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"

    with patch(
        "app.services.visualization_cache.generate_and_cache_boxplot"
    ) as mock_generate:
        mock_generate.return_value = mock_boxplot_data.dict()

        response = await async_test_client.get(
            f"/api/visualizations/boxplot/{dataset_id}/{column_name}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "min" in data
        assert "q1" in data
        assert "median" in data
        assert "q3" in data
        assert "max" in data
        assert "outliers" in data
        assert data["min"] == mock_boxplot_data.min
        assert data["max"] == mock_boxplot_data.max


@pytest.mark.asyncio
async def test_get_boxplot_error(async_test_client):
    """Test getting boxplot data with invalid parameters."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"

    with patch(
        "app.services.visualization_cache.generate_and_cache_boxplot"
    ) as mock_generate:
        mock_generate.side_effect = ValueError("Column not found")

        response = await async_test_client.get(
            f"/api/visualizations/boxplot/{dataset_id}/{column_name}"
        )

        assert response.status_code == 400
        assert "error" in response.json()


@pytest.mark.asyncio
async def test_get_correlation_matrix(async_test_client, mock_correlation_data):
    """Test getting correlation matrix data."""
    dataset_id = "test_dataset_123"

    with patch(
        "app.services.visualization_cache.generate_and_cache_correlation_matrix"
    ) as mock_generate:
        mock_generate.return_value = mock_correlation_data.dict()

        response = await async_test_client.get(
            f"/api/visualizations/correlation/{dataset_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "matrix" in data
        assert "columns" in data
        assert len(data["matrix"]) == len(mock_correlation_data.matrix)
        assert len(data["columns"]) == len(mock_correlation_data.columns)


@pytest.mark.asyncio
async def test_get_correlation_matrix_error(async_test_client):
    """Test getting correlation matrix data with invalid parameters."""
    dataset_id = "test_dataset_123"

    with patch(
        "app.services.visualization_cache.generate_and_cache_correlation_matrix"
    ) as mock_generate:
        mock_generate.side_effect = ValueError("Dataset not found")

        response = await async_test_client.get(
            f"/api/visualizations/correlation/{dataset_id}"
        )

        assert response.status_code == 400
        assert "error" in response.json()


@pytest.mark.asyncio
async def test_get_histogram_server_error(async_test_client):
    """Test server error when getting histogram data."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"

    with patch(
        "app.services.visualization_cache.generate_and_cache_histogram"
    ) as mock_generate:
        mock_generate.side_effect = Exception("Server error")

        response = await async_test_client.get(
            f"/api/visualizations/histogram/{dataset_id}/{column_name}"
        )

        assert response.status_code == 500
        assert "error" in response.json()


@pytest.mark.asyncio
async def test_get_boxplot_server_error(async_test_client):
    """Test server error when getting boxplot data."""
    dataset_id = "test_dataset_123"
    column_name = "test_column"

    with patch(
        "app.services.visualization_cache.generate_and_cache_boxplot"
    ) as mock_generate:
        mock_generate.side_effect = Exception("Server error")

        response = await async_test_client.get(
            f"/api/visualizations/boxplot/{dataset_id}/{column_name}"
        )

        assert response.status_code == 500
        assert "error" in response.json()


@pytest.mark.asyncio
async def test_get_correlation_matrix_server_error(async_test_client):
    """Test server error when getting correlation matrix data."""
    dataset_id = "test_dataset_123"

    with patch(
        "app.services.visualization_cache.generate_and_cache_correlation_matrix"
    ) as mock_generate:
        mock_generate.side_effect = Exception("Server error")

        response = await async_test_client.get(
            f"/api/visualizations/correlation/{dataset_id}"
        )

        assert response.status_code == 500
        assert "error" in response.json()
