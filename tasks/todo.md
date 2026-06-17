# Issue #176 — CI/Docker hardening follow-ups (batch 2)

Umbrella issue. Batch 1 (multi-stage backend image, digest pins, Node 20, uv pin, isort)
shipped in PR #214. This PR implements 4 selected self-contained follow-ups.

Branch: `chore/176-ci-docker-hardening-batch2`

## Scope (user-confirmed)
1. **Backend runtime non-root user**
2. **Backend `.dockerignore`** (trim builder context)
3. **Dependabot Docker digest refresh** (+ github-actions to maintain SHA pins)
4. **Repo-wide GitHub Actions SHA pinning**

Out of scope (large/incremental — stay open on #176): mypy→blocking, ruff pyupgrade,
broaden integration coverage. CI service-container image digest pinning = documented follow-up.

## Plan

### 1. Backend non-root user (`apps/backend/Dockerfile`, runtime stage)
- Create non-root system user/group (`appuser`, uid/gid 1001) via `groupadd`/`useradd`
  (Debian slim, not alpine's addgroup/adduser).
- `--chown=appuser:appuser` on the three `COPY --from=builder` lines (.venv, app, utils).
- Keep `python -c "import app.main"` guard (runs as root pre-switch, fine).
- `USER appuser` before EXPOSE. gunicorn binds :8000 (>1024 → non-root OK); curl healthcheck OK.
- Mirrors the frontend image's existing non-root pattern.

### 2. Backend `.dockerignore`
- Add clearly-non-build entries: `tests/`, `tasks/`, `sample_datasets/`, `claudedocs/`,
  `scripts/`, `.benchmarks/`, `.apm/`, loose artifacts (`coverage_summary.txt`, `test.csv`,
  `docker-compose.test.yml`).
- NEVER exclude build inputs: `pyproject.toml`, `uv.lock`, `app/`, `utils/`, `main.py`,
  `__init__.py`, **`README.md`** (referenced by `[project].readme`; no `[build-system]`).
- VERIFY with a real `docker build` (the meaningful test for this change).

### 3. `.github/dependabot.yml` (new)
- `docker` for `apps/backend`, `apps/frontend`, `apps/mcp` (weekly) — refresh `FROM @sha256`
  + `COPY --from=...@sha256` digest pins.
- `github-actions` for `/` (weekly) — keep the new SHA pins current.

### 4. GitHub Actions SHA pinning (all 8 workflows)
Replace `uses: org/action@vN` → `uses: org/action@<sha> # vN`. Resolved SHAs:
- actions/checkout@v5              -> 93cb6efe18208431cddfb8368fd83d5badbf9bfd
- actions/upload-artifact@v4       -> ea165f8d65b6e75b540449e92b4886f43607fa02
- actions/setup-python@v5          -> a26af69be951a213d495a4c3e4e4022e16d87065
- actions/setup-node@v4            -> 49933ea5288caeca8642d1e84afbd3f7d6820020
- codecov/codecov-action@v4        -> b9fd7d16f6d7d1b5d2bec1a2887e65ceed900238
- anthropics/claude-code-action@v1 -> 9dd8b95a392eb34b6f5fb56cf5a64cb735912d4b
- actions/cache@v4                 -> 0057852bfaa89a56745cba8c7296529d2fc39830

## Verification
- `docker build apps/backend` succeeds (non-root + .dockerignore); runs `import app.main`.
- `docker build apps/frontend` still succeeds (unchanged, sanity).
- actionlint / YAML lint workflows; confirm no bare `@vN` action refs remain.
- Validate dependabot.yml.

## PR
- References #176; lists done + still-open items.
