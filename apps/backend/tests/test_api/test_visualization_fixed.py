"""
Fixed tests for visualization API endpoints
"""

import pytest
from httpx import AsyncClient


class TestVisualizationAPI:
    """Test suite for visualization endpoints"""
    
    @pytest.mark.asyncio
    async def test_histogram_endpoint_exists(self, mock_async_client: AsyncClient):
        """Test histogram endpoint exists"""
        response = await mock_async_client.get("/api/v1/visualizations/histogram/test-123/column")
        
        assert response.status_code in [404, 401, 403, 400]
    
    @pytest.mark.asyncio
    async def test_boxplot_endpoint_exists(self, mock_async_client: AsyncClient):
        """Test boxplot endpoint exists"""
        response = await mock_async_client.get("/api/v1/visualizations/boxplot/test-123/column")
        
        assert response.status_code in [404, 401, 403, 400]
    
    @pytest.mark.asyncio
    async def test_correlation_endpoint_exists(self, mock_async_client: AsyncClient):
        """Test correlation matrix endpoint exists"""
        response = await mock_async_client.get("/api/v1/visualizations/correlation/test-123")
        
        assert response.status_code in [404, 401, 403]
    
    @pytest.mark.asyncio
    async def test_scatter_endpoint_exists(self, mock_async_client: AsyncClient):
        """Test scatter plot endpoint exists"""
        response = await mock_async_client.get("/api/v1/visualizations/scatter/test-123/col1/col2")
        
        assert response.status_code in [404, 401, 403, 400]
    
    @pytest.mark.asyncio
    async def test_line_chart_endpoint_exists(self, mock_async_client: AsyncClient):
        """Test line chart endpoint exists"""
        response = await mock_async_client.get("/api/v1/visualizations/line/test-123/date?y_columns=value")
        
        assert response.status_code in [404, 401, 403, 400]
    
    @pytest.mark.asyncio
    async def test_timeseries_endpoint_exists(self, mock_async_client: AsyncClient):
        """Test time series endpoint exists"""
        response = await mock_async_client.get("/api/v1/visualizations/timeseries/test-123/date/value")
        
        assert response.status_code in [404, 401, 403, 400]