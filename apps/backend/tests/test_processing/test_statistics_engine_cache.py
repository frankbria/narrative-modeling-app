"""
Tests for statistics engine cache integration
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, patch, Mock
from datetime import datetime
import hashlib
import json

from app.services.data_processing.statistics_engine import StatisticsEngine, DatasetStatistics, ColumnStatistics


class TestStatisticsEngineCache:
    """Test cases for statistics engine cache integration"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = StatisticsEngine()

    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """Test that cache keys are generated consistently"""
        # Create test data
        df = pd.DataFrame({
            'numeric_col': [1, 2, 3, 4, 5],
            'categorical_col': ['A', 'B', 'C', 'A', 'B']
        })
        
        column_types = {
            'numeric_col': 'integer',
            'categorical_col': 'categorical'
        }
        
        # Generate cache key
        cache_key = self.engine._generate_cache_key(df, column_types)
        
        # Verify cache key format
        assert cache_key.startswith("stats:")
        assert len(cache_key) > 10  # Should have hash component
        
        # Verify same data generates same key
        cache_key2 = self.engine._generate_cache_key(df, column_types)
        assert cache_key == cache_key2
        
        # Verify different data generates different key
        df_different = df.copy()
        df_different['numeric_col'] = df_different['numeric_col'] * 2
        cache_key3 = self.engine._generate_cache_key(df_different, column_types)
        assert cache_key != cache_key3

    @pytest.mark.asyncio
    async def test_cache_miss_and_set(self):
        """Test cache miss behavior and data caching"""
        # Create test data
        df = pd.DataFrame({
            'numeric_col': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'categorical_col': ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'B', 'C', 'A'],
            'date_col': pd.date_range('2023-01-01', periods=10)
        })
        
        column_types = {
            'numeric_col': 'integer',
            'categorical_col': 'categorical',
            'date_col': 'datetime'
        }
        
        # Mock cache service for cache miss
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Cache miss
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.data_processing.statistics_engine.cache_service', mock_cache):
            # Generate statistics
            stats = await self.engine.calculate_statistics(df, column_types)
            
            # Verify cache was checked
            mock_cache.get.assert_called_once()
            
            # Verify cache was set with correct TTL (2 hours = 7200 seconds)
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args
            assert call_args[0][2] == 7200  # TTL
            
            # Verify statistics structure
            assert isinstance(stats, DatasetStatistics)
            assert stats.row_count == 10
            assert stats.column_count == 3
            assert len(stats.column_statistics) == 3

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Test cache hit behavior"""
        # Create test data
        df = pd.DataFrame({
            'numeric_col': [1, 2, 3, 4, 5],
            'categorical_col': ['A', 'B', 'C', 'A', 'B']
        })
        
        column_types = {
            'numeric_col': 'integer',
            'categorical_col': 'categorical'
        }
        
        # Create mock cached statistics
        cached_stats = {
            "row_count": 5,
            "column_count": 2,
            "column_statistics": [
                {
                    "column_name": "numeric_col",
                    "data_type": "integer",
                    "total_count": 5,
                    "null_count": 0,
                    "null_percentage": 0.0,
                    "unique_count": 5,
                    "unique_percentage": 100.0,
                    "mean": 3.0,
                    "median": 3.0,
                    "std_dev": 1.58,
                    "min_value": 1.0,
                    "max_value": 5.0,
                    "q1": 2.0,
                    "q3": 4.0,
                    "most_frequent_values": []
                },
                {
                    "column_name": "categorical_col",
                    "data_type": "categorical",
                    "total_count": 5,
                    "null_count": 0,
                    "null_percentage": 0.0,
                    "unique_count": 3,
                    "unique_percentage": 60.0,
                    "most_frequent_values": []
                }
            ],
            "memory_usage_mb": 0.001,
            "correlation_matrix": None,
            "missing_value_summary": {},
            "calculated_at": datetime.utcnow().isoformat()
        }
        
        # Mock cache service for cache hit
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=cached_stats)  # Cache hit
        mock_cache.set = AsyncMock()
        
        with patch('app.services.data_processing.statistics_engine.cache_service', mock_cache):
            # Generate statistics
            stats = await self.engine.calculate_statistics(df, column_types)
            
            # Verify cache was checked
            mock_cache.get.assert_called_once()
            
            # Verify cache was NOT set (because we hit cache)
            mock_cache.set.assert_not_called()
            
            # Verify returned statistics match cached data
            assert stats.row_count == 5
            assert stats.column_count == 2
            assert len(stats.column_statistics) == 2

    @pytest.mark.asyncio
    async def test_cache_failure_graceful_degradation(self):
        """Test that statistics engine works when cache fails"""
        # Create test data
        df = pd.DataFrame({
            'numeric_col': [1, 2, 3, 4, 5],
            'categorical_col': ['A', 'B', 'C', 'A', 'B']
        })
        
        column_types = {
            'numeric_col': 'integer',
            'categorical_col': 'categorical'
        }
        
        # Mock cache service to simulate failures
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(side_effect=Exception("Redis connection error"))
        mock_cache.set = AsyncMock(side_effect=Exception("Redis connection error"))
        
        with patch('app.services.data_processing.statistics_engine.cache_service', mock_cache):
            # Should still generate statistics despite cache failures
            stats = await self.engine.generate_statistics(df, column_types)
            
            # Verify statistics were computed correctly
            assert isinstance(stats, DatasetStatistics)
            assert stats.row_count == 5
            assert stats.column_count == 2
            
            # Verify cache operations were attempted
            mock_cache.get.assert_called_once()
            mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_with_different_data_types(self):
        """Test caching with various data types"""
        # Create test data with multiple data types
        df = pd.DataFrame({
            'int_col': [1, 2, 3, 4, 5],
            'float_col': [1.1, 2.2, 3.3, 4.4, 5.5],
            'str_col': ['a', 'b', 'c', 'd', 'e'],
            'bool_col': [True, False, True, False, True],
            'date_col': pd.date_range('2023-01-01', periods=5),
            'datetime_col': pd.date_range('2023-01-01 10:00:00', periods=5, freq='H')
        })
        
        column_types = {
            'int_col': 'numeric',
            'float_col': 'numeric',
            'str_col': 'categorical',
            'bool_col': 'boolean',
            'date_col': 'date',
            'datetime_col': 'datetime'
        }
        
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Cache miss
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.data_processing.statistics_engine.cache_service', mock_cache):
            stats = await self.engine.generate_statistics(df, column_types)
            
            # Verify all columns were processed
            assert len(stats.column_statistics) == 6
            
            # Verify cache operations
            mock_cache.get.assert_called_once()
            mock_cache.set.assert_called_once()
            
            # Check that cached data includes all column statistics
            cached_data = mock_cache.set.call_args[0][1]  # Second argument to set()
            assert isinstance(cached_data, dict)
            assert cached_data["total_columns"] == 6

    @pytest.mark.asyncio
    async def test_cache_with_missing_values(self):
        """Test caching statistics with missing values"""
        # Create test data with NaN values
        df = pd.DataFrame({
            'numeric_with_nan': [1, 2, np.nan, 4, 5],
            'categorical_with_nan': ['A', 'B', None, 'A', 'B'],
            'all_nan': [np.nan, np.nan, np.nan, np.nan, np.nan]
        })
        
        column_types = {
            'numeric_with_nan': 'numeric',
            'categorical_with_nan': 'categorical',
            'all_nan': 'numeric'
        }
        
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Cache miss
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.data_processing.statistics_engine.cache_service', mock_cache):
            stats = await self.engine.generate_statistics(df, column_types)
            
            # Verify null counts are calculated correctly
            numeric_stats = next(cs for cs in stats.column_stats if cs.column_name == 'numeric_with_nan')
            assert numeric_stats.null_count == 1
            assert numeric_stats.null_percentage == 20.0
            
            categorical_stats = next(cs for cs in stats.column_stats if cs.column_name == 'categorical_with_nan')
            assert categorical_stats.null_count == 1
            assert categorical_stats.null_percentage == 20.0
            
            all_nan_stats = next(cs for cs in stats.column_stats if cs.column_name == 'all_nan')
            assert all_nan_stats.null_count == 5
            assert all_nan_stats.null_percentage == 100.0

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_data_change(self):
        """Test that cache is properly invalidated when data changes"""
        # Create initial data
        df1 = pd.DataFrame({
            'numeric_col': [1, 2, 3, 4, 5],
            'categorical_col': ['A', 'B', 'C', 'A', 'B']
        })
        
        # Create modified data
        df2 = pd.DataFrame({
            'numeric_col': [1, 2, 3, 4, 5, 6],  # Added one more row
            'categorical_col': ['A', 'B', 'C', 'A', 'B', 'C']
        })
        
        column_types = {
            'numeric_col': 'integer',
            'categorical_col': 'categorical'
        }
        
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Always cache miss
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.data_processing.statistics_engine.cache_service', mock_cache):
            # Generate statistics for first dataset
            stats1 = await self.engine.generate_statistics(df1, column_types)
            
            # Generate statistics for second dataset
            stats2 = await self.engine.generate_statistics(df2, column_types)
            
            # Verify different cache keys were used (called get twice)
            assert mock_cache.get.call_count == 2
            assert mock_cache.set.call_count == 2
            
            # Verify different statistics
            assert stats1.total_rows == 5
            assert stats2.total_rows == 6

    @pytest.mark.asyncio
    async def test_cache_serialization_deserialization(self):
        """Test that complex statistics objects are properly serialized/deserialized"""
        # Create test data
        df = pd.DataFrame({
            'numeric_col': [1, 2, 3, 4, 5],
            'categorical_col': ['A', 'B', 'C', 'A', 'B']
        })
        
        column_types = {
            'numeric_col': 'integer',
            'categorical_col': 'categorical'
        }
        
        # First call - cache miss, compute and cache
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.data_processing.statistics_engine.cache_service', mock_cache):
            stats1 = await self.engine.generate_statistics(df, column_types)
            
            # Get the cached data
            cached_data = mock_cache.set.call_args[0][1]
            
            # Simulate cache hit with the cached data
            mock_cache.get = AsyncMock(return_value=cached_data)
            mock_cache.set.reset_mock()
            
            # Second call - cache hit
            stats2 = await self.engine.generate_statistics(df, column_types)
            
            # Verify set was not called on cache hit
            mock_cache.set.assert_not_called()
            
            # Verify statistics match
            assert stats1.total_rows == stats2.total_rows
            assert stats1.total_columns == stats2.total_columns
            assert len(stats1.column_stats) == len(stats2.column_stats)
            
            # Verify specific column statistics match
            for cs1, cs2 in zip(stats1.column_stats, stats2.column_stats):
                assert cs1.column_name == cs2.column_name
                assert cs1.data_type == cs2.data_type
                assert cs1.null_count == cs2.null_count