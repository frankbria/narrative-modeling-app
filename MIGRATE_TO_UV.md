# Migration Guide: Poetry to uv

## Overview
This guide helps migrate the Narrative Modeling App from Poetry to uv, a faster Python package manager by Astral (makers of Ruff).

## Why uv?
- **10-100x faster** than pip and poetry
- **Drop-in replacement** for pip
- **Built in Rust** for performance
- **Handles virtual environments** automatically
- **Compatible** with pyproject.toml

## Installation

### Install uv
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Migration Steps

### 1. Backend Migration (apps/backend)

#### Current Poetry Setup
```toml
# pyproject.toml uses [tool.poetry]
[tool.poetry.dependencies]
python = "^3.10"
fastapi = "^0.115.0"
# ... etc
```

#### Option A: Keep pyproject.toml (Recommended)
```bash
cd apps/backend

# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install from pyproject.toml
uv pip install -e .

# Install dev dependencies
uv pip install -e ".[dev]"
```

#### Option B: Generate requirements.txt
```bash
# Export from poetry first
poetry export -f requirements.txt -o requirements.txt --without-hashes
poetry export -f requirements.txt -o requirements-dev.txt --without-hashes --dev

# Then use uv
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
```

#### Update pyproject.toml for uv
```toml
# Change from poetry format to standard format
[project]
name = "narrative-modeling-backend"
version = "0.1.0"
description = "Backend for the Narrative Modeling Application"
authors = [{name = "Frank Bria", email = "frank.bria@gmail.com"}]
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115.0",
    "beanie>=1.29.0",
    "motor>=3.7.0",
    "boto3>=1.37.28",
    "pandas>=2.2.3",
    "scikit-learn>=1.6.1",
    "openai>=1.72.0",
    # ... rest of dependencies
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.5",
    "black>=24.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"
```

### 2. MCP Server Migration (apps/mcp)

```bash
cd apps/mcp

# Same process
uv venv
source .venv/bin/activate
uv pip install -e .
```

### 3. Update Scripts and Commands

#### Development Scripts
```bash
# Old (Poetry)
poetry run python -m app.main
poetry run pytest
poetry run black .
poetry run ruff .

# New (uv)
uv run python -m app.main
uv run pytest
uv run black .
uv run ruff .

# Or with activated venv
python -m app.main
pytest
black .
ruff .
```

#### Update Dockerfile
```dockerfile
# Old
FROM python:3.11-slim
RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

# New
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml ./
RUN uv venv && uv pip install -e .
```

### 4. CI/CD Updates

#### GitHub Actions
```yaml
# Old
- name: Install Poetry
  uses: snok/install-poetry@v1
  
- name: Install dependencies
  run: poetry install

# New
- name: Install uv
  uses: astral-sh/setup-uv@v3
  
- name: Install dependencies
  run: |
    uv venv
    uv pip install -e ".[dev]"
```

### 5. Update Documentation

#### README.md
```markdown
## Setup

1. Install uv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Create virtual environment and install:
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```

3. Run the application:
   ```bash
   uv run python -m app.main
   ```
```

## Common Commands Comparison

| Task | Poetry | uv |
|------|--------|-----|
| Create venv | `poetry install` | `uv venv` |
| Install deps | `poetry install` | `uv pip install -e .` |
| Add dependency | `poetry add fastapi` | `uv pip install fastapi` + update pyproject.toml |
| Run command | `poetry run python` | `uv run python` or just `python` with activated venv |
| Install editable | automatic | `uv pip install -e .` |
| Export requirements | `poetry export` | `uv pip freeze > requirements.txt` |

## Benefits After Migration

1. **Speed**: Dependencies install in seconds, not minutes
2. **Simplicity**: Standard pyproject.toml format
3. **Compatibility**: Works with all pip packages
4. **Performance**: Faster resolution and caching
5. **Modern**: Actively developed with frequent updates

## Troubleshooting

### Issue: Dependencies not found
```bash
# Make sure to use -e for editable install
uv pip install -e .
```

### Issue: Dev dependencies not installed
```bash
# Install with dev extras
uv pip install -e ".[dev]"
```

### Issue: Command not found
```bash
# Either activate venv first
source .venv/bin/activate

# Or use uv run
uv run <command>
```

## Final Cleanup

After successful migration:
1. Delete `poetry.lock` files
2. Remove `[tool.poetry]` sections from pyproject.toml
3. Update all documentation references
4. Update team guides

## Quick Start for Team

```bash
# One-time setup
curl -LsSf https://astral.sh/uv/install.sh | sh

# For each project
cd apps/backend
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run anything
python -m app.main
pytest
```