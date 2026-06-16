import pytest
from unittest.mock import patch, MagicMock, PropertyMock, AsyncMock
import json
from app.models.visualization_cache import (
    HistogramData,
    BoxplotData,
    CorrelationMatrixData,
)
from app.main import app
from beanie import PydanticObjectId, Link
from app.models.user_data import UserData
from app.auth.nextauth_auth import get_current_user_id


@pytest.fixture
def mock_auth():
    """Override the authentication dependency for testing."""

    async def fake_get_current_user_id() -> str:
        return "test_user_123"

    print("DEBUG: Overriding authentication dependency")
    app.dependency_overrides[get_current_user_id] = fake_get_current_user_id
    yield
    print("DEBUG: Restoring authentication dependency")
    app.dependency_overrides.pop(get_current_user_id, None)


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


@pytest.fixture
def mock_dataset_id():
    """Create a mock dataset ID for testing."""
    return PydanticObjectId()


@pytest.fixture
def mock_dataset():
    """Create a mock dataset for testing."""
    dataset = MagicMock(spec=UserData)
    dataset.id = PydanticObjectId()
    dataset.s3_url = "s3://test-bucket/test-file.csv"

    # Create a proper Link object using the correct syntax with document_class parameter
    dataset.link = Link(dataset.id, document_class=UserData)

    # Make id accessible as a property and ensure it returns a PydanticObjectId
    # This is needed because the service uses this to create Link objects
    type(dataset).id = PropertyMock(return_value=dataset.id)

    # Add any other required attributes
    dataset.user_id = "test_user_123"
    dataset.filename = "test_file.csv"
    dataset.num_rows = 100
    dataset.num_columns = 5
    dataset.data_schema = [
        {"name": "col1", "type": "numeric"},
        {"name": "col2", "type": "numeric"},
        {"name": "col3", "type": "numeric"},
        {"name": "col4", "type": "numeric"},
        {"name": "col5", "type": "numeric"},
    ]

    return dataset


@pytest.fixture
def mock_dataframe():
    """Create a mock DataFrame for testing."""
    import pandas as pd

    # Create a simple DataFrame with test data
    return pd.DataFrame(
        {
            "col1": [1, 2, 3, 4, 5],
            "col2": [5, 4, 3, 2, 1],
            "test_column": [1.5, 2.5, 3.5, 4.5, 5.5],
        }
    )


@pytest.mark.asyncio
async def test_get_histogram(
    async_authorized_client,
    mock_histogram_data,
    setup_database,
    mock_auth,
    mock_dataset_id,
    mock_dataset,
):
    """Test getting histogram data for a numeric column."""
    dataset_id = mock_dataset_id
    column_name = "test_column"
    num_bins = 50

    print(
        f"DEBUG: Testing GET request to /api/v1/visualizations/histogram/{dataset_id}/{column_name}"
    )

    # Mock UserData.get to return a valid dataset, then mock the cache function
    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.generate_and_cache_histogram",
        return_value=mock_histogram_data.model_dump(),
    ):
        print(
            f"DEBUG: Mocked generate_and_cache_histogram to return: {json.dumps(mock_histogram_data.model_dump(), indent=2)}"
        )

        response = await async_authorized_client.get(
            f"/api/v1/visualizations/histogram/{dataset_id}/{column_name}",
            params={"num_bins": num_bins},
            headers={"Authorization": "Bearer test_token"},
        )

        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert "bins" in data
        assert "counts" in data
        assert "bin_edges" in data
        assert len(data["bins"]) == len(mock_histogram_data.bins)
        assert len(data["counts"]) == len(mock_histogram_data.counts)


