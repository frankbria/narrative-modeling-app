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
from mcp.types import CallToolResult, TextContent

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
    assert svc._sse_url == "http://h:1234/sse"  # the server's sse_app() serves the stream at /sse
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


# The results below are the SDK's own type, never a stand-in: the client read the 1.x
# field names through getattr with a default, so on the 2.x SDK a stand-in carrying the
# old names kept passing while a failed tool call came back as a result (#620).
def _session_answering(result: CallToolResult) -> SimpleNamespace:
    return SimpleNamespace(call_tool=AsyncMock(return_value=result))


async def _execute(mcp_service, result: CallToolResult):
    session = _session_answering(result)
    with patch.object(mcp_service, "_open_session", new=AsyncMock(return_value=session)):
        return await mcp_service.execute_tool(
            MCPToolRequest(tool_name="eda_summary_tool", parameters={"params": {}})
        )


async def test_a_failed_tool_call_is_an_error_not_a_result(mcp_service):
    failed = CallToolResult(content=[TextContent(type="text", text="boom")], is_error=True)
    resp = await _execute(mcp_service, failed)
    assert resp.result is None
    assert "boom" in resp.error


async def test_a_dict_result_is_read_from_the_structured_content(mcp_service):
    answered = CallToolResult(content=[], structured_content={"success": True, "rows": 3})
    resp = await _execute(mcp_service, answered)
    assert resp.error is None
    assert resp.result == {"success": True, "rows": 3}


async def test_a_wrapped_scalar_result_is_unwrapped(mcp_service):
    resp = await _execute(mcp_service, CallToolResult(content=[], structured_content={"result": 7}))
    assert resp.result == 7


async def test_a_text_only_result_is_parsed_as_json(mcp_service):
    text_only = CallToolResult(content=[TextContent(type="text", text='{"success": false}')])
    resp = await _execute(mcp_service, text_only)
    assert resp.result == {"success": False}


async def test_text_that_is_not_json_is_returned_as_it_is(mcp_service):
    plain = CallToolResult(content=[TextContent(type="text", text="twelve rows")])
    assert (await _execute(mcp_service, plain)).result == "twelve rows"


async def test_a_result_with_nothing_in_it_is_none(mcp_service):
    assert (await _execute(mcp_service, CallToolResult(content=[]))).result is None
