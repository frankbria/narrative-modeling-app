"""
Tests for AI analysis API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.main import app
from app.models.user_data import UserData
from app.services.mcp_integration import MCPAnalysisResponse


@pytest.fixture
def mock_user_data_with_analysis():
    """Mock user data object with processed data"""
    return UserData(
        id="test-file-123",
        user_id="test-user-123",
        filename="test_data.csv",
        file_path="s3://test-bucket/test-file-123.csv",
        file_size=1024,
        file_type="csv",
        upload_date=datetime.utcnow(),
        is_processed=True,
        schema={
            "row_count": 100,
            "column_count": 5,
            "columns": [
                {"name": "id", "type": "integer"},
                {"name": "value", "type": "float"},
                {"name": "category", "type": "string"}
            ]
        },
        statistics={
            "columns": {
                "value": {"mean": 50.0, "std": 10.0}
            }
        },
        quality_report={
            "overall_quality_score": 0.85,
            "issues": ["Some missing values in 'category' column"]
        }
    )


@pytest.fixture
def mock_ai_summary():
    """Mock AI summary response"""
    return {
        "summary": "This dataset contains 100 rows and 5 columns with transaction data.",
        "key_insights": [
            "The average transaction value is $50",
            "There are 3 distinct categories",
            "20% of records have missing category values"
        ],
        "recommendations": [
            "Fill missing category values",
            "Consider normalizing the value column",
            "Add date/time information for trend analysis"
        ],
        "data_quality_assessment": "Good overall quality with minor missing data issues"
    }


class TestAIAnalysisAPI:
    """Test suite for AI analysis endpoints"""
    
    @pytest.mark.asyncio
    async def test_analyze_dataset_success(self, authorized_client, mock_user_data_with_analysis):
        """Test successful AI analysis of dataset"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data_with_analysis
            
            with patch('app.services.mcp_integration.mcp_service.analyze_dataset', new_callable=AsyncMock) as mock_analyze:
                mock_analyze.return_value = MCPAnalysisResponse(
                    file_id="test-file-123",
                    analysis_type="comprehensive",
                    summary="Comprehensive analysis of the dataset shows good data quality.",
                    insights=[
                        {"type": "data_overview", "title": "Dataset Overview", "description": "100 rows, 5 columns"},
                        {"type": "quality", "title": "Data Quality", "description": "85% quality score"}
                    ],
                    recommendations=["Address missing values", "Consider feature engineering"],
                    visualizations=None,
                    metadata={"execution_time": 1.5}
                )
                
                response = authorized_client.post("/api/v1/ai/analyze/test-file-123")
                
                assert response.status_code == 200
                data = response.json()
                assert "summary" in data
                assert "insights" in data
                assert len(data["insights"]) == 2
                assert "recommendations" in data
                assert len(data["recommendations"]) == 2
    
    @pytest.mark.asyncio
    async def test_analyze_dataset_not_processed(self, authorized_client):
        """Test analyzing unprocessed dataset"""
        mock_user_data = UserData(
            id="test-file-123",
            user_id="test-user-123",
            filename="test_data.csv",
            file_path="s3://test-bucket/test-file-123.csv",
            file_size=1024,
            file_type="csv",
            upload_date=datetime.utcnow(),
            is_processed=False
        )
        
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data
            
            response = authorized_client.post("/api/v1/ai/analyze/test-file-123")
            
            assert response.status_code == 400
            assert "Dataset must be processed" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_summarize_dataset_success(self, authorized_client, mock_user_data_with_analysis, mock_ai_summary):
        """Test AI dataset summarization"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data_with_analysis
            
            with patch('app.services.dataset_summarization.DatasetSummarizer.summarize', new_callable=AsyncMock) as mock_summarize:
                mock_summarize.return_value = mock_ai_summary
                
                response = authorized_client.get("/api/v1/ai/summarize/test-file-123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["summary"] == mock_ai_summary["summary"]
                assert len(data["key_insights"]) == 3
                assert len(data["recommendations"]) == 3
                assert "data_quality_assessment" in data
    
    @pytest.mark.asyncio
    async def test_summarize_dataset_not_found(self, authorized_client):
        """Test summarizing non-existent dataset"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            response = authorized_client.get("/api/v1/ai/summarize/non-existent-123")
            
            assert response.status_code == 404
            assert "Dataset not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_analyze_with_custom_prompts(self, authorized_client, mock_user_data_with_analysis):
        """Test AI analysis with custom prompts"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data_with_analysis
            
            with patch('app.services.mcp_integration.mcp_service.analyze_dataset', new_callable=AsyncMock) as mock_analyze:
                mock_analyze.return_value = MCPAnalysisResponse(
                    file_id="test-file-123",
                    analysis_type="comprehensive",
                    summary="Analysis focused on business metrics.",
                    insights=[
                        {"type": "business", "title": "Business Insights", "description": "Revenue trends identified"}
                    ],
                    recommendations=["Optimize pricing strategy"],
                    visualizations=None,
                    metadata={"execution_time": 2.0}
                )
                
                response = authorized_client.post(
                    "/api/v1/ai/analyze/test-file-123",
                    json={
                        "analysis_type": "comprehensive",
                        "include_visualization": False,
                        "custom_prompts": ["Focus on business metrics", "Identify revenue patterns"]
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "Business Insights" in str(data["insights"])
    
    @pytest.mark.asyncio
    async def test_analyze_with_mcp_failure(self, authorized_client, mock_user_data_with_analysis):
        """Test AI analysis when MCP service fails"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data_with_analysis
            
            with patch('app.services.mcp_integration.mcp_service.analyze_dataset', new_callable=AsyncMock) as mock_analyze:
                # Simulate MCP failure - should return fallback analysis
                mock_analyze.side_effect = Exception("MCP service unavailable")
                
                response = authorized_client.post("/api/v1/ai/analyze/test-file-123")
                
                # Should still succeed with fallback
                assert response.status_code == 200
                data = response.json()
                assert "summary" in data
                assert "insights" in data
    
    @pytest.mark.asyncio
    async def test_summarize_with_cache(self, authorized_client, mock_user_data_with_analysis, mock_ai_summary):
        """Test that summarization uses cache when available"""
        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user_data_with_analysis
            
            with patch('app.services.dataset_summarization.DatasetSummarizer.summarize', new_callable=AsyncMock) as mock_summarize:
                mock_summarize.return_value = mock_ai_summary
                
                # First call
                response1 = authorized_client.get("/api/v1/ai/summarize/test-file-123")
                assert response1.status_code == 200
                
                # Second call should use cache (mock should only be called once)
                response2 = authorized_client.get("/api/v1/ai/summarize/test-file-123")
                assert response2.status_code == 200
                
                # Verify summarize was called only once
                assert mock_summarize.call_count == 1