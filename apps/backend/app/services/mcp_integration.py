"""
MCP (Model Context Protocol) integration service for AI tool orchestration
"""

import json
import logging
import os
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _result_payload(result: Any) -> Any:
    """Extract a tool's return value from an MCP ``CallToolResult`` (#506).

    FastMCP serves a tool's dict return as ``structuredContent`` (and mirrors it into
    a text block). A non-object return is wrapped as ``{"result": ...}``; a dict return
    passes through. Fall back to JSON-parsing the first text block, then raw text.
    """
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        if set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    for content in getattr(result, "content", None) or []:
        text = getattr(content, "text", None)
        if text is not None:
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                return text
    return None


class MCPToolRequest(BaseModel):
    """Request model for MCP tool execution"""
    tool_name: str
    parameters: dict[str, Any]
    context: dict[str, Any] | None = None


class MCPToolResponse(BaseModel):
    """Response model from MCP tool execution"""
    tool_name: str
    result: Any
    error: str | None = None
    execution_time: float


class MCPAnalysisRequest(BaseModel):
    """Request for comprehensive data analysis via MCP"""
    file_id: str
    analysis_type: str = Field(default="comprehensive", pattern="^(comprehensive|statistical|quality|summary)$")
    include_visualization: bool = True
    custom_prompts: list[str] | None = None


class MCPAnalysisResponse(BaseModel):
    """Response from MCP analysis"""
    file_id: str
    analysis_type: str
    summary: str
    insights: list[dict[str, Any]]
    recommendations: list[str]
    visualizations: list[dict[str, Any]] | None = None
    metadata: dict[str, Any]


