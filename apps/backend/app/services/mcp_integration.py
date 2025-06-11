"""
MCP (Model Context Protocol) integration service for AI tool orchestration
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MCPToolRequest(BaseModel):
    """Request model for MCP tool execution"""
    tool_name: str
    parameters: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


class MCPToolResponse(BaseModel):
    """Response model from MCP tool execution"""
    tool_name: str
    result: Any
    error: Optional[str] = None
    execution_time: float


class MCPAnalysisRequest(BaseModel):
    """Request for comprehensive data analysis via MCP"""
    file_id: str
    analysis_type: str = Field(default="comprehensive", pattern="^(comprehensive|statistical|quality|summary)$")
    include_visualization: bool = True
    custom_prompts: Optional[List[str]] = None


class MCPAnalysisResponse(BaseModel):
    """Response from MCP analysis"""
    file_id: str
    analysis_type: str
    summary: str
    insights: List[Dict[str, Any]]
    recommendations: List[str]
    visualizations: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any]


@dataclass
class MCPConfig:
    """Configuration for MCP server connection"""
    host: str = None
    port: int = None
    timeout: int = None
    api_key: Optional[str] = None
    
    def __post_init__(self):
        if self.host is None:
            self.host = os.getenv("MCP_HOST", "localhost")
        if self.port is None:
            self.port = int(os.getenv("MCP_PORT", "10000"))
        if self.timeout is None:
            self.timeout = int(os.getenv("MCP_TIMEOUT", "30"))
        if self.api_key is None:
            self.api_key = os.getenv("MCP_API_KEY")
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class MCPIntegrationService:
    """Service for integrating with MCP server for AI-powered analysis"""
    
    def __init__(self, config: Optional[MCPConfig] = None):
        self.config = config or MCPConfig()
        self.client = httpx.AsyncClient(timeout=self.config.timeout)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def check_health(self) -> bool:
        """Check if MCP server is healthy"""
        try:
            response = await self.client.get(f"{self.config.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"MCP health check failed: {e}")
            return False
    
    async def execute_tool(self, request: MCPToolRequest) -> MCPToolResponse:
        """Execute a specific MCP tool"""
        try:
            headers = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            response = await self.client.post(
                f"{self.config.base_url}/tools/{request.tool_name}",
                json=request.model_dump(),
                headers=headers
            )
            
            if response.status_code != 200:
                return MCPToolResponse(
                    tool_name=request.tool_name,
                    result=None,
                    error=f"Tool execution failed: {response.text}",
                    execution_time=0.0
                )
            
            data = await response.json()
            return MCPToolResponse(**data)
            
        except Exception as e:
            logger.error(f"Error executing MCP tool {request.tool_name}: {e}")
            return MCPToolResponse(
                tool_name=request.tool_name,
                result=None,
                error=str(e),
                execution_time=0.0
            )
    
    async def analyze_dataset(
        self, 
        file_id: str,
        schema: Dict[str, Any],
        statistics: Dict[str, Any],
        quality_report: Dict[str, Any],
        sample_data: List[Dict[str, Any]],
        analysis_type: str = "comprehensive"
    ) -> MCPAnalysisResponse:
        """
        Perform comprehensive dataset analysis using MCP tools
        
        Args:
            file_id: Identifier for the dataset
            schema: Inferred schema information
            statistics: Calculated statistics
            quality_report: Quality assessment report
            sample_data: Sample rows from the dataset
            analysis_type: Type of analysis to perform
            
        Returns:
            MCPAnalysisResponse with insights and recommendations
        """
        try:
            # Prepare context for MCP tools
            context = {
                "file_id": file_id,
                "schema": schema,
                "statistics": statistics,
                "quality_report": quality_report,
                "sample_data": sample_data[:10]  # Limit sample size
            }
            
            # Execute EDA summary tool
            eda_request = MCPToolRequest(
                tool_name="eda_summary",
                parameters={
                    "schema": schema,
                    "statistics": statistics,
                    "quality_report": quality_report
                },
                context=context
            )
            
            eda_response = await self.execute_tool(eda_request)
            
            if eda_response.error:
                logger.error(f"EDA summary failed: {eda_response.error}")
                # Fallback to basic analysis
                return self._create_fallback_analysis(file_id, analysis_type, schema, statistics)
            
            # Parse EDA results
            insights = self._parse_eda_insights(eda_response.result)
            recommendations = self._generate_recommendations(insights, quality_report)
            
            # Generate visualizations if requested
            visualizations = None
            if analysis_type in ["comprehensive", "statistical"]:
                viz_request = MCPToolRequest(
                    tool_name="generate_visualizations",
                    parameters={
                        "statistics": statistics,
                        "schema": schema,
                        "insights": insights
                    },
                    context=context
                )
                
                viz_response = await self.execute_tool(viz_request)
                if not viz_response.error:
                    visualizations = viz_response.result
            
            # Create summary
            summary = self._create_analysis_summary(insights, schema, statistics)
            
            return MCPAnalysisResponse(
                file_id=file_id,
                analysis_type=analysis_type,
                summary=summary,
                insights=insights,
                recommendations=recommendations,
                visualizations=visualizations,
                metadata={
                    "mcp_version": "1.0",
                    "tools_used": ["eda_summary", "generate_visualizations"] if visualizations else ["eda_summary"],
                    "execution_time": eda_response.execution_time
                }
            )
            
        except Exception as e:
            logger.error(f"MCP analysis failed: {e}")
            return self._create_fallback_analysis(file_id, analysis_type, schema, statistics)
    
    def _parse_eda_insights(self, eda_result: Any) -> List[Dict[str, Any]]:
        """Parse insights from EDA tool response"""
        if isinstance(eda_result, dict) and "insights" in eda_result:
            return eda_result["insights"]
        
        # Default insights structure
        return [
            {
                "type": "data_overview",
                "title": "Dataset Overview",
                "description": "Basic dataset characteristics",
                "details": eda_result if isinstance(eda_result, dict) else {"raw": str(eda_result)}
            }
        ]
    
    def _generate_recommendations(
        self, 
        insights: List[Dict[str, Any]], 
        quality_report: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on insights and quality report"""
        recommendations = []
        
        # Quality-based recommendations
        if quality_report.get("overall_quality_score", 1.0) < 0.8:
            recommendations.append("Consider data cleaning to improve overall quality score")
        
        # Add recommendations from quality report
        if "recommendations" in quality_report:
            recommendations.extend(quality_report["recommendations"][:3])
        
        # Insight-based recommendations
        for insight in insights:
            if insight.get("type") == "missing_data" and insight.get("severity") == "high":
                recommendations.append("Address missing data issues before proceeding with analysis")
            elif insight.get("type") == "outliers" and insight.get("count", 0) > 10:
                recommendations.append("Review and handle outliers in the dataset")
        
        return list(set(recommendations))[:5]  # Unique recommendations, max 5
    
    def _create_analysis_summary(
        self, 
        insights: List[Dict[str, Any]], 
        schema: Dict[str, Any],
        statistics: Dict[str, Any]
    ) -> str:
        """Create a text summary of the analysis"""
        column_count = schema.get("column_count", 0)
        row_count = schema.get("row_count", 0)
        
        summary_parts = [
            f"Dataset contains {row_count:,} rows and {column_count} columns.",
            f"Data quality score: {statistics.get('quality_score', 'N/A')}.",
            f"Found {len(insights)} key insights about the data."
        ]
        
        # Add top insight if available
        if insights:
            top_insight = insights[0]
            summary_parts.append(f"Key finding: {top_insight.get('title', 'Data analysis complete')}")
        
        return " ".join(summary_parts)
    
    def _create_fallback_analysis(
        self,
        file_id: str,
        analysis_type: str,
        schema: Dict[str, Any],
        statistics: Dict[str, Any]
    ) -> MCPAnalysisResponse:
        """Create a fallback analysis when MCP is unavailable"""
        return MCPAnalysisResponse(
            file_id=file_id,
            analysis_type=analysis_type,
            summary="Basic analysis completed without MCP tools.",
            insights=[
                {
                    "type": "fallback",
                    "title": "Basic Data Overview",
                    "description": f"Dataset has {schema.get('row_count', 0)} rows and {schema.get('column_count', 0)} columns"
                }
            ],
            recommendations=["MCP server unavailable - using basic analysis"],
            visualizations=None,
            metadata={"mcp_available": False, "fallback_mode": True}
        )


# Singleton instance
mcp_service = MCPIntegrationService()