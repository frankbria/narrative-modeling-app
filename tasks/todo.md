# Issue #176 — CI/Docker hardening follow-ups (mechanical subset)

Branch: `chore/176-ci-docker-hardening`
Scope confirmed with user: mechanical hardening only. Items 1 (mypy→blocking) and
7 (broaden integration coverage) stay open as tracked follow-ups; ruff pyupgrade
(~2,958 findings) deferred — import-sorting only.

## Tasks (PR #214)
- [x] 2. Backend Dockerfile multi-stage — `builder` keeps build-essential; slim
      `runtime` copies only `/app` (venv+code) + installs curl, libgomp1.
- [x] 3. Node 18 → 20 — ci.yml (3), e2e-tests.yml, smoke-tests.yml, perf-tests.yml,
      frontend Dockerfile (deps/builder/runtime).
- [x] 4. Pin uv — `ghcr.io/astral-sh/uv:0.5` → `:0.5.31@sha256:7bff3c37…`.
- [x] 6. Drop `npm ci || npm install` fallback — ci.yml (3), e2e-tests.yml.
- [x] 5. Ruff `extend-select = ["I"]` + autofix 314 I001; guard app/main.py ordering.

## Verification
- [x] `docker build` backend image succeeds; `import app.main` + xgboost/lightgbm
      in runtime image; gcc absent, curl present.
- [x] `ruff check .` clean.
- [x] Service-free pytest suite green (imports intact after isort).
- [x] Workflow YAML still valid.
- [x] Cross-family review (codex): no findings. claude-review = infra max-turns (no findings).
- [x] CI Success green; docs/testing/guide.md synced to Node 20.

## Deferred (issue stays open)
- 1. mypy → blocking (~317 findings, incremental typing project)
- 7. Broaden integration coverage (needs reliable LocalStack/OpenAI)
- ruff pyupgrade rules (UP*) — 2,958-finding repo-wide churn
