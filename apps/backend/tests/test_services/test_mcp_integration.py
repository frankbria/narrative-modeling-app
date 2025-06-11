"""
Tests for MCP integration service
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.mcp_integration import (
    MCPIntegrationService,
    MCPConfig,
    MCPToolRequest,
    MCPToolResponse,
    MCPAnalysisResponse
)


@pytest.fixture
def mcp_config():
    """Create test MCP configuration"""
    return MCPConfig(
        host="localhost",
        port=10000,
        timeout=5,
        api_key="test_api_key"
    )


@pytest.fixture
def mcp_service(mcp_config):
    """Create MCP integration service instance"""
    return MCPIntegrationService(config=mcp_config)


@pytest.fixture
def sample_schema():
    """Sample schema for testing"""
    return {
        "column_count": 5,
        "row_count": 100,
        "columns": [
            {"name": "id", "data_type": "integer"},
            {"name": "value", "data_type": "float"},
            {"name": "category", "data_type": "categorical"}
        ]
    }


@pytest.fixture
def sample_statistics():
    """Sample statistics for testing"""
    return {
        "quality_score": 0.85,
        "column_statistics": [
            {"column_name": "id", "mean": 50.5},
            {"column_name": "value", "mean": 100.0}
        ]
    }


@pytest.fixture
def sample_quality_report():
    """Sample quality report for testing"""
    return {
        "overall_quality_score": 0.85,
        "recommendations": ["Address missing values", "Remove duplicates"],
        "dimension_scores": {
            "completeness": 0.9,
            "validity": 0.8
        }
    }


class TestMCPIntegrationService:
    """Test MCP integration functionality"""

    async def test_health_check_success(self, mcp_service):
        """Test successful health check"""
        with patch.object(mcp_service.client, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            result = await mcp_service.check_health()
            
            assert result is True
            mock_get.assert_called_once_with("http://localhost:10000/health")

    async def test_health_check_failure(self, mcp_service):
        """Test failed health check"""
        with patch.object(mcp_service.client, 'get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            
            result = await mcp_service.check_health()
            
            assert result is False

    async def test_execute_tool_success(self, mcp_service):
        """Test successful tool execution"""
        request = MCPToolRequest(
            tool_name="test_tool",
            parameters={"param1": "value1"},
            context={"file_id": "123"}
        )
        
        with patch.object(mcp_service.client, 'post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "tool_name": "test_tool",
                "result": {"output": "success"},
                "error": None,
                "execution_time": 1.5
            }
            mock_post.return_value = mock_response
            
            result = await mcp_service.execute_tool(request)
            
            assert isinstance(result, MCPToolResponse)
            assert result.tool_name == "test_tool"
            assert result.result == {"output": "success"}
            assert result.error is None
            assert result.execution_time == 1.5

    async def test_execute_tool_failure(self, mcp_service):
        """Test failed tool execution"""
        request = MCPToolRequest(
            tool_name="failing_tool",
            parameters={}
        )
        
        with patch.object(mcp_service.client, 'post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_response.text = "Internal server error"
            mock_post.return_value = mock_response
            
            result = await mcp_service.execute_tool(request)
            
            assert result.tool_name == "failing_tool"
            assert result.result is None
            assert "Tool execution failed" in result.error
            assert result.execution_time == 0.0

    async def test_analyze_dataset_success(
        self, 
        mcp_service, 
        sample_schema, 
        sample_statistics, 
        sample_quality_report
    ):
        """Test successful dataset analysis"""
        with patch.object(mcp_service, 'execute_tool') as mock_execute:
            # Mock EDA tool response
            eda_response = MCPToolResponse(
                tool_name="eda_summary",
                result={
                    "insights": [
                        {
                            "type": "data_overview",
                            "title": "Dataset Overview",
                            "description": "100 rows with 5 columns"
                        },
                        {
                            "type": "missing_data",
                            "title": "Missing Data Found",
                            "severity": "low",
                            "count": 5
                        }
                    ]
                },
                error=None,
                execution_time=2.0
            )
            
            # Mock visualization tool response
            viz_response = MCPToolResponse(
                tool_name="generate_visualizations",
                result=[
                    {"type": "histogram", "column": "value", "data": {}},
                    {"type": "scatter", "columns": ["id", "value"], "data": {}}
                ],
                error=None,
                execution_time=1.0
            )
            
            mock_execute.side_effect = [eda_response, viz_response]
            
            result = await mcp_service.analyze_dataset(
                file_id="test_file_123",
                schema=sample_schema,
                statistics=sample_statistics,
                quality_report=sample_quality_report,
                sample_data=[{"id": 1, "value": 10.5}],
                analysis_type="comprehensive"
            )
            
            assert isinstance(result, MCPAnalysisResponse)
            assert result.file_id == "test_file_123"
            assert result.analysis_type == "comprehensive"
            assert len(result.insights) == 2
            assert len(result.recommendations) > 0
            assert result.visualizations is not None
            assert len(result.visualizations) == 2
            assert "mcp_version" in result.metadata
            assert result.metadata["tools_used"] == ["eda_summary", "generate_visualizations"]

    async def test_analyze_dataset_with_eda_failure(
        self, 
        mcp_service, 
        sample_schema, 
        sample_statistics, 
        sample_quality_report
    ):
        """Test dataset analysis with EDA tool failure"""
        with patch.object(mcp_service, 'execute_tool') as mock_execute:
            # Mock failed EDA response
            eda_response = MCPToolResponse(
                tool_name="eda_summary",
                result=None,
                error="EDA tool unavailable",
                execution_time=0.0
            )
            
            mock_execute.return_value = eda_response
            
            result = await mcp_service.analyze_dataset(
                file_id="test_file_123",
                schema=sample_schema,
                statistics=sample_statistics,
                quality_report=sample_quality_report,
                sample_data=[],
                analysis_type="summary"
            )
            
            # Should return fallback analysis
            assert result.file_id == "test_file_123"
            assert result.metadata["fallback_mode"] is True
            assert result.metadata["mcp_available"] is False
            assert "MCP server unavailable" in result.recommendations[0]

    async def test_parse_eda_insights(self, mcp_service):
        """Test parsing EDA insights"""
        # Test with proper insights structure
        eda_result = {
            "insights": [
                {"type": "test", "title": "Test Insight"}
            ]
        }
        insights = mcp_service._parse_eda_insights(eda_result)
        assert len(insights) == 1
        assert insights[0]["type"] == "test"
        
        # Test with non-standard structure
        eda_result = {"data": "some data"}
        insights = mcp_service._parse_eda_insights(eda_result)
        assert len(insights) == 1
        assert insights[0]["type"] == "data_overview"
        assert insights[0]["details"]["data"] == "some data"

    async def test_generate_recommendations(self, mcp_service, sample_quality_report):
        """Test recommendation generation"""
        insights = [
            {
                "type": "missing_data",
                "severity": "high"
            },
            {
                "type": "outliers",
                "count": 20
            }
        ]
        
        recommendations = mcp_service._generate_recommendations(
            insights, 
            sample_quality_report
        )
        
        assert len(recommendations) > 0
        assert any("missing data" in rec.lower() for rec in recommendations)
        assert any("outlier" in rec.lower() for rec in recommendations)

    async def test_create_analysis_summary(self, mcp_service, sample_schema, sample_statistics):
        """Test analysis summary creation"""
        insights = [
            {
                "type": "test",
                "title": "Important Finding"
            }
        ]
        
        summary = mcp_service._create_analysis_summary(
            insights,
            sample_schema,
            sample_statistics
        )
        
        assert "100 rows and 5 columns" in summary
        assert "Key finding: Important Finding" in summary
        assert "1 key insights" in summary

    async def test_config_from_environment(self):
        """Test configuration from environment variables"""
        with patch.dict('os.environ', {
            'MCP_HOST': 'test-host',
            'MCP_PORT': '8080',
            'MCP_TIMEOUT': '60',
            'MCP_API_KEY': 'secret-key'
        }):
            config = MCPConfig()
            
            assert config.host == 'test-host'
            assert config.port == 8080
            assert config.timeout == 60
            assert config.api_key == 'secret-key'
            assert config.base_url == 'http://test-host:8080'

    async def test_context_manager(self, mcp_config):
        """Test async context manager functionality"""
        async with MCPIntegrationService(config=mcp_config) as service:
            assert service is not None
            assert service.client is not None
        
        # Client should be closed after exiting context