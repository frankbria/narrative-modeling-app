"""
Tests for visualization cache service
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, patch, Mock
from beanie import PydanticObjectId
from datetime import datetime

from app.services.visualization_cache import (
    get_cached_visualization,
    cache_visualization,
    generate_and_cache_histogram,
    generate_and_cache_boxplot,
    generate_and_cache_correlation_matrix
)
from app.models.user_data import UserData
from app.models.visualization_cache import VisualizationCache


class TestVisualizationCache:
    """Test cases for visualization cache service"""

    @pytest.mark.asyncio
    async def test_get_cached_visualization_redis_hit(self):
        """Test getting cached visualization from Redis"""
        dataset_id = str(PydanticObjectId())
        visualization_type = "histogram"
        column_name = "numeric_col"
        
        # Mock cached data
        cached_data = {
            "bins": [1.0, 2.0, 3.0, 4.0, 5.0],
            "counts": [2, 3, 2, 1, 2],
            "bin_edges": [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        }
        
        # Mock cache service for Redis hit
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=cached_data)
        
        with patch('app.services.visualization_cache.cache_service', mock_cache):
            result = await get_cached_visualization(dataset_id, visualization_type, column_name)
            
            # Verify Redis was checked
            expected_key = f"viz:{dataset_id}:{visualization_type}:{column_name}"
            mock_cache.get.assert_called_once_with(expected_key)
            
            # Verify cached data was returned
            assert result == cached_data

    @pytest.mark.asyncio
    async def test_get_cached_visualization_mongodb_fallback(self, setup_database):
        """Test fallback to MongoDB when Redis cache misses"""
        dataset_id = str(PydanticObjectId())
        visualization_type = "boxplot"
        column_name = "numeric_col"
        
        # Mock dataset
        mock_dataset = Mock()
        mock_dataset.id = PydanticObjectId(dataset_id)
        
        # Mock visualization cache entry
        cached_data = {
            "min": 1.0,
            "q1": 2.0,
            "median": 3.0,
            "q3": 4.0,
            "max": 5.0,
            "outliers": []
        }
        
        mock_viz_cache = Mock()
        mock_viz_cache.data = cached_data
        
        # Mock cache service for Redis miss
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Redis miss
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.visualization_cache.cache_service', mock_cache), \
             patch('app.services.visualization_cache.UserData.get', return_value=mock_dataset), \
             patch('app.services.visualization_cache.VisualizationCache.find_one', return_value=mock_viz_cache):
            
            result = await get_cached_visualization(dataset_id, visualization_type, column_name)
            
            # Verify Redis was checked first
            mock_cache.get.assert_called_once()
            
            # Verify data was cached in Redis for next time
            mock_cache.set.assert_called_once_with(
                f"viz:{dataset_id}:{visualization_type}:{column_name}",
                cached_data,
                ttl=3600
            )
            
            # Verify MongoDB data was returned
            assert result == cached_data

    @pytest.mark.asyncio
    async def test_get_cached_visualization_not_found(self, setup_database):
        """Test when visualization is not found in either cache"""
        dataset_id = str(PydanticObjectId())
        visualization_type = "correlation"
        
        # Mock dataset
        mock_dataset = Mock()
        mock_dataset.id = PydanticObjectId(dataset_id)
        
        # Mock cache service for Redis miss
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Redis miss
        
        with patch('app.services.visualization_cache.cache_service', mock_cache), \
             patch('app.services.visualization_cache.UserData.get', return_value=mock_dataset), \
             patch('app.services.visualization_cache.VisualizationCache.find_one', return_value=None):
            
            result = await get_cached_visualization(dataset_id, visualization_type)
            
            # Verify result is None
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_visualization_new_entry(self, setup_database):
        """Test caching new visualization data"""
        dataset_id = str(PydanticObjectId())
        visualization_type = "histogram"
        column_name = "numeric_col"
        
        data = {
            "bins": [1.0, 2.0, 3.0, 4.0, 5.0],
            "counts": [2, 3, 2, 1, 2],
            "bin_edges": [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        }
        
        # Mock dataset
        mock_dataset = Mock()
        mock_dataset.id = PydanticObjectId(dataset_id)
        
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock(return_value=True)
        
        # Mock new visualization cache entry
        mock_viz_cache = Mock()
        mock_viz_cache.save = AsyncMock()
        
        with patch('app.services.visualization_cache.cache_service', mock_cache), \
             patch('app.services.visualization_cache.UserData.get', return_value=mock_dataset), \
             patch('app.services.visualization_cache.VisualizationCache.find_one', return_value=None), \
             patch('app.services.visualization_cache.VisualizationCache', return_value=mock_viz_cache):
            
            result = await cache_visualization(dataset_id, visualization_type, data, column_name)
            
            # Verify Redis was updated
            mock_cache.set.assert_called_once_with(
                f"viz:{dataset_id}:{visualization_type}:{column_name}",
                data,
                ttl=3600
            )
            
            # Verify new MongoDB entry was created and saved
            mock_viz_cache.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_and_cache_histogram(self, setup_database):
        """Test histogram generation and caching"""
        dataset_id = str(PydanticObjectId())
        column_name = "numeric_col"
        num_bins = 5
        
        # Mock dataset
        mock_dataset = Mock()
        mock_dataset.id = PydanticObjectId(dataset_id)
        mock_dataset.s3_url = "s3://test-bucket/test-file.csv"
        
        # Create test DataFrame
        test_df = pd.DataFrame({
            'numeric_col': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        })
        
        with patch('app.services.visualization_cache.get_cached_visualization', return_value=None), \
             patch('app.services.visualization_cache.UserData.get', return_value=mock_dataset), \
             patch('pandas.read_csv', return_value=test_df), \
             patch('app.services.visualization_cache.get_file_from_s3', return_value="mock_file_path"), \
             patch('app.services.visualization_cache.cache_visualization') as mock_cache_viz:
            
            result = await generate_and_cache_histogram(dataset_id, column_name, num_bins)
            
            # Verify histogram data structure
            assert "bins" in result
            assert "counts" in result
            assert "bin_edges" in result
            assert len(result["bins"]) == num_bins
            
            # Verify caching was called
            mock_cache_viz.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_and_cache_correlation_matrix(self, setup_database):
        """Test correlation matrix generation and caching"""
        dataset_id = str(PydanticObjectId())
        
        # Mock dataset
        mock_dataset = Mock()
        mock_dataset.id = PydanticObjectId(dataset_id)
        mock_dataset.s3_url = "s3://test-bucket/test-file.csv"
        
        # Create test DataFrame with numeric columns
        test_df = pd.DataFrame({
            'col1': [1, 2, 3, 4, 5],
            'col2': [2, 4, 6, 8, 10],  # Perfect positive correlation with col1
            'col3': [5, 4, 3, 2, 1],   # Perfect negative correlation with col1
            'col4': ['a', 'b', 'c', 'd', 'e']  # Non-numeric column (should be excluded)
        })
        
        with patch('app.services.visualization_cache.get_cached_visualization', return_value=None), \
             patch('app.services.visualization_cache.UserData.get', return_value=mock_dataset), \
             patch('pandas.read_csv', return_value=test_df), \
             patch('app.services.visualization_cache.get_file_from_s3', return_value="mock_file_path"), \
             patch('app.services.visualization_cache.cache_visualization') as mock_cache_viz:
            
            result = await generate_and_cache_correlation_matrix(dataset_id)
            
            # Verify correlation matrix structure
            assert "matrix" in result
            assert "columns" in result
            
            # Verify only numeric columns are included
            assert len(result["columns"]) == 3  # col1, col2, col3 (col4 excluded)
            assert "col4" not in result["columns"]
            
            # Verify matrix dimensions
            assert len(result["matrix"]) == 3
            assert all(len(row) == 3 for row in result["matrix"])
            
            # Verify caching was called
            mock_cache_viz.assert_called_once()

    @pytest.mark.asyncio
    async def test_visualization_cache_error_handling(self, setup_database):
        """Test error handling in visualization cache operations"""
        dataset_id = str(PydanticObjectId())
        
        # Mock cache service to raise errors
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(side_effect=Exception("Redis error"))
        mock_cache.set = AsyncMock(side_effect=Exception("Redis error"))
        
        # Mock dataset
        mock_dataset = Mock()
        mock_dataset.id = PydanticObjectId(dataset_id)
        
        with patch('app.services.visualization_cache.cache_service', mock_cache), \
             patch('app.services.visualization_cache.UserData.get', return_value=mock_dataset), \
             patch('app.services.visualization_cache.VisualizationCache.find_one', return_value=None):
            
            # Should handle Redis errors gracefully
            result = await get_cached_visualization(dataset_id, "histogram", "numeric_col")
            assert result is None

    @pytest.mark.asyncio
    async def test_visualization_cache_ttl_consistency(self, setup_database):
        """Test that TTL is consistently set to 1 hour across all operations"""
        dataset_id = str(PydanticObjectId())
        data = {"test": "data"}
        
        # Mock dataset
        mock_dataset = Mock()
        mock_dataset.id = PydanticObjectId(dataset_id)
        
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.visualization_cache.cache_service', mock_cache), \
             patch('app.services.visualization_cache.UserData.get', return_value=mock_dataset), \
             patch('app.services.visualization_cache.VisualizationCache.find_one', return_value=None), \
             patch('app.services.visualization_cache.VisualizationCache') as mock_viz_cache_class:
            
            mock_viz_cache = Mock()
            mock_viz_cache.save = AsyncMock()
            mock_viz_cache_class.return_value = mock_viz_cache
            
            await cache_visualization(dataset_id, "histogram", data, "col1")
            
            # Verify TTL is set to 3600 seconds (1 hour)
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args
            assert call_args[1]["ttl"] == 3600