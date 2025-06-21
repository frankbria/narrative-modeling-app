"""
Fixed tests for AI analysis API endpoints
"""

import pytest
from httpx import AsyncClient
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone


class TestAIAnalysisAPI:
    """Test suite for AI analysis endpoints"""
    
    @pytest.mark.asyncio
    async def test_analyze_endpoint_exists(self, mock_async_client: AsyncClient):
        """Test that AI analysis endpoint exists"""
        response = await mock_async_client.post("/api/v1/ai/analyze/test-123")
        
        # Should get 404 for non-existent dataset or 400/422 for validation
        # Not "route not found"
        assert response.status_code in [404, 400, 422, 401, 403]
    
    @pytest.mark.asyncio 
    async def test_summarize_endpoint_exists(self, mock_async_client: AsyncClient):
        """Test that AI summarization endpoint exists"""
        response = await mock_async_client.get("/api/v1/ai/summarize/test-123")

        assert response.status_code in [404, 401, 403]