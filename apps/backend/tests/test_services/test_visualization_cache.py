import pytest
import json
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock, Mock
from beanie import Link

from app.models.visualization_cache import (
    VisualizationCache,
    HistogramData,
    BoxplotData,
    CorrelationMatrixData)
from app.models.user_data import UserData
from app.services.visualization_cache import (
    get_cached_visualization,
    cache_visualization,
    generate_and_cache_histogram,
    generate_and_cache_boxplot,
    generate_and_cache_correlation_matrix)


@pytest.fixture
def mock_db_session():
    """Create a mock database session for testing."""
    session = MagicMock()
    return session


@pytest.fixture
def sample_histogram_data():
    """Create sample histogram data for testing."""
    return HistogramData(
        bins=[10, 20, 30, 40, 50],
        counts=[5, 10, 15, 20, 25],
        bin_edges=[0, 10, 20, 30, 40, 50])


@pytest.fixture
def sample_boxplot_data():
    """Create sample boxplot data for testing."""
    return BoxplotData(min=0, q1=10, median=25, q3=40, max=50, outliers=[60, 70, 80])


@pytest.fixture
def sample_correlation_matrix():
    """Create sample correlation matrix data for testing."""
    return CorrelationMatrixData(
        columns=["col1", "col2", "col3"],
        matrix=[[1.0, 0.5, 0.3], [0.5, 1.0, 0.7], [0.3, 0.7, 1.0]])


@pytest.fixture
def mock_dataset():
    """Create a mock UserData object for testing."""
    return UserData(
        id="test-dataset-123",
        user_id="test-user-123",
        filename="test.csv",
        s3_url="https://test-bucket.s3.amazonaws.com/test.csv",
        num_rows=100,
        num_columns=5,
        data_schema=[],
        created_at=datetime.now(),
        original_filename="test.csv",
        updated_at=datetime.now())


class TestVisualizationCache:
    """Test suite for visualization cache functionality."""

    @pytest.mark.asyncio
    async def test_get_cached_visualization_histogram(
        self, sample_histogram_data, mock_dataset
    ):
        """Test retrieving a cached histogram visualization."""
        # Setup
        dataset_id = mock_dataset.id
        column_name = "test_column"
        visualization_type = "histogram"

        # Create a mock cache entry
        mock_cache = AsyncMock(spec=VisualizationCache)
        mock_cache.data = sample_histogram_data.model_dump()
        mock_cache.dataset_id = Link(mock_dataset, document_class=UserData)

        # Mock the find_one method
        with patch(
            "app.services.visualization_cache.VisualizationCache.find_one",
            new_callable=AsyncMock) as mock_find_one:
            mock_find_one.return_value = mock_cache

            # Execute
            result = await get_cached_visualization(
                dataset_id, visualization_type, column_name
            )

            # Assert
            assert result == sample_histogram_data.model_dump()
            mock_find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_visualization_boxplot(
        self, sample_boxplot_data, mock_dataset
    ):
        """Test retrieving a cached boxplot visualization."""
        # Setup

        # Create a mock cache entry
        mock_cache.data = sample_boxplot_data.model_dump()
        mock_cache.dataset_id = Link(mock_dataset, document_class=UserData)

        # Mock the find_one method
        with patch(
            "app.services.visualization_cache.VisualizationCache.find_one"
        ) as mock_find_one:
            mock_find_one.return_value = mock_cache

            # Execute
            result = await check_cache(
                dataset_id, visualization_type, column_name
            )

            # Assert
            assert result == sample_boxplot_data.model_dump()
            mock_find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_visualization_correlation(
        self, sample_correlation_matrix, mock_dataset
    ):
        """Test retrieving a cached correlation matrix visualization."""
        # Setup

        # Create a mock cache entry
        mock_cache.data = sample_correlation_matrix.model_dump()
        mock_cache.dataset_id = Link(mock_dataset, document_class=UserData)

        # Mock the find_one method
        with patch(
            "app.services.visualization_cache.VisualizationCache.find_one"
        ) as mock_find_one:
            mock_find_one.return_value = mock_cache

            # Execute
            result = await check_cache(
                dataset_id, "correlation_matrix", None
            )

            # Assert
            assert result == sample_correlation_matrix.model_dump()
            mock_find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_visualization_histogram(
        self, sample_histogram_data, mock_dataset
    ):
        """Test caching a histogram visualization."""
        # Setup

        # Mock the database operations
        with patch(
            "app.services.visualization_cache.VisualizationCache.find_one",
            mock_find_one.return_value = None

            with patch(
                "app.services.visualization_cache.VisualizationCache.insert",
                new_callable=AsyncMock) as mock_insert:
                mock_insert.return_value = None

                # Execute
                result = await cache_visualization(
                    dataset_id, visualization_type, column_name, sample_histogram_data
                )

                # Assert
                assert result is not None
                mock_insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_visualization_boxplot(self, sample_boxplot_data, mock_dataset):
        """Test caching a boxplot visualization."""
        # Setup

        # Mock the database operations
        with patch(
            "app.services.visualization_cache.VisualizationCache.find_one",
            mock_find_one.return_value = None

            with patch(
                "app.services.visualization_cache.VisualizationCache.insert",
                mock_insert.return_value = None

                # Execute
                    dataset_id, visualization_type, column_name, sample_boxplot_data
                )

                # Assert
                assert result is not None
                mock_insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_visualization_correlation(
        self, sample_correlation_matrix, mock_dataset
    ):
        """Test caching a correlation matrix visualization."""
        # Setup

        # Mock the database operations
        with patch(
            "app.services.visualization_cache.VisualizationCache.find_one",
            mock_find_one.return_value = None

            with patch(
                "app.services.visualization_cache.VisualizationCache.insert",
                mock_insert.return_value = None

                # Execute
                    dataset_id, visualization_type, None, sample_correlation_matrix
                )

                # Assert
                assert result is not None
                mock_insert.assert_called_once()
