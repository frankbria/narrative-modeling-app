# apps/mcp — MCP server conventions

> MCP server conventions. The root `CLAUDE.md` (product name, git hooks, tests, CI, quality gates) still applies.

- Exposes `eda_summary_tool` over SSE via the `mcp` SDK's `MCPServer` (entry `main.py`). **Server and backend client move together (#620):** both pin `mcp>=2,<3`; a new major migrates both. Relock with `uv lock --upgrade[-package mcp] --exclude-newer <a week ago>`, then plain `uv lock`.
- **The backend client speaks real MCP (#506):** `app/services/mcp_integration.py` uses `sse_client` + `ClientSession` with a bearer token, calls `eda_summary_tool` with `params={dataset_id, user_id}` (the server reads S3 and checks ownership). Bound both `timeout` and `sse_read_timeout` by `MCP_TIMEOUT`. Failures fall back, never fabricate. Read result fields as attributes (`result.is_error`, `result.structured_content`), never `getattr` with a default; raise a tool error after the session closes. Unit tests build the SDK's real `CallToolResult`.
- **`apps/backend` is NOT a package (no `__init__.py`):** with one, `apps/mcp` (named `mcp`) shadows the installed SDK under pytest. The `backend-integration` job runs `uv sync --frozen` in `apps/mcp` so the SSE round trip runs (`require_service`; `test_mcp_round_trip_runs_in_ci.py` bans a plain `pytest.skip`).
