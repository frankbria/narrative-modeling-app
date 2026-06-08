# Backend (FastAPI) production image — built by docker-compose.staging.yml and
# deployed by .github/workflows/deploy.yml (issue #150).
#
# Python is pinned to 3.13 to match .python-version / requires-python. uv manages
# the virtualenv; only runtime deps are installed (--no-dev). libgomp1 is needed
# by the gradient-boosting stack (xgboost/lightgbm); curl backs the healthcheck.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# uv binary from the official distroless image (pinned major for reproducibility).
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached unless the manifests change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code.
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# gunicorn manages uvicorn workers; bind to all interfaces on 8000 (the staging
# compose maps host 8010 -> container 8000).
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
