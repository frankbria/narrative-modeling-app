# Issue #283 — [P2.6] Dependency hygiene

**Plan source:** self-authored from acceptance criteria (no plan comment). No architectural fork → autonomous.

**Verified against actual code (2026-07-21).** Several ACs were already resolved by prior issues or turned out to be dead code — verification changed the scope from "migrate" to "delete".

## Per-AC plan

| # | AC | Verified state | Action |
|---|----|----------------|--------|
| 1 | `uv remove axios` | `axios>=0.4.0` in `apps/backend/pyproject.toml` `[project.dependencies]`. Only repo ref is a JS code-sample string in `api_documentation.py` (not a Python import). Dependency-confusion smell. | `uv remove axios` (backend) |
| 2 | migrate XLSX parsing to maintained lib **or** backend path + size cap | `exceljs` used **only** by `apps/frontend/app/api/upload/route.ts` (+ its test). That route has **zero callers** — the upload page previews via the FastAPI backend (`${API_URL}/upload/secure`, openpyxl parse, #270 size caps). Route is dead. | **Delete** the dead route + `route.test.ts`; `npm uninstall exceljs`. XLSX parsing now lives solely on the backend path w/ size cap (= the AC's 2nd option). |
| 3 | pin one next-auth version | Declared twice: root `package.json` (`^5.0.0-beta.29`, vestigial — not a workspace, unreferenced by CI/Docker) vs `apps/frontend/package.json` (`^5.0.0-beta.28`). | Delete vestigial root `package.json` + `package-lock.json`; pin `apps/frontend` next-auth to a single exact version (betas don't follow semver). |
| 4 | replace vendored fastmcp w/ pinned PyPI dep | **Already done by #255** — `apps/mcp/main.py` imports `mcp.server.fastmcp` from the `mcp>=1.25.0` SDK. `apps/mcp/fastmcp/` holds **0 `.py` / 0 git-tracked files** — only stale untracked `__pycache__`. | Local `rm -rf apps/mcp/fastmcp` (untracked cruft; no PR diff). Document AC as satisfied. |
| 5 | move dev tooling to `[dependency-groups] dev` | `pytest`, `pytest-asyncio`, `pytest-benchmark`, `ruff` in `[project.dependencies]` (ship via `uv sync --no-dev` Docker build). CI runs plain `uv sync` (installs `dev` via `default-groups`). | Move the 4 tools into the existing `dev` group. CI keeps them; Docker `--no-dev` drops them from the image. |
| 6 | consolidate to one JWT lib | Backend has both `jwt>=1.3.1` and `python-jose[cryptography]`. Only `from jose import jwt` is imported anywhere; bare `jwt` package imported nowhere. | `uv remove jwt` (backend). Keep python-jose. |
| 7 | remove empty manifests | `ml/requirements.txt` (0B), `apps/mcp/requirements.txt` (0B) empty. Root `uv.lock` doesn't exist. "Poetry/uv split" = root `pyproject.toml` (Poetry) + `shared/` pkg (`shared/poetry.lock`) — `shared/` imported by nothing in `apps/` (only imports itself). | Delete both empty `requirements.txt`. Delete dead `shared/` + root Poetry `pyproject.toml` (the "Poetry/uv split" named in the issue Impact). |

## Verification (no new business logic → regression-guarded by existing suites)
- Backend: `cd apps/backend && uv lock && uv sync && uv run ruff check . && uv run pytest` (service-free subset) green.
- Frontend: `cd apps/frontend && npm install && npm run type-check && npm run build && npm test` green.
- MCP: `cd apps/mcp && uv run pytest tests/` green.
- Grep guards: no remaining `exceljs`, `axios` (dep), bare `jwt` import, `from shared`, `/api/upload` refs.

## Not doing (YAGNI / out of scope)
- Not migrating exceljs to another JS lib (route is dead → delete beats migrate).
- Not touching `apps/mcp/pyproject.toml` (already on `mcp>=1.25.0`, no fastmcp dep).