@pytest.mark.asyncio
async def test_get_histogram_error(
    async_authorized_client, setup_database, mock_auth, mock_dataset_id, mock_dataset
):
    """Test getting histogram data with invalid parameters."""
    dataset_id = mock_dataset_id
    column_name = "test_column"
    num_bins = -1  # Invalid number of bins

    print(
        f"DEBUG: Testing GET request to /api/v1/visualizations/histogram/{dataset_id}/{column_name} with invalid num_bins={num_bins}"
    )

    # Mock UserData.get to return a valid dataset, then mock the cache function to raise ValueError
    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.generate_and_cache_histogram",
        side_effect=ValueError("Invalid number of bins"),
    ):
        print("DEBUG: Mocked generate_and_cache_histogram to raise ValueError")

        response = await async_authorized_client.get(
            f"/api/v1/visualizations/histogram/{dataset_id}/{column_name}",
            params={"num_bins": num_bins},
            headers={"Authorization": "Bearer test_token"},
        )

        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 400
        assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_boxplot(
    async_authorized_client,
    mock_boxplot_data,
    setup_database,
    mock_auth,
    mock_dataset_id,
    mock_dataset,
):
    """Test getting boxplot data for a numeric column."""
    dataset_id = mock_dataset_id
    column_name = "test_column"

    print(
        f"DEBUG: Testing GET request to /api/v1/visualizations/boxplot/{dataset_id}/{column_name}"
    )

    # Mock UserData.get to return a valid dataset, then mock the cache function
    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.generate_and_cache_boxplot",
        return_value=mock_boxplot_data.model_dump(),
    ):
        print(
            f"DEBUG: Mocked generate_and_cache_boxplot to return: {json.dumps(mock_boxplot_data.model_dump(), indent=2)}"
        )

        response = await async_authorized_client.get(
            f"/api/v1/visualizations/boxplot/{dataset_id}/{column_name}",
            headers={"Authorization": "Bearer test_token"},
        )

        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

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
async def test_get_boxplot_error(
    async_authorized_client, setup_database, mock_auth, mock_dataset_id, mock_dataset
):
    """Test getting boxplot data with invalid parameters."""
    dataset_id = mock_dataset_id
    column_name = "test_column"

    print(
        f"DEBUG: Testing GET request to /api/v1/visualizations/boxplot/{dataset_id}/{column_name} with error"
    )

    # Mock UserData.get to return a valid dataset, then mock the cache function to raise ValueError
    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.generate_and_cache_boxplot",
        side_effect=ValueError("Column not found"),
    ):
        print("DEBUG: Mocked generate_and_cache_boxplot to raise ValueError")

        response = await async_authorized_client.get(
            f"/api/v1/visualizations/boxplot/{dataset_id}/{column_name}",
            headers={"Authorization": "Bearer test_token"},
        )

        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_get_correlation_matrix(
    async_authorized_client,
    mock_correlation_data,
    setup_database,
    mock_auth,
    mock_dataset_id,
    mock_dataset,
):
    """Test getting correlation matrix data."""
    dataset_id = mock_dataset_id

    print(f"DEBUG: Testing GET request to /api/v1/visualizations/correlation/{dataset_id}")

    # Mock UserData.get to return a valid dataset, then mock the cache function
    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.generate_and_cache_correlation_matrix",
        return_value=mock_correlation_data.model_dump(),
    ):
        print(
            f"DEBUG: Mocked generate_and_cache_correlation_matrix to return: {json.dumps(mock_correlation_data.model_dump(), indent=2)}"
        )

        response = await async_authorized_client.get(
            f"/api/v1/visualizations/correlation/{dataset_id}",
            headers={"Authorization": "Bearer test_token"},
        )

        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert "matrix" in data
        assert "columns" in data
        assert len(data["matrix"]) == len(mock_correlation_data.matrix)
        assert len(data["columns"]) == len(mock_correlation_data.columns)


@pytest.mark.asyncio
async def test_get_correlation_matrix_error(
    async_authorized_client, setup_database, mock_auth, mock_dataset_id, mock_dataset
):
    """Test error handling for correlation matrix data."""
    dataset_id = mock_dataset_id

    print(f"DEBUG: Testing GET request to /api/v1/visualizations/correlation/{dataset_id}")

    # Mock UserData.get to return a valid dataset, then mock the cache function to raise ValueError
    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.generate_and_cache_correlation_matrix",
        side_effect=ValueError("Invalid data for correlation matrix"),
    ):
        print("DEBUG: Mocked generate_and_cache_correlation_matrix to raise ValueError")

        response = await async_authorized_client.get(
            f"/api/v1/visualizations/correlation/{dataset_id}",
            headers={"Authorization": "Bearer test_token"},
        )

        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_get_histogram_server_error(
    async_authorized_client, setup_database, mock_auth, mock_dataset_id, mock_dataset
):
    """Test server error when getting histogram data."""
    dataset_id = mock_dataset_id
    column_name = "test_column"

    print(
        f"DEBUG: Testing GET request to /api/v1/visualizations/histogram/{dataset_id}/{column_name} with server error"
    )

    # Mock UserData.get to return a valid dataset, then mock the cache function to raise Exception
    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.generate_and_cache_histogram",
        side_effect=Exception("Server error"),
    ):
        print("DEBUG: Mocked generate_and_cache_histogram to raise Exception")

        response = await async_authorized_client.get(
            f"/api/v1/visualizations/histogram/{dataset_id}/{column_name}",
            headers={"Authorization": "Bearer test_token"},
        )

        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_get_boxplot_server_error(
    async_authorized_client, setup_database, mock_auth, mock_dataset_id, mock_dataset
):
    """Test server error when getting boxplot data."""
    dataset_id = mock_dataset_id
    column_name = "test_column"

    print(
        f"DEBUG: Testing GET request to /api/v1/visualizations/boxplot/{dataset_id}/{column_name} with server error"
    )

    # Mock UserData.get to return a valid dataset, then mock the cache function to raise Exception
    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.generate_and_cache_boxplot",
        side_effect=Exception("Server error"),
    ):
        print("DEBUG: Mocked generate_and_cache_boxplot to raise Exception")

        response = await async_authorized_client.get(
            f"/api/v1/visualizations/boxplot/{dataset_id}/{column_name}",
            headers={"Authorization": "Bearer test_token"},
        )

        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_get_correlation_matrix_server_error(
    async_authorized_client, setup_database, mock_auth, mock_dataset_id, mock_dataset
):
    """Test server error handling for correlation matrix data."""
    dataset_id = mock_dataset_id

    print(f"DEBUG: Testing GET request to /api/v1/visualizations/correlation/{dataset_id}")

    # Mock UserData.get to return a valid dataset, then mock the cache function to raise Exception
    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.generate_and_cache_correlation_matrix",
        side_effect=Exception("Internal server error"),
    ):
        print("DEBUG: Mocked generate_and_cache_correlation_matrix to raise Exception")

        response = await async_authorized_client.get(
            f"/api/v1/visualizations/correlation/{dataset_id}",
            headers={"Authorization": "Bearer test_token"},
        )

        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


def _sample_df():
    """A small DataFrame, mimicking get_dataframe_from_s3's return."""
    import pandas as pd

    return pd.DataFrame({"col1": [1, 2, 3, 4, 5], "col2": [5, 4, 3, 2, 1]})


@pytest.mark.asyncio
async def test_get_scatter_plot_loads_current_data(
    async_authorized_client, setup_database, mock_auth, mock_dataset_id, mock_dataset
):
    """Scatter plot loads via get_dataframe_from_s3 (handles raw keys, s3 URLs,
    and parquet). With no transformed file, it falls back to the original
    upload's s3_url."""
    dataset_id = mock_dataset_id
    mock_dataset.file_path = None  # not yet transformed → use s3_url

    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.get_dataframe_from_s3",
        new=AsyncMock(return_value=_sample_df()),
    ) as mock_get_df:
        response = await async_authorized_client.get(
            f"/api/v1/visualizations/scatter/{dataset_id}/col1/col2",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 5
        assert data["xLabel"] == "col1"
        assert data["yLabel"] == "col2"
        mock_get_df.assert_awaited_once_with(mock_dataset.s3_url)


@pytest.mark.asyncio
async def test_get_scatter_plot_prefers_transformed_file(
    async_authorized_client, setup_database, mock_auth, mock_dataset_id, mock_dataset
):
    """When the dataset has been transformed, visualizations must load the
    current file (file_path), not the original upload."""
    dataset_id = mock_dataset_id
    mock_dataset.file_path = "s3://test-bucket/transformed.parquet"

    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.get_dataframe_from_s3",
        new=AsyncMock(return_value=_sample_df()),
    ) as mock_get_df:
        response = await async_authorized_client.get(
            f"/api/v1/visualizations/scatter/{dataset_id}/col1/col2",
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        mock_get_df.assert_awaited_once_with("s3://test-bucket/transformed.parquet")


@pytest.mark.asyncio
async def test_get_line_chart_loads_current_data(
    async_authorized_client, setup_database, mock_auth, mock_dataset_id, mock_dataset
):
    """Line chart loads current data the same way as scatter."""
    dataset_id = mock_dataset_id
    mock_dataset.file_path = None

    with patch(
        "app.api.routes.visualizations.UserData.get",
        return_value=mock_dataset,
    ), patch(
        "app.api.routes.visualizations.get_dataframe_from_s3",
        new=AsyncMock(return_value=_sample_df()),
    ) as mock_get_df:
        response = await async_authorized_client.get(
            f"/api/v1/visualizations/line/{dataset_id}/col1",
            params={"y_columns": "col2"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 5
        assert data["lines"] == [{"dataKey": "col2", "label": "col2"}]
        mock_get_df.assert_awaited_once_with(mock_dataset.s3_url)