@dataclass
class MCPConfig:
    """Configuration for MCP server connection"""
    host: str | None = None
    port: int | None = None
    timeout: int | None = None
    api_key: str | None = None
    
    def __post_init__(self) -> None:
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
    """Client for the FastMCP server, which exposes ``eda_summary_tool`` over MCP-on-SSE.

    #506: the previous client POSTed to REST paths FastMCP never exposes, ``await``ed
    httpx's synchronous ``.json()``, and sent a tool name/arg shape the server does not
    register — three independent bugs, so every call failed at the transport level. This
    speaks real MCP over SSE via the ``mcp`` SDK's ``sse_client`` + ``ClientSession``.
    """

    def __init__(self, config: MCPConfig | None = None):
        self.config = config or MCPConfig()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    @property
    def _sse_url(self) -> str:
        # FastMCP's sse_app() serves the SSE stream at /sse (main.py: mcp.sse_app()).
        return f"{self.config.base_url}/sse"

    def _headers(self) -> dict[str, str]:
        # The server fails closed without a bearer token (BearerAuthMiddleware).
        if self.config.api_key:
            return {"Authorization": f"Bearer {self.config.api_key}"}
        return {}

    async def _open_session(self, stack: AsyncExitStack) -> ClientSession:
        read, write = await stack.enter_async_context(
            sse_client(
                self._sse_url,
                headers=self._headers(),
                timeout=float(self.config.timeout or 30),
            )
        )
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return session

    async def check_health(self) -> bool:
        """True iff an MCP session opens and the server registers ``eda_summary_tool``."""
        try:
            async with AsyncExitStack() as stack:
                session = await self._open_session(stack)
                tools = await session.list_tools()
                return any(t.name == "eda_summary_tool" for t in tools.tools)
        except Exception as e:
            logger.error(f"MCP health check failed: {e}")
            return False

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool over SSE and return its structured payload.

        Raises on transport or tool error so callers can fall back.
        """
        async with AsyncExitStack() as stack:
            session = await self._open_session(stack)
            result = await session.call_tool(tool_name, arguments)
            if getattr(result, "isError", False):
                text = "; ".join(
                    getattr(c, "text", "") for c in (getattr(result, "content", None) or [])
                )
                raise RuntimeError(f"MCP tool {tool_name} returned an error: {text}")
            return _result_payload(result)

    async def execute_tool(self, request: MCPToolRequest) -> MCPToolResponse:
        """Execute a named MCP tool over SSE (thin wrapper over ``_call_tool``)."""
        started = time.monotonic()
        try:
            payload = await self._call_tool(request.tool_name, request.parameters)
            return MCPToolResponse(
                tool_name=request.tool_name,
                result=payload,
                error=None,
                execution_time=time.monotonic() - started,
            )
        except Exception as e:
            logger.error(f"Error executing MCP tool {request.tool_name}: {e}")
            return MCPToolResponse(
                tool_name=request.tool_name,
                result=None,
                error=str(e),
                execution_time=time.monotonic() - started,
            )

    async def analyze_dataset(
        self,
        dataset_id: str,
        user_id: str,
        schema: dict[str, Any] | None = None,
        statistics: dict[str, Any] | None = None,
        quality_report: dict[str, Any] | None = None,
        sample_data: list[dict[str, Any]] | None = None,
        analysis_type: str = "comprehensive"
    ) -> MCPAnalysisResponse:
        """
        Perform dataset analysis via the MCP ``eda_summary_tool``.

        The tool reads the dataset from S3 **server-side** from the owner-scoped
        ``(dataset_id, user_id)`` — the client sends only those, never the dataset
        contents (#506). ``schema``/``statistics``/``quality_report`` are used only to
        enrich the summary and the fallback, not sent to the tool.

        Args:
            dataset_id: The owner's dataset id (``str(UserData.id)``).
            user_id: The requesting user id; the server authorizes ownership.
            schema/statistics/quality_report/sample_data: local context for the
                summary + fallback (optional).
            analysis_type: Type of analysis to report.

        Returns:
            MCPAnalysisResponse with insights and recommendations, or a fallback.
        """
        schema = schema or {}
        statistics = statistics or {}
        quality_report = quality_report or {}
        try:
            # The tool takes a single `params` object (EdaInput: dataset_id, user_id).
            eda_response = await self.execute_tool(
                MCPToolRequest(
                    tool_name="eda_summary_tool",
                    parameters={"params": {"dataset_id": dataset_id, "user_id": user_id}},
                )
            )

            if eda_response.error:
                logger.error(f"EDA summary tool call failed: {eda_response.error}")
                return self._create_fallback_analysis(dataset_id, analysis_type, schema, statistics)

            # The tool returns {"success": bool, "data"|"message": ...} — never fabricate
            # analysis from a failed/empty result (#506/#539); fall back honestly.
            payload = eda_response.result
            if not isinstance(payload, dict) or not payload.get("success"):
                message = payload.get("message") if isinstance(payload, dict) else None
                logger.error(f"EDA summary tool reported failure: {message}")
                return self._create_fallback_analysis(dataset_id, analysis_type, schema, statistics)

            eda_data = payload.get("data", {})
            insights = self._parse_eda_insights(eda_data)
            recommendations = self._generate_recommendations(insights, quality_report)
            summary = self._create_analysis_summary(insights, schema, statistics)

            return MCPAnalysisResponse(
                file_id=dataset_id,
                analysis_type=analysis_type,
                summary=summary,
                insights=insights,
                recommendations=recommendations,
                visualizations=None,
                metadata={
                    "tools_used": ["eda_summary_tool"],
                    "execution_time": eda_response.execution_time,
                    "mcp_available": True,
                }
            )

        except Exception as e:
            logger.error(f"MCP analysis failed: {e}")
            return self._create_fallback_analysis(dataset_id, analysis_type, schema, statistics)
    
    def _parse_eda_insights(self, eda_result: Any) -> list[dict[str, Any]]:
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
        insights: list[dict[str, Any]], 
        quality_report: dict[str, Any]
    ) -> list[str]:
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
        insights: list[dict[str, Any]], 
        schema: dict[str, Any],
        statistics: dict[str, Any]
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
        schema: dict[str, Any],
        statistics: dict[str, Any]
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