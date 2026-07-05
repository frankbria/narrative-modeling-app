# Issue #255 [P0.5] — MCP server cannot start; its single tool is incompatible with real datasets

**Plan source:** self-authored (no plan comment on the issue). No architectural fork → proceeding autonomously.

## Findings (state vs. acceptance criteria)

Much of this issue's hardening already landed in #254 (ownership checks, bucket-pinned
S3 parsing, temp cleanup in `finally`, generic errors). Verified live:
- `import main` fails today with `PackageNotFoundError: No package metadata was found for fastmcp` (vendored copy) → server can't start.
- `mcp.server.fastmcp.FastMCP` (SDK, locked 1.25.0) is a drop-in: `.tool()` accepts the pydantic-model param, `sse_app()` returns a Starlette app.

## Steps

- [ ] **1. Fix startup import (AC1).** `main.py`: drop the `sys.path.insert(... fastmcp/src)` +
  `from fastmcp.server.server import FastMCP`; use `from mcp.server.fastmcp import FastMCP`.
  Delete the vendored `fastmcp/` dir (143 tracked files) — no longer imported.
  `pyproject.toml`: bump `mcp>=1.6.0` → `mcp>=1.25.0`.
- [ ] **2. Offload blocking calls (AC4).** `tools/eda_summary.py`: run the blocking
  S3 download + `pd.read_csv` + pandas analysis via `asyncio.to_thread` so the async
  handler doesn't block the event loop. Keep temp cleanup in the async `finally`.
- [ ] **3. Deslop dead/stale code (AC6 "correct or implement").** Delete dead
  `tool_runner.py` (calls nonexistent `eda_summary.run`, imported nowhere) and the empty
  stubs `tools/model_train.py`, `tools/null_analysis.py`. Fix `render.yaml`
  (Poetry + `pip install -e ./fastmcp` → `python main.py`, no vendored install).
- [ ] **4. Tests (AC5).** Non-mocked temp-file cleanup test (real file removed on success
  *and* on read failure) in `tests/test_tools/`; subprocess smoke test that `main` imports
  (proves the server can start). URL-parse tests already exist and are non-mocked.
- [ ] **5. Docs (AC6).** Rewrite `README.md` to reality: single `eda_summary_tool`, entry
  point `main.py` (not `server.py`), actual dir layout, real run command; remove the ~9
  advertised-but-nonexistent tools and the vendored-fastmcp doc link. Update root
  `CLAUDE.md` MCP-setup snippet (`server.py` → `main.py`) and the `### MCP Server` note
  (startability fixed).

## Acceptance criteria checklist

- [ ] Import `FastMCP` from `mcp.server.fastmcp`; vendored copy dropped (AC1)
- [ ] Reuses a hardened S3 URL parser (AC2 — satisfied by #254's `parse_and_validate_s3_url`, a superset of the backend's `parse_s3_url`; kept local since the apps aren't linked)
- [ ] Temp files cleaned up in `finally` (AC3 — done in #254; preserved)
- [ ] Blocking calls offloaded via `asyncio.to_thread` (AC4)
- [ ] Non-mocked URL-parse + cleanup tests (AC5)
- [ ] README/CLAUDE.md corrected (AC6)

## Deviations / decisions (autonomous)

- **Keep MCP-local `parse_and_validate_s3_url`** rather than importing the backend's
  `parse_s3_url`: the MCP app is standalone (backend isn't a dependency), and the local
  parser is a strict superset (adds bucket allowlisting). Reusing it satisfies AC2's intent.
- **Drop, not fix, the vendored fastmcp** (AC allows either) — lazy + correct.
