"""Per-data-type tests for the visualization cache service.

Covers MongoDB-fallback retrieval and new-entry caching for each payload
shape (histogram, boxplot, correlation matrix). Service-level interaction
tests (Redis hit/miss, error handling, TTL) live in
test_visualization_cache_integration.py.
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
from beanie import PydanticObjectId

from app.models.visualization_cache import (
    HistogramData,
    BoxplotData,
    CorrelationMatrixData)
from app.services.visualization_cache import (
    get_cached_visualization,
    cache_visualization)

pytestmark = pytest.mark.unit


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
    """A lightweight stand-in for the UserData document."""
    dataset = Mock()
    dataset.id = PydanticObjectId()
    return dataset


@pytest.fixture
def mock_redis_miss():
    """Cache service that misses on get and accepts set."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    return cache


async def _get_round_trip(mock_redis_miss, mock_dataset, payload, viz_type, column):
    """Retrieve `payload` through the MongoDB-fallback path."""
    mock_cache_entry = Mock()
    mock_cache_entry.data = payload

    with patch('app.services.visualization_cache.cache_service', mock_redis_miss), \
         patch('app.services.visualization_cache.UserData.get', new=AsyncMock(return_value=mock_dataset)), \
         patch('app.services.visualization_cache.VisualizationCache.find_one',
               new=AsyncMock(return_value=mock_cache_entry)) as mock_find_one:
        result = await get_cached_visualization(str(mock_dataset.id), viz_type, column)

    mock_find_one.assert_called_once()
    # The lookup must be scoped to this dataset's id (DBRef storage)
    query_filter = mock_find_one.call_args.args[0]
    assert query_filter["dataset_id.$id"] == mock_dataset.id
    assert query_filter["visualization_type"] == viz_type
    return result


class TestGetCachedVisualization:
    """MongoDB-fallback retrieval for each visualization data type."""

    @pytest.mark.asyncio
    async def test_get_cached_visualization_histogram(
        self, mock_redis_miss, mock_dataset, sample_histogram_data
    ):
        payload = sample_histogram_data.model_dump()
        result = await _get_round_trip(
            mock_redis_miss, mock_dataset, payload, "histogram", "test_column")
        assert result == payload

    @pytest.mark.asyncio
    async def test_get_cached_visualization_boxplot(
        self, mock_redis_miss, mock_dataset, sample_boxplot_data
    ):
        payload = sample_boxplot_data.model_dump()
        result = await _get_round_trip(
            mock_redis_miss, mock_dataset, payload, "boxplot", "test_column")
        assert result == payload

    @pytest.mark.asyncio
    async def test_get_cached_visualization_correlation(
        self, mock_redis_miss, mock_dataset, sample_correlation_matrix
    ):
        payload = sample_correlation_matrix.model_dump()
        result = await _get_round_trip(
            mock_redis_miss, mock_dataset, payload, "correlation", None)
        assert result == payload


async def _cache_new_entry(mock_redis_miss, mock_dataset, payload, viz_type, column):
    """Store `payload` as a new cache entry and return the saved mock."""
    saved_entry = Mock()
    saved_entry.save = AsyncMock()

    with patch('app.services.visualization_cache.cache_service', mock_redis_miss), \
         patch('app.services.visualization_cache.UserData.get', new=AsyncMock(return_value=mock_dataset)), \
         patch('app.services.visualization_cache.VisualizationCache') as mock_viz_class:
        mock_viz_class.find_one = AsyncMock(return_value=None)
        mock_viz_class.return_value = saved_entry

        result = await cache_visualization(str(mock_dataset.id), viz_type, payload, column)

    saved_entry.save.assert_called_once()
    constructor_kwargs = mock_viz_class.call_args.kwargs
    assert constructor_kwargs["visualization_type"] == viz_type
    assert constructor_kwargs["data"] == payload
    return result


class TestCacheVisualization:
    """New-entry caching for each visualization data type."""

    @pytest.mark.asyncio
    async def test_cache_visualization_histogram(
        self, mock_redis_miss, mock_dataset, sample_histogram_data
    ):
        result = await _cache_new_entry(
            mock_redis_miss, mock_dataset,
            sample_histogram_data.model_dump(), "histogram", "test_column")
        assert result is not None

    @pytest.mark.asyncio
    async def test_cache_visualization_boxplot(
        self, mock_redis_miss, mock_dataset, sample_boxplot_data
    ):
        result = await _cache_new_entry(
            mock_redis_miss, mock_dataset,
            sample_boxplot_data.model_dump(), "boxplot", "test_column")
        assert result is not None

    @pytest.mark.asyncio
    async def test_cache_visualization_correlation(
        self, mock_redis_miss, mock_dataset, sample_correlation_matrix
    ):
        result = await _cache_new_entry(
            mock_redis_miss, mock_dataset,
            sample_correlation_matrix.model_dump(), "correlation", None)
        assert result is not None
