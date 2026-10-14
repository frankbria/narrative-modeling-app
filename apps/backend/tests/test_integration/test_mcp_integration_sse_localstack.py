"""#506 AC5: a real tool call against a running MCP server over SSE.

Everything the unit suite mocks — the SSE transport, the tool name, the `params` arg
shape, and result parsing — is exercised here end-to-end against the actual MCP
server (`apps/mcp/main.py`) started as a subprocess. Before #506 this was impossible:
the client spoke REST to paths the server never exposes.

The tool call uses a non-existent dataset id, so the server returns a well-formed
``{"success": False, "message": ...}`` (owner check fails) — which only round-trips if
transport + tool name + arg shape + result parsing are ALL correct. It needs Mongo (the
server resolves the dataset there) and the `apps/mcp` uv environment; skips otherwise,
except in CI, where the environment is synced and a skip is a failure (#998).
"""

import contextlib
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

from app.services.mcp_integration import (
    MCPConfig,
    MCPIntegrationService,
    MCPToolRequest,
)
from tests.conftest import require_service

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

API_KEY = "integration-test-mcp-key"
MCP_DIR = Path(__file__).resolve().parents[4] / "apps" / "mcp"  # repo_root/apps/mcp


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mcp_server():
    # require_service, not a plain skip (#998): the backend-integration CI job syncs
    # apps/mcp so these run on every PR, and CI_REQUIRE_SERVICES turns a missing server
    # into a failure. They skipped on every run until then, so an `mcp` bump in either
    # app could break the connection with CI green. test_mcp_round_trip_runs_in_ci.py
    # pins the sync step. Locally, an unsynced apps/mcp still skips.
    if not (MCP_DIR / "main.py").exists() or not (MCP_DIR / ".venv").exists():
        require_service("apps/mcp environment not available (run `uv sync` in apps/mcp)")
    port = _free_port()
    env = {
        **os.environ,
        "MCP_API_KEY": API_KEY,
        "MCP_HOST": "127.0.0.1",
        "PORT": str(port),  # the server reads PORT, not MCP_PORT
        "MONGODB_URI": os.getenv("TEST_MONGODB_URI", "mongodb://localhost:27017/"),
        "MONGODB_DB": os.getenv("TEST_MONGODB_DB", "narrative-modeling_test"),
    }
    proc = subprocess.Popen(
        ["uv", "run", "python", "main.py"],
        cwd=str(MCP_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        # Wait for the port to accept connections (server up).
        deadline = time.time() + 60
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                require_service(f"MCP server exited early: {out[-500:]}")
            with contextlib.closing(socket.socket()) as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.5)
        else:
            require_service("MCP server did not start within 60s")
        yield port
    finally:
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=10)


def _service(port: int, api_key: str = API_KEY) -> MCPIntegrationService:
    return MCPIntegrationService(
        config=MCPConfig(host="127.0.0.1", port=port, timeout=15, api_key=api_key)
    )


async def test_check_health_finds_the_registered_tool(mcp_server):
    assert await _service(mcp_server).check_health() is True


async def test_real_tool_call_round_trips_over_sse(mcp_server):
    """The whole #506 fix in one assertion: a real call to eda_summary_tool with the
    params arg shape returns a parsed dict. Unknown dataset -> success False, message set."""
    svc = _service(mcp_server)
    resp = await svc.execute_tool(
        MCPToolRequest(
            tool_name="eda_summary_tool",
            parameters={"params": {"dataset_id": "does-not-exist", "user_id": "nobody"}},
        )
    )
    assert resp.error is None, f"transport failed: {resp.error}"
    assert isinstance(resp.result, dict), resp.result
    assert resp.result.get("success") is False
    assert resp.result.get("message")  # a generic access-denied / not-found message


async def test_wrong_api_key_is_rejected(mcp_server):
    # The server fails closed (BearerAuthMiddleware): a bad token can't open a session.
    assert await _service(mcp_server, api_key="wrong-key").check_health() is False


async def test_a_tool_call_the_server_fails_is_reported_as_an_error(mcp_server):
    """A tool the server cannot run answers with the result's error flag set, not a
    transport failure. The client must read that flag from the SDK's own result (#620:
    2.x renamed it, and the old name read as "no error")."""
    resp = await _service(mcp_server).execute_tool(
        MCPToolRequest(tool_name="eda_summary_tool", parameters={"params": {}})
    )
    assert resp.result is None, resp.result
    assert resp.error and "eda_summary_tool" in resp.error
