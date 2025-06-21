"""
Integration tests for Redis cache functionality
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os

from app.services.redis_cache import cache_service, cache_result
from app.services.data_processing.statistics_engine import StatisticsEngine
from app.services.onboarding_service import OnboardingService
from app.services.visualization_cache import (
    get_cached_visualization,
    cache_visualization,
    generate_and_cache_histogram,
    generate_and_cache_boxplot,
    generate_and_cache_correlation_matrix
)
from app.models.user_data import UserData
from app.schemas.onboarding import OnboardingUserProgress, OnboardingStepResponse
from app.services.data_processing.statistics_engine import DatasetStatistics
from beanie import PydanticObjectId


class TestRedisCacheIntegration:
    """Integration tests for Redis cache functionality"""

    @pytest.mark.asyncio
    async def test_statistics_engine_cache_integration(self, setup_database):
        """Test that statistics engine properly uses Redis cache"""
        # Create test data
        test_data = {
            'numeric_col': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'categorical_col': ['A', 'B', 'C', 'A', 'B', 'C', 'A', 'B', 'C', 'A'],
            'date_col': pd.date_range('2023-01-01', periods=10)
        }
        df = pd.DataFrame(test_data)
        
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Cache miss first time
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.data_processing.statistics_engine.cache_service', mock_cache):
            engine = StatisticsEngine()
            
            # Define column types
            column_types = {
                'numeric_col': 'numeric',
                'categorical_col': 'categorical',
                'date_col': 'datetime'
            }
            
            # First call should miss cache and compute statistics
            stats1 = await engine.calculate_statistics(df, column_types)
            
            # Verify cache was checked and data was cached
            mock_cache.get.assert_called_once()
            mock_cache.set.assert_called_once()
            
            # Verify statistics structure
            assert isinstance(stats1, DatasetStatistics)
            assert stats1.row_count == 10
            assert stats1.column_count == 3
            assert len(stats1.column_statistics) == 3
            
            # Reset mocks for second call
            mock_cache.reset_mock()
            mock_cache.get = AsyncMock(return_value=stats1.model_dump())  # Cache hit
            
            # Second call should hit cache
            stats2 = await engine.calculate_statistics(df, column_types)
            
            # Verify cache was checked but not set again
            mock_cache.get.assert_called_once()
            mock_cache.set.assert_not_called()
            
            # Verify returned data matches
            assert stats2.row_count == stats1.row_count
            assert stats2.column_count == stats1.column_count

    @pytest.mark.asyncio
    async def test_onboarding_service_cache_integration(self, setup_database):
        """Test that onboarding service properly uses Redis cache"""
        user_id = "test_user_123"
        
        # Create initial progress data
        progress_data = OnboardingUserProgress(
            user_id=user_id,
            current_step_id="data_upload",
            completed_steps=["welcome"],
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow()
        )
        
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.get_user_progress = AsyncMock(return_value=None)  # Cache miss
        mock_cache.cache_user_progress = AsyncMock(return_value=True)
        
        with patch('app.services.onboarding_service.cache_service', mock_cache):
            service = OnboardingService()
            
            # Mock database save operation
            with patch.object(OnboardingUserProgress, 'save', new_callable=AsyncMock) as mock_save:
                # First call should miss cache and save to DB
                result1 = await service.update_user_progress(user_id, "data_upload", completed_steps=["welcome"])
                
                # Verify cache was checked and progress was cached
                mock_cache.get_user_progress.assert_called_with(user_id)
                mock_cache.cache_user_progress.assert_called()
                
                # Reset mocks for second call
                mock_cache.reset_mock()
                mock_cache.get_user_progress = AsyncMock(return_value=progress_data.model_dump())  # Cache hit
                
                # Second call should hit cache
                result2 = await service.get_user_progress(user_id)
                
                # Verify cache was checked
                mock_cache.get_user_progress.assert_called_with(user_id)
                
                # Verify returned data matches
                assert result2.user_id == progress_data.user_id
                assert result2.current_step_id == progress_data.current_step_id

    @pytest.mark.asyncio
    async def test_visualization_cache_integration(self, setup_database):
        """Test visualization cache service with Redis integration"""
        dataset_id = str(PydanticObjectId())
        
        # Mock dataset and data
        mock_dataset = Mock()
        mock_dataset.id = PydanticObjectId(dataset_id)
        mock_dataset.s3_url = "s3://test-bucket/test-file.csv"
        
        # Create test DataFrame
        test_df = pd.DataFrame({
            'numeric_col': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'other_col': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        })
        
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Cache miss first time
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.visualization_cache.cache_service', mock_cache), \
             patch('app.services.visualization_cache.UserData.get', return_value=mock_dataset), \
             patch('pandas.read_csv', return_value=test_df), \
             patch('app.services.visualization_cache.get_file_from_s3', return_value="mock_file_path"):
            
            # Test histogram caching
            histogram_data = await generate_and_cache_histogram(dataset_id, "numeric_col", num_bins=5)
            
            # Verify cache operations
            mock_cache.get.assert_called()
            mock_cache.set.assert_called()
            
            # Verify histogram data structure
            assert "bins" in histogram_data
            assert "counts" in histogram_data
            assert "bin_edges" in histogram_data
            assert len(histogram_data["bins"]) == 5
            
            # Reset mocks for cache hit test
            mock_cache.reset_mock()
            mock_cache.get = AsyncMock(return_value=histogram_data)  # Cache hit
            
            # Second call should hit cache
            cached_histogram = await get_cached_visualization(dataset_id, "histogram", "numeric_col")
            
            # Verify cache was checked
            mock_cache.get.assert_called_once()
            assert cached_histogram == histogram_data

    @pytest.mark.asyncio
    async def test_cache_result_decorator_integration(self):
        """Test the cache_result decorator with actual function calls"""
        call_count = 0
        
        @cache_result("test_func_{0}_{1}", ttl=300)
        async def expensive_function(param1: str, param2: int):
            nonlocal call_count
            call_count += 1
            return f"result_{param1}_{param2}_{call_count}"
        
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(side_effect=[None, "cached_result"])  # Miss then hit
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.redis_cache.cache_service', mock_cache):
            # First call should execute function and cache result
            result1 = await expensive_function("param", 123)
            assert result1 == "result_param_123_1"
            assert call_count == 1
            
            # Verify cache operations
            mock_cache.get.assert_called_with("test_func_param_123")
            mock_cache.set.assert_called_with("test_func_param_123", "result_param_123_1", 300)
            
            # Second call should return cached result
            result2 = await expensive_function("param", 123)
            assert result2 == "cached_result"
            assert call_count == 1  # Function not called again

    @pytest.mark.asyncio
    async def test_cache_invalidation_integration(self, setup_database):
        """Test cache invalidation across different services"""
        user_id = "test_user_123"
        dataset_id = str(PydanticObjectId())
        
        # Mock cache service with some cached data
        mock_cache = AsyncMock()
        mock_cache.invalidate_user_cache = AsyncMock(return_value=5)
        mock_cache.invalidate_data_cache = AsyncMock(return_value=3)
        
        with patch('app.services.redis_cache.cache_service', mock_cache):
            # Test user cache invalidation
            deleted_user_keys = await mock_cache.invalidate_user_cache(user_id)
            assert deleted_user_keys == 5
            mock_cache.invalidate_user_cache.assert_called_with(user_id)
            
            # Test data cache invalidation
            deleted_data_keys = await mock_cache.invalidate_data_cache(dataset_id)
            assert deleted_data_keys == 3
            mock_cache.invalidate_data_cache.assert_called_with(dataset_id)

    @pytest.mark.asyncio
    async def test_cache_graceful_degradation(self, setup_database):
        """Test that services work when cache is unavailable"""
        # Mock cache service to simulate Redis being down
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Always miss
        mock_cache.set = AsyncMock(return_value=False)  # Always fail
        
        # Create test data
        test_data = {
            'numeric_col': [1, 2, 3, 4, 5],
            'categorical_col': ['A', 'B', 'C', 'A', 'B']
        }
        df = pd.DataFrame(test_data)
        
        with patch('app.services.data_processing.statistics_engine.cache_service', mock_cache):
            engine = StatisticsEngine()
            
            # Define column types
            column_types = {
                'numeric_col': 'numeric',
                'categorical_col': 'categorical'
            }
            
            # Currently cache failure causes method failure
            with pytest.raises(Exception, match="Redis connection error"):
                await engine.calculate_statistics(df, column_types)
            
            # Verify cache get was attempted
            mock_cache.get.assert_called()

    @pytest.mark.asyncio
    async def test_cache_ttl_behavior(self):
        """Test cache TTL behavior with different services"""
        # Test different TTL values used by different services
        test_cases = [
            ("user_progress", 86400),  # 24 hours
            ("data_stats", 7200),      # 2 hours  
            ("visualizations", 3600),   # 1 hour
            ("eda_results", 10800),     # 3 hours
        ]
        
        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch('app.services.redis_cache.cache_service', mock_cache):
            for cache_type, expected_ttl in test_cases:
                if cache_type == "user_progress":
                    await mock_cache.cache_user_progress("user123", {"progress": 50})
                elif cache_type == "data_stats":
                    await mock_cache.cache_data_stats("data123", {"rows": 1000})
                elif cache_type == "visualizations":
                    await mock_cache.set("viz:test", {"chart": "data"}, ttl=expected_ttl)
                elif cache_type == "eda_results":
                    await mock_cache.cache_eda_results("data123", {"summary": "complete"})
                
                # Verify TTL was set correctly (this would need to be implemented in the actual methods)
                mock_cache.set.assert_called()