# MCP Server - Narrative Modeling App

Model Context Protocol (MCP) server exposing data-analysis tools for the
Narrative Modeling Application over an SSE transport.

## Architecture

- **Framework**: FastMCP from the [`mcp`](https://pypi.org/project/mcp/) SDK
  (`mcp.server.fastmcp`) — there is no separately-installed `fastmcp` package.
- **Transport**: SSE (Starlette + uvicorn), bound to `127.0.0.1` by default.
- **Language**: Python 3.10+
- **Package Manager**: uv
- **Entry point**: `main.py`

## Quick Start

### Prerequisites

- Python 3.10+
- uv
- The required environment variables (see Security & Deployment below)

### Run

```bash
cd apps/mcp
uv sync
MCP_API_KEY=<secret> uv run python main.py
```

The server refuses to start without `MCP_API_KEY` (fails closed). It listens on
`127.0.0.1:$PORT` (`PORT` defaults to `10000`; `MCP_HOST` overrides the bind
address).

## Available Tools

- **`eda_summary_tool`** — generates an exploratory-data-analysis summary
  (shape, dtypes, missing-data/outlier/skew quality metrics, high-cardinality
  and correlated features, transformation suggestions, grouped insights) for a
  dataset the caller owns.

  Input: `{ "dataset_id": str, "user_id": str }`. The S3 location is resolved
  and ownership-checked **server-side** from the `user_data` record — callers
  never supply a bucket/key/URL. Returns `{ "success": bool, "data": {...} }`
  on success or `{ "success": false, "message": str }` on failure (generic
  messages only — no S3/ownership internals leak).

## Security & Deployment

The SSE server exposes tools that read datasets from S3 with the server's AWS
credentials. To prevent cross-tenant data exfiltration (issue #254) the server
enforces the following — **all must hold before any deploy**:

- **Bind to localhost.** `main.py` binds `127.0.0.1` by default (`MCP_HOST`
  override). The only intended caller is the backend on the same host. Never
  expose the port on `0.0.0.0` / a public interface.
- **Require a bearer token.** `MCP_API_KEY` must be set or the server refuses to
  start (fails closed). Every request must send
  `Authorization: Bearer <MCP_API_KEY>`; the backend already does.
- **Ownership is enforced per request.** Tools take a `dataset_id` + `user_id`
  and resolve the dataset from the `user_data` collection, verifying
  `dataset.user_id == user_id`. The S3 key is derived **server-side** from the
  stored record — callers never supply a bucket/key/URL.
- **Bucket allowlist.** Downloads are pinned to the configured app bucket
  (`AWS_S3_BUCKET`, or `AWS_BUCKET_NAME`); a URL pointing elsewhere is rejected.
- **Generic errors.** Missing vs. unauthorized vs. S3 failures all return the
  same generic message (no `AccessDenied`-vs-`NotFound` leakage, no enumeration).
- **Scope the IAM policy.** Provision the server's IAM identity with read access
  scoped to the app bucket/prefix only — the allowlist is defense-in-depth, not
  a substitute for least-privilege credentials.

**Required env:** `MCP_API_KEY`, `MONGODB_URI`, `MONGODB_DB`, `AWS_S3_BUCKET` (or
`AWS_BUCKET_NAME`), `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`.
`MONGODB_DB` selects the database explicitly and **must match the backend's**
`MONGODB_DB` — `MONGODB_URI` is bare (no default database), so without it the owner
lookup would hit the wrong database and deny legitimate requests (#540). The server
fails fast at startup if it is unset.

**Trust boundary (beta):** the bearer token is a single shared secret, so the
MCP trusts the (localhost, authenticated) backend to assert the correct
`user_id`. Per-user MCP tokens are a future hardening.

## Testing

```bash
# Run the MCP test suite
uv run pytest tests/
```

## Project Structure

```
apps/mcp/
├── main.py            # SSE server entry point (registers tools, runs uvicorn)
├── auth.py            # Bearer-token ASGI middleware (SSE-safe)
├── config.py          # Settings
├── tools/
│   └── eda_summary.py # eda_summary_tool implementation
├── utils/
│   ├── s3_service.py  # bucket-pinned S3 URL parsing + download
│   ├── user_data.py   # dataset-record lookup
│   └── numpy_json.py  # numpy → JSON coercion
├── models/
│   └── user_data.py   # read-only UserData mirror (ownership check)
├── tests/             # pytest suite
├── pyproject.toml
└── README.md
```

## Adding a Tool

1. Implement the tool in `tools/` (a pydantic input model + an `async` handler
   that resolves + ownership-checks the dataset server-side).
2. Register it in `main.py` with `@mcp.tool()`.
3. Add tests under `tests/`.
4. Update this README's Available Tools list.

## Related Documentation

- [Backend API](../backend/README.md)
- [Product Requirements](../../PRODUCT_REQUIREMENTS.md)
