# CLAUDE.md - Project Conventions and Guidelines

## Project Overview
Narrative Modeling App — an AI-guided platform that democratizes machine learning by helping non-expert analysts build, explore, and deploy models without writing code.

> Per-issue implementation history lives in git/PRs, not here. This file holds durable conventions only.

## Architecture

### Frontend (`apps/frontend/`, Next.js)
- App Router, TypeScript strict, Tailwind CSS
- NextAuth v5 (Google, GitHub); frontend mints an HS256 JWT (`sub=userId`) in the session callback for the backend to verify

### Backend (`apps/backend/`, FastAPI)
- Async FastAPI, MongoDB via Beanie ODM, AWS S3 for files, `BackgroundTasks` for AI/ML work
- Canonical Beanie model registry: `app/models/registry.py` (shared by app lifespan + `setup_database` fixture)

### MCP Server (`apps/mcp/`, FastMCP)
- Exposes `eda_summary_tool` over SSE; called by the backend on the same host. Entry point `main.py`. FastMCP from the installed `mcp` SDK (`mcp.server.fastmcp`), not vendored.

## Backend Conventions & Recurring Gotchas
- **Two model surfaces:** `MLModel` (routes under `/api/v1/ml/`) is the **real** trained-model surface — build everything here. `ModelConfig` (`/api/v1/models/`) is **dead legacy**, never created by the training flow; its train/deploy/performance routes are `410 Gone`. Bot plans (Traycer/CodeRabbit) routinely target the wrong one.
- **Schema ↔ type mirrors:** backend Pydantic schemas mirror frontend TS types — change both together. Notably `app/schemas/evaluation.py` ↔ `apps/frontend/lib/types/evaluation.ts`.
- **`MLModel` mock fixture:** adding any optional `MLModel` field breaks the `sample_ml_model` MagicMock under `response_model=MLModel` validation unless the fixture sets it. Recurs constantly.
- **New optional fields degrade:** add `MLModel`/schema fields as optional/defaulted so pre-existing models still validate and endpoints return `partial=true` rather than 500.
- **Route order:** register specific `/ml/{model_id}/<sub>` routes **before** the catch-all `/{model_id}`.
- **AI services:** OpenAI (JSON mode) behind the shared circuit breaker + a deterministic rule-based fallback — endpoints must work fully **without** an API key.
- **Removable dependency levers:** heavy optional deps live in PEP 735 `[dependency-groups]` (`interpretability` = shap/numba stack; `tuning` = optuna), kept in `default-groups`, lazy-imported. Slim image: `uv sync --frozen --no-dev --no-group <group>`; the app degrades gracefully.
- **Error handling (#269):** central handlers in `app/middleware/error_handlers.py` sanitize **all 5xx** (generic body + `X-Request-ID`, never echo `str(e)`) and pass 4xx validation text through. Do not reintroduce `str(e)` in 5xx bodies.
- **Two dataset id-spaces:** `DatasetMetadata` (string `dataset_id`, S3 `datasets/{user}/...`, string-keyed children) and legacy `UserData` (ObjectId, `Link` DBRef children) are **dual-written**, linked only by `(user_id, s3_url)`. Deletion cascades across both via `DatasetErasureService` (#259).
- **Viz data source:** visualization/preview endpoints load from `UserData.s3_url`, **not** `file_path` (a raw S3 key the strict downloader rejects).
- **Transformation engine contract:** the engine maps only a few transform types; `FILL_MISSING` uses `method` (mean/median numeric-only). The `/datasets` upload path stores `data_schema=[]` with real columns in `inferred_schema` (a `SchemaInference` dump).
- **Beanie `save()`** surfaces a unique-index violation as `RevisionIdWasChanged`, not `DuplicateKeyError`.
- **Artifact integrity (#266):** model artifacts are HMAC-SHA256 signed (signature in Mongo, bytes in S3); joblib/pickle loads verify before deserializing and refuse on mismatch.
- **Model cache + inference (#265):** `_ModelArtifactCache` is a TTL-LRU keyed by `(model_id, user_id)`, invalidated on delete/retrain/deploy. All inference routes through `run_locked_inference` (per-model lock + `to_thread`).
- **datetime:** use `datetime.now(UTC)` / the `app/utils/datetime.py` helpers (`utcnow`, `as_utc`). Mongo reads datetimes back **naive** — coerce stored values with `as_utc` before arithmetic against aware `now`.
- **Rate limiting (#151):** global `RateLimitMiddleware` on all `/api/v1`; per-key buckets only on `/production/v1/models`. **Disabled in the test env.**

## Testing Commands
- Backend (full): `cd apps/backend && uv run pytest` — needs MongoDB on :27017; optional Redis (:6380) + LocalStack (:4566) via `docker compose -f docker-compose.test.yml up -d` (tests skip with a reason when absent)
- Backend (service-free): `cd apps/backend && PYTHONPATH=. uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ tests/test_models/ tests/test_auth/ tests/test_model_training/test_problem_detector.py tests/test_model_training/test_feature_engineer.py -m "not integration and not performance" -v`
- Frontend: `cd apps/frontend && npm test` | type check: `npm run type-check` | lint: `npm run lint`
- MCP: `cd apps/mcp && uv run pytest tests/`

### Test footguns
- **Route tests (#267):** `tests/test_api/conftest.py::mock_async_client` mounts only `health` + `secure_upload`, so requests to any other router 404 and `assert x in [200, 404, 422]`-style checks pass vacuously. Use **`async_authorized_client`** (full app, auth overridden) + real Mongo docs and assert **exact** statuses. For the X-API-Key production surface, insert a real `APIKey` and pass the raw `sk_live_…` header. The in-memory `prediction_log` is process-global and never cleared by `setup_database` — reset it when asserting per-model counts.
- **Frontend lint is warning-capped (#333):** Next 16 removed `next lint`, so `npm run lint` is `eslint . --max-warnings 280`. The ceiling is deliberate and ratchets **down** as debt clears — never up to accommodate new warnings. **Adding one new warning anywhere (a stray `any` is the usual culprit) fails CI even though nothing errored.** Fix the warning, or lower the number deliberately — never widen `globalIgnores` to dodge it. Lint scope is the whole project, not `next lint`'s `app`/`components`/`lib`, so `e2e/` and `__tests__/` are linted too (with `no-console`/`no-require-imports` relaxed there).
- **React Compiler rules (#373 → #393):** four of the five `eslint-plugin-react-hooks` v7 rules are burned down and enforced as **`error`** (`immutability`, `static-components`, `refs`, `preserve-manual-memoization`) — reintroducing one fails the build. Only `set-state-in-effect` is still `warn` (46 sites, #393), which is what keeps the `react-compiler-rules-pending-burndown` block alive and `reactCompiler: true` off. **Counts from these rules are lower bounds:** the compiler bails out of a component at its first error, so fixing one rule can *reveal* more violations of another — clearing `immutability` raised `set-state-in-effect` from 26 to 46. Re-measure after each batch instead of working a fixed list.
- **`apps/frontend/__mocks__/` auto-applies to EVERY suite (#390):** it sits next to `node_modules`, so jest uses those manual mocks for node-module imports with **no `jest.mock()` call anywhere**. A mock left on an old major's API does not fail loudly — it keeps rendering from props the real library ignores, turning a broken component into a green suite. This bit exactly once already: after the react-window v1→v2 migration, `ColumnSelector`'s 53 tests failed correctly while `BulkColumnSelector`'s 16 **passed against an equally broken component**, because that suite also declared its own inline v1 mock. When bumping a mocked dependency's major, **update the mock in the same PR and make it throw on the old prop shape**, then mutation-check it (revert the component; the tests must fail).
- **Frontend jest.setup (#268):** the global `beforeEach` sets `global.fetch` to **reject** by default — any test that fetches must stub `global.fetch` explicitly. `useRouter()` returns a stable per-test spy at `global.__NEXT_ROUTER_MOCKS__` (`push`/`replace`/…) for asserting redirects. Contract locked by `__tests__/setup/jestSetupContract.test.tsx`. Radix tabs need `mouseDown`+`mouseUp`+`click`, not a bare `click`.

## CI & Test Suite Status
- Backend full suite green locally (~1,460 passed); pytest uses the **test** database, never `MONGODB_URI`.
- **`ci.yml` is the PR gate.** Runs: backend (ruff **blocking** with `E`/`F`/`I`/`UP`; mypy **blocking** — plain `uv run mypy app/`; service-free pytest), frontend (eslint, `tsc --noEmit`, `next build`, jest), MCP pytest, backend integration (Mongo/Redis/LocalStack, `CI_REQUIRE_SERVICES=true` so services can't silently skip), and the `e2e-smoke` job (Playwright `@smoke` on the full stack).
- The single aggregate **`CI Success`** status is the only required check for `main` — it transitively enforces all of the above (incl. e2e smoke). Advisory-only: `backend-typecheck`, the `@perf` job (`perf-tests.yml`), `security-audit`, and the Claude/GLM review bots.
- `deploy.yml` ships `main` → staging over SSH (secret-gated). **The VPS firewalls port 22 off the public internet** (`ufw` allows it only from the home subnet and `on tailscale0`), so the runner joins the tailnet first — `HOST` must be the box's **tailnet** name/`100.x` address, never `dev.briaanalytics.com`, and `SSH_KNOWN_HOSTS` must be labelled with that same value (#384). Humans on the home subnet still SSH to the public name directly. `integration-tests.yml`/`e2e-tests.yml` are manual (`workflow_dispatch`).
- Guides: `apps/backend/docs/TEST_INFRASTRUCTURE.md`, `apps/backend/docs/TDD_GUIDE.md`.

## Environment Variables
- Frontend: `.env.local` | Backend: `.env`
- Required: AWS credentials, MongoDB URI, OpenAI API key, NextAuth secret
- `SKIP_AUTH=true` bypasses auth — honored **only** when `ENVIRONMENT` is `development`/`test`; startup fails hard otherwise (#149). Maps all requests to `dev-user-default`.

## Data Flow
1. Upload → backend processes → S3
2. Metadata → MongoDB
3. Background AI analysis triggered
4. Frontend renders results + visualizations

## MCP Server Setup
```bash
cd apps/mcp
uv sync
MCP_API_KEY=<secret> uv run python main.py   # binds 127.0.0.1; fails closed without MCP_API_KEY
```
See `apps/mcp/README.md` for tools, env, and the security model. Recommended external MCP servers: Context7 (library docs), Serena (project memory).

## Documentation Requirements
Keep docs synchronized with code: update OpenAPI specs when endpoints change; Python docstrings + TS JSDoc on public/complex surfaces; remove outdated comments immediately; update the relevant section of **this file** when a convention changes (don't add per-issue narrative — that's git/PR history).

## Automated Workflow Configuration
- **Quality gates before PR:** all tests pass, coverage >85%, ruff/eslint clean, mypy/tsc clean, no TODO/FIXME/NotImplemented markers, security scan (OWASP).
- **CodeRabbit:** max 3 iterations; auto-fix style/types/simple-bugs/docs. Escalate on iteration-3 failures, architecture changes, or security decisions.
