# Quick uv Migration Steps

## 1. Install uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. Backend Migration

```bash
cd apps/backend

# Backup original
cp pyproject.toml pyproject.toml.backup

# Replace pyproject.toml with the new content below
# Then run:
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

### New Backend pyproject.toml
Save this as `apps/backend/pyproject.toml`:

```toml
[project]
name = "narrative-modeling-backend"
version = "0.1.0"
description = "Backend for the Narrative Modeling Application"
authors = [{name = "Frank Bria", email = "frank.bria@gmail.com"}]
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "sqlalchemy>=2.0.40",
    "python-multipart>=0.0.20",
    "beanie>=1.29.0",
    "motor>=3.7.0",
    "python-jose[cryptography]>=3.4.0",
    "python-dotenv>=1.1.0",
    "boto3>=1.37.28",
    "httpx>=0.28.1",
    "uvicorn>=0.34.0",
    "fastapi>=0.115.0",
    "pydantic>=2.11.0",
    "pydantic-settings>=2.2.1",
    "pandas>=2.2.3",
    "scikit-learn>=1.6.1",
    "numpy>=2.2.4",
    "sqlalchemy-utils>=0.41.2",
    "openai>=1.72.0",
    "jwt>=1.3.0",
    "asgi-lifespan>=2.1.0",
    "axios>=0.4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.5",
    "pytest-asyncio>=0.26.0",
    "black>=24.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["app"]
```

## 3. MCP Server Migration

```bash
cd apps/mcp

# Backup original
cp pyproject.toml pyproject.toml.backup

# Replace pyproject.toml with the new content below
# Then run:
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### New MCP pyproject.toml
Save this as `apps/mcp/pyproject.toml`:

```toml
[project]
name = "mcp-modeling-server"
version = "0.1.0"
description = "FastMCP server for Narrative Modeling App"
authors = [{name = "Frank Bria", email = "frank.bria@gmail.com"}]
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.2.3",
    "numpy>=2.2.4",
    "matplotlib>=3.8.4",
    "pydantic>=2.11.0",
    "scikit-learn>=1.6.1",
    "httpx>=0.28.1",
    "python-multipart>=0.0.20",
    "boto3>=1.37.31",
    "openai>=1.72.0",
    "python-dotenv>=1.1.0",
    "exceptiongroup>=1.2.2",
    "mcp>=1.6.0",
    "openapi-pydantic>=0.5.1",
    "rich>=14.0.0",
    "typer>=0.15.2",
    "websockets>=15.0.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.5",
    "black>=24.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
py-modules = ["main", "tool_runner"]
packages = ["tools", "models", "utils"]

[tool.uv]
virtualenvs.in-project = true
```

## 4. Test Everything

```bash
# Test backend
cd apps/backend
source .venv/bin/activate
python -m app.main

# Test MCP
cd apps/mcp  
source .venv/bin/activate
python main.py
```

## 5. Update .gitignore

Add these lines to `.gitignore`:
```
# uv
.venv/
uv.lock

# Poetry backups (remove after migration)
*.poetry-backup
poetry.lock.backup
```

## 6. Commit Changes

```bash
git add .
git commit -m "Migrate from Poetry to uv package manager"
```

## Benefits You'll See Immediately
- ⚡ Dependencies install in 5-10 seconds instead of 2-3 minutes
- 🚀 No more `poetry run` - just use `python` directly
- 💾 Better caching across projects
- 🔧 Simpler pyproject.toml format