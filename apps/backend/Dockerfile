# Backend (FastAPI) production image — built by docker-compose.staging.yml and
# deployed by .github/workflows/deploy.yml (issue #150).
#
# Multi-stage (issue #176): the `builder` stage carries build-essential (~200 MB),
# needed only to compile wheels during `uv sync`; the final `runtime` stage copies
# just the built `/app` (virtualenv + code) into a slim image and installs only the
# runtime libraries. libgomp1 is required by the gradient-boosting stack
# (xgboost/lightgbm); curl backs the healthcheck.
#
# Python is pinned to 3.13 to match .python-version / requires-python. Both stages
# share the same python:3.13-slim base, so the interpreter path baked into
# /app/.venv stays valid when the venv is copied forward. uv is pinned to a patch
# tag + digest for reproducible builds.

# ── builder: compile wheels and build the virtualenv ────────────────────────
# Base image digest-pinned (issue #176): both stages MUST use the identical
# digest so the interpreter baked into /app/.venv matches the runtime interpreter
# when the venv is copied forward. Refresh both pins together when bumping.
# Pinned 2026-06-17 (python:3.13-slim); digest-refresh automation tracked on #176.
FROM python:3.13-slim@sha256:c33f0bc4364a6881bed1ec0cc2665e6c53c87a43e774aaeab88e6f17af105e4f AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# build-essential is only needed here to compile any sdist-only wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# uv binary from the official distroless image (patch tag + digest pinned for
# reproducibility — issue #176; resolves to uv 0.5.31). Pinned 2026-06-17.
COPY --from=ghcr.io/astral-sh/uv:0.5.31@sha256:7bff3c3776ec467fc1437960f2c469d8beb30f536a6465a3350c647ccd260ec2 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached unless the manifests change). --no-dev still
# installs the `interpretability` group (shap) because it's in default-groups, so
# this beta image ships SHAP. For a slim production image (~57 MB lighter, drops
# shap+numba+llvmlite), append `--no-group interpretability` to both uv sync lines;
# the app degrades to model-native importance and `import app.main` stays valid
# (shap is lazy-imported). See pyproject.toml [dependency-groups] (issue #204).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code, then install the project itself into the venv.
COPY . .
RUN uv sync --frozen --no-dev

# ── runtime: minimal image with only the built venv + code ──────────────────
# Same digest as the builder above (see note there) — keep the two in sync.
FROM python:3.13-slim@sha256:c33f0bc4364a6881bed1ec0cc2665e6c53c87a43e774aaeab88e6f17af105e4f AS runtime

# MPLCONFIGDIR: matplotlib (pulled in by SHAP/visualization) needs a writable cache
# dir; as a non-root user it can't write under the root-owned /app home (issue #176).
# Point it at a dedicated dir pre-created + chown'd below. Keeps /app read-only and
# avoids a per-boot "temporary cache directory" fallback warning. (Comment kept above
# the ENV — inline comments inside a `\`-continued instruction are non-standard.)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    MPLCONFIGDIR=/var/cache/matplotlib

# Runtime-only libraries: curl for the healthcheck, libgomp1 for xgboost/lightgbm.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user (issue #176), mirroring the frontend image. Debian slim
# ships groupadd/useradd (not alpine's addgroup/adduser). uid/gid 1001 matches the
# frontend's convention. The copied venv/app are chown'd to this user below.
RUN groupadd --system --gid 1001 appuser \
    && useradd --system --uid 1001 --gid appuser --home-dir /app appuser \
    && mkdir -p "$MPLCONFIGDIR" \
    && chown appuser:appuser "$MPLCONFIGDIR"

WORKDIR /app

# Copy only what the server needs at runtime, leaving build/test artifacts
# (tests/, docs/, tasks/, sample_datasets/, pyproject.toml, uv.lock, …) out of
# the image: the virtualenv and the `app` package. gunicorn runs from
# WORKDIR /app, so /app is on sys.path and the package resolves. No compiler
# toolchain is carried forward. --chown hands ownership to the non-root appuser.
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/app /app/app

# Guard the targeted COPY above: fail the build if the runtime image is missing
# a top-level package the app imports (e.g. a future sibling of app/).
# Import only — no DB/lifespan side effects fire here. Runs as root pre-switch.
RUN python -c "import app.main"

# Drop privileges for the running server. gunicorn binds :8000 (>1024 → no root
# needed) and the curl healthcheck works as any user.
USER appuser

EXPOSE 8000

# Readiness, not liveness (issue #273): /health/ready 503s when Mongo is down, so
# a container with a dead dependency is marked unhealthy instead of "healthy while
# serving 500s". Matches the staging compose healthcheck.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/ready || exit 1

# gunicorn manages uvicorn workers; bind to all interfaces on 8000 (the staging
# compose maps host 8010 -> container 8000).
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
