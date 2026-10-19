# CLAUDE.md - Project Conventions and Guidelines

## Project Overview
SheetPredict — an AI-guided platform that helps non-expert analysts build, explore, and deploy ML models without writing code.

**One product name, SheetPredict (#765).** Pages show `COMPANY.serviceName` (`apps/frontend/lib/legal/company.ts`); `COMPANY.valueLine` equals `docs/product/positioning.md` (sign-up page test). API vendor media type: `application/vnd.sheetpredict.v1+json`. `apps/backend/tests/test_security/test_product_name.py` fails on a retired name in any tracked text file, comments and guides included — describe an old name without writing it. Identifiers keep theirs (repo, packages, databases, buckets, test-user address). The only exempt file is `positioning.md`.

> This file holds durable conventions: the rule, where it lives, and the guard that enforces it. `#NNN` points at the PR with the story; per-issue history lives in git, not here.

## Where the rest lives
Per-app conventions load when you work in that app: `apps/backend/CLAUDE.md` (FastAPI: routes, auth, models, datasets/S3, transformations, training, billing, jobs), `apps/frontend/CLAUDE.md` (Next.js: auth, Tailwind, middleware, pages, errors), `apps/mcp/CLAUDE.md`. Read the relevant one before changing code there.

## Git hooks
- `./scripts/install-git-hooks.sh` runs at session start (`SessionStart` hook) and symlinks `.githooks/pre-push`, which refuses a push updating the default branch (`enforce_admins` is false, so a direct push would succeed). Override: `git push --no-verify`.
- `.claude/hooks/no-push-to-main.sh` is the early-feedback layer for agents (parses command text; only checks the current branch). Override: `ALLOW_MAIN_PUSH=1 git push ...`.
- The installer never clobbers a real file in `.git/hooks` (the untracked secret-scanning `pre-commit` lives there); `core.hooksPath` stays unchanged. Both hooks have `--self-check` tables that CI runs.

## Testing Commands
- Backend (full): `cd apps/backend && uv run pytest` — needs MongoDB on :27017; optional Redis (:6380) + LocalStack (:4566) via `docker compose -f docker-compose.test.yml up -d`.
- Backend (PR gate): `cd apps/backend && PYTHONPATH=. uv run pytest tests/ -m "not integration and not performance" -v`. Selection is by **marker**, never by path.
- Frontend: `cd apps/frontend && npm test` | `npm run type-check` | `npm run lint`
- MCP: `cd apps/mcp && uv run pytest tests/`

### Test footguns
- **Route tests use real documents (#267, #683):** `mock_async_client` mounts only health + secure_upload (other routes 404 vacuously). Use `async_authorized_client` with real Mongo docs and exact statuses. Seed datasets with `UserData(...).insert()` and processed state from captured `dataProcessResponse.json`; never a `MagicMock` dataset or a patched `save`. For X-API-Key routes insert a real `APIKey` and send the raw `sk_live_…`.
- **Captured fixtures (#808):** `apps/frontend/__tests__/fixtures/` bodies are captured, never hand-written — regenerate with `UPDATE_FIXTURES=1 PYTHONPATH=. uv run pytest <capturing test>` (e.g. `tests/test_api/test_user_data_response_fixture.py`) and build page fixtures on them.
- **Frontend lint is warning-capped (#333):** `eslint . --max-warnings 117` over the whole project (incl. `e2e/`, `__tests__/`). The cap only ratchets down; never widen `globalIgnores`.
- **React Compiler rules (#393):** `immutability`, `static-components`, `refs`, `preserve-manual-memoization` are `error`; `set-state-in-effect` is still `warn` (keeps `reactCompiler` off). Counts are lower bounds — re-measure after each batch.
- **`apps/frontend/__mocks__/` auto-applies to every suite (#390):** when bumping a mocked dependency's major, update the mock in the same PR, make it throw on the old prop shape, and mutation-check.
- **Charts run against real recharts (#346):** mock only `ResponsiveContainer` via `jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts()`; assert on drawn output (`axisTicks`, `.recharts-bar-rectangle`, `.recharts-line-curve[d]`). `Tooltip` stays a stub. Recharts majors break at the type level — run `tsc`.
- **jest.setup (#268):** global `fetch` rejects by default — stub it; `useRouter()` spies live at `global.__NEXT_ROUTER_MOCKS__`; Radix tabs need `mouseDown` + `mouseUp` + `click`. Contract: `__tests__/setup/jestSetupContract.test.tsx`.
- **E2E uses real auth (#493):** never `SKIP_AUTH` in `test-e2e.sh`. Direct backend calls get headers from `e2e/helpers/apiAuth.ts::apiAuthHeaders(request)`; a second tenant via `signInAs`. `e2e/workflows/tenant-isolation.spec.ts` (`@smoke`) is the isolation guard — a new owned surface joins its `owned` list.
- **Account-scoped specs run as their own user (#743):** names in `e2e/isolatedUsers.ts`, opted into with `test.use({ storageState: isolatedState('<name>') })` (`TEST_ISOLATED_USERS=1`). Never reset, erase or re-plan the shared user.
- **E2E assertions must be able to fail (#921, #999, #810):** drive pages navigation reaches; no assertions inside `try/catch` or `if (await x.isVisible())`; no bare `return;` (`__tests__/e2e/noEarlyReturns.test.ts`) — seed preconditions (`seedEvaluationWorkflow`, `trainModel`). Assert stage landings with `e2e/helpers/landing.ts::expectLandedOnStage(page, url, '<Stage>')`, never the address alone. Break the thing a new spec tests once before trusting it. `e2e/pages/TransformPage.ts` is legacy (#991); `e2e/fixtures/auth.ts`'s `authenticatedPage` is deprecated.
- **Red smoke (#578):** read `error-context.md` and `trace.zip` before retrying. `authenticatedPage` (`e2e/fixtures/index.ts`) fails naming the actual landing URL; a failure across in-run retries is a real signal, not flake.

## CI & Test Suite Status
- pytest always uses the **test** database (`tests/conftest.py::_app_uses_the_test_database`) and pins its own S3 settings (blank credentials, local `AWS_ENDPOINT_URL`; `test_suite_never_reaches_aws.py`) — read a credential in a fixture with `os.getenv(NAME) or "test"`.
- **`ci.yml` is the PR gate:** backend (ruff `E`/`F`/`I`/`UP`, mypy, pytest by marker against Mongo), frontend (eslint, `tsc --noEmit`, `next build`, jest), MCP pytest, backend integration (`CI_REQUIRE_SERVICES=true`), `e2e-smoke`. **`CI Success` is the only required check.** Advisory: `backend-typecheck`, `perf-tests.yml`, `security-audit`, review bots. `e2e-tests.yml` runs the full suite nightly and opens/closes a `[P2] [testing] The nightly full e2e suite is failing` issue.
- **Review bots — absent ≠ clean (#571, #626, #955):** a red `claude-review`, or a GLM run that failed to start or finished faster than a review takes, means no verdict. `review-bots-health.yml` (`scripts/ci/review_bots_health.sh`; add new reviewers to `WORKFLOWS`) opens/closes a `[P2] [infra] Review bot is failing at startup: <workflow>` issue, deduped on that phrase. Keep the GLM caller's `permissions:` in step with the pinned callee and never add a caller-level `concurrency:` group matching the callee's (`test_review_bots_health_wiring.py`). `claude-review` keeps its step `timeout-minutes: 9` below the job's 10 so the "did not complete" comment can post, and runs only for human PRs (Dependabot skips are by design).
- **Staging access:** `ssh staging-ts '<cmd>'` only, with inline `python -c "…"` (opaque piped scripts are refused; `scripts/` isn't in the image). If refused or the alias is missing, don't retry variants — `gh workflow run staging-health.yml --ref <branch>` (exit 137 = boot loop). Split secret-needing verification into a code PR + an operator issue with exact commands.
- **Wait for CI with `scripts/ci/wait_for_checks.sh <pr|sha>`** in the foreground with a bounded timeout (0 = `CI Success`, 1 = failure, 2 = timeout).
- Deploys, staging health, staging env vars and the nginx edge config: the `staging-ops` skill (`.claude/skills/staging-ops/SKILL.md`).
- Guides: `docs/dev/TEST_INFRASTRUCTURE.md`, `docs/dev/E2E_TESTING_GUIDE.md`, `docs/dev/LOCAL_DEVELOPMENT.md`.

## Docs and licence
- **`docs/` holds only what is current and used:** `adr/` (decision records — supersede, never rewrite), `ops/` (runbooks that workflows, scripts and the legal pages point at), `product/`, `dev/`. Session notes, sprint/story reports and per-issue demos are not committed (`/tasks/` is gitignored); history lives in git and the PRs.
- **Licence is Apache-2.0:** `LICENSE` is the verbatim text, attribution is in `NOTICE`; `pyproject.toml`/`package.json`, `GET /` and the OpenAPI `info.license` state the same SPDX id (`tests/test_security/test_license.py`).
- **Env templates:** repo-root `.env.staging.example` and `.env.production.example` hold exactly the variables `docker-compose.staging.yml` interpolates (plus `NGINX_SERVER_NAME`), in the same order with the same comments — only values differ. `apps/backend/.env.example` and `apps/frontend/.env.local.example` are local-dev; the variables both services read carry identical values and text. Change a pair together.

## Environment Variables
- **`NEXT_PUBLIC_API_URL` includes `/api/v1` (#406, #470):** append only the resource path; never re-add `/api` or "normalise" with `.replace(...)`. Never call a bare relative `/api/v1` from `app/`, `components/`, `lib/` (Next route handlers under `app/api/**` are the only relative target). Guard: `__tests__/lib/apiUrlConstruction.test.ts`.
- **`MONGODB_URI` is bare; the database is `MONGODB_DB` (#545, #551, #694)**, passed to both halves with the same value (the backend selects `client[db_name]`; the NextAuth adapter gets `databaseName`). Omitting it silently lands on a database named `test`. The frontend's `assertDatabaseConfig` (`lib/auth-config.ts`, production only) and the backend's `resolve_database_name` refuse a missing or disagreeing name. Guard: `__tests__/lib/authAdapterDatabase.test.ts`.
- **Local development uses LocalStack, never a deployed bucket (#878):** `AWS_ENDPOINT_URL=http://localhost:4566` (bucket via `awslocal s3 mb`). `development_uses_a_real_bucket()` warns once per process otherwise.
- `SKIP_AUTH=true` maps all requests to `dev-user-default` and is honoured only when `ENVIRONMENT` is `development`/`test` (startup fails otherwise, #149).

## Documentation Requirements
Keep docs in sync with code: OpenAPI when endpoints change; docstrings/JSDoc on public or complex surfaces; remove outdated comments immediately; update the relevant section of the matching CLAUDE.md (root, `apps/*/CLAUDE.md`, or the `staging-ops` skill) when a convention changes — the rule and its guard, not the story.

## Automated Workflow Configuration
- **Quality gates before PR:** tests pass, coverage >85%, ruff/eslint clean, mypy/tsc clean, no TODO/FIXME/NotImplemented markers, OWASP scan, and `scripts/quality/crap.sh` passes: every added or modified function scores CRAP < 6 — split or cover it, never skip (exit 2 = a measurement is missing: follow the hint; backend coverage needs MongoDB). No standing exemptions.
- **CRAP gate reads `.tsx` with lizard's TypeScript reader, which misreads some shapes (#765, #808, #825, #855).** Write instead:
  - `props: {…}` destructured in the first statement (`const { a } = props`), not a typed destructured parameter.
  - callbacks typed `VoidFunction` or as a method signature (`onSelect(view: View): void`), not `() => void` in a props type.
  - `{x ? <A/> : <B/>}`, not a parenthesised JSX ternary.
  - a named type, not an inline object type as a generic argument (`ComponentType<{…}>` blinds the whole file).
  - `unknown` + a cast at the caller, not a generic function declaration.
  - a component with a statement before `return <JSX>` (a bare return gets no LCOV line); inline JSX arrows named in the component body; `??` counts as two branches; a file not yet `git add`ed reads as absent.
  When line ranges look wrong, run `uvx lizard -l typescript <file>`.
- **CodeRabbit:** max 3 iterations; auto-fix style/types/simple bugs/docs. Escalate on iteration-3 failures, architecture changes, or security decisions.
