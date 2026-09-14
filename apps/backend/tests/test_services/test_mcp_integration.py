"""Tests for the MCP integration service (#506).

The previous suite mocked an httpx ``AsyncClient`` and an ``AsyncMock`` response so the
broken ``await response.json()`` (httpx's ``.json()`` is sync) succeeded and the wrong
REST transport / tool name / arg shape went unnoticed. This suite pins the real MCP
contract: the client calls the tool named ``eda_summary_tool`` with a single ``params``
object ``{dataset_id, user_id}`` over the MCP session, and maps the tool's
``{"success": ..., "data"|"message": ...}`` result honestly (no fabrication on failure).

Transport is covered end-to-end by ``test_mcp_integration_sse_localstack.py`` (AC5).
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.mcp_integration import (
    MCPAnalysisResponse,
    MCPConfig,
    MCPIntegrationService,
    MCPToolRequest,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mcp_service():
    return MCPIntegrationService(
        config=MCPConfig(host="localhost", port=10000, timeout=5, api_key="test_api_key")
    )


def test_sse_url_and_bearer_header():
    svc = MCPIntegrationService(config=MCPConfig(host="h", port=1234, api_key="k"))
    assert svc._sse_url == "http://h:1234/sse"  # FastMCP serves the stream at /sse
    assert svc._headers() == {"Authorization": "Bearer k"}
    # No key -> no header (server will 401; we don't send a placeholder)
    assert MCPIntegrationService(config=MCPConfig(host="h", port=1, api_key=None))._headers() == {}


async def test_execute_tool_calls_the_named_tool_with_arguments(mcp_service):
    with patch.object(mcp_service, "_call_tool", new=AsyncMock(return_value={"ok": 1})) as call:
        resp = await mcp_service.execute_tool(
            MCPToolRequest(tool_name="eda_summary_tool", parameters={"params": {"a": 1}})
        )
    call.assert_awaited_once_with("eda_summary_tool", {"params": {"a": 1}})
    assert resp.error is None and resp.result == {"ok": 1}
    assert resp.execution_time >= 0


async def test_execute_tool_reports_transport_error(mcp_service):
    with patch.object(mcp_service, "_call_tool", new=AsyncMock(side_effect=RuntimeError("boom"))):
        resp = await mcp_service.execute_tool(
            MCPToolRequest(tool_name="eda_summary_tool", parameters={})
        )
    assert resp.result is None and "boom" in resp.error


async def test_analyze_dataset_calls_eda_summary_tool_with_owner_scoped_params(mcp_service):
    """The core #506 fix: correct tool NAME and ARG SHAPE — the client sends only
    (dataset_id, user_id) wrapped in `params`, never the dataset contents."""
    captured = {}

    async def fake_call_tool(name, arguments):
        captured["name"] = name
        captured["arguments"] = arguments
        return {"success": True, "data": {"insights": [{"type": "overview", "title": "T"}]}}

    with patch.object(mcp_service, "_call_tool", new=fake_call_tool):
        result = await mcp_service.analyze_dataset(
            dataset_id="ds-1", user_id="u-1",
            schema={"row_count": 3, "column_count": 2}, statistics={"quality_score": 0.9},
        )
    assert captured["name"] == "eda_summary_tool"
    assert captured["arguments"] == {"params": {"dataset_id": "ds-1", "user_id": "u-1"}}
    assert isinstance(result, MCPAnalysisResponse)
    assert result.metadata["mcp_available"] is True
    assert result.metadata["tools_used"] == ["eda_summary_tool"]
    assert result.insights and result.insights[0]["title"] == "T"


async def test_analyze_dataset_falls_back_on_tool_failure_not_fabricate(mcp_service):
    """A {"success": False} tool result must NOT be turned into fabricated analysis —
    fall back honestly (#506/#539)."""
    with patch.object(
        mcp_service, "_call_tool",
        new=AsyncMock(return_value={"success": False, "message": "Access denied"}),
    ):
        result = await mcp_service.analyze_dataset(dataset_id="ds", user_id="u")
    assert result.metadata.get("mcp_available") is False
    assert result.metadata.get("fallback_mode") is True


async def test_analyze_dataset_falls_back_on_transport_error(mcp_service):
    with patch.object(mcp_service, "_call_tool", new=AsyncMock(side_effect=RuntimeError("no server"))):
        result = await mcp_service.analyze_dataset(dataset_id="ds", user_id="u")
    assert result.metadata.get("mcp_available") is False


async def test_check_health_true_when_tool_registered(mcp_service):
    fake_session = SimpleNamespace(
        list_tools=AsyncMock(
            return_value=SimpleNamespace(tools=[SimpleNamespace(name="eda_summary_tool")])
        )
    )

    @asynccontextmanager
    async def fake_stack_session(_stack):  # not used; we patch _open_session directly
        yield fake_session

    with patch.object(mcp_service, "_open_session", new=AsyncMock(return_value=fake_session)):
        assert await mcp_service.check_health() is True


async def test_check_health_false_when_tool_absent(mcp_service):
    fake_session = SimpleNamespace(
        list_tools=AsyncMock(return_value=SimpleNamespace(tools=[SimpleNamespace(name="other")]))
    )
    with patch.object(mcp_service, "_open_session", new=AsyncMock(return_value=fake_session)):
        assert await mcp_service.check_health() is False


async def test_check_health_false_on_connection_error(mcp_service):
    with patch.object(mcp_service, "_open_session", new=AsyncMock(side_effect=OSError("refused"))):
        assert await mcp_service.check_health() is False
