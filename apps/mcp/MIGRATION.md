# MCP Server Migration Notes

## Poetry → uv Migration (Completed)

**Migration Date:** December 2024
**Status:** ✅ Complete

### What Changed

The MCP server has been migrated from Poetry to uv for dependency management.

**Before (Poetry):**
```bash
poetry install
poetry run mcp dev server.py
poetry run pytest
```

**After (uv):**
```bash
uv sync
uv run mcp dev server.py
uv run pytest
```

### Migration Steps Completed

1. ✅ Converted `pyproject.toml` to PEP 621 standard format
   - Removed Poetry-specific `[tool.poetry]` sections
   - Added standard `[project]` section
   - Added `[tool.uv]` for uv-specific configuration

2. ✅ Generated `uv.lock` from dependencies
   - Lock file tracks exact versions of all dependencies
   - Compatible with Python 3.10+

3. ✅ Updated README.md with uv commands
   - All examples use `uv sync` and `uv run`
   - Installation instructions reference uv

4. ✅ Removed `poetry.lock` (outdated)
   - Last updated Nov 26, 2024
   - Replaced by `uv.lock` (Dec 31, 2024)

### Benefits of uv

- **Faster:** 10-100x faster than Poetry for installs
- **Simpler:** No separate tool installation needed (can use `npx uv` or install globally)
- **Standards-based:** Uses PEP 621 `pyproject.toml` format
- **Compatible:** Works with standard Python packaging ecosystem

### Current Configuration

**pyproject.toml structure:**
```toml
[project]
name = "mcp-modeling-server"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [...]

[tool.uv]
dev-dependencies = [...]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Verification

To verify the migration:
```bash
cd apps/mcp
uv sync                    # Install dependencies
uv run pytest             # Run tests
uv run mcp dev server.py  # Start server
```

All commands should work without Poetry installed.

### Rollback (Not Recommended)

If rollback is needed:
1. Restore `poetry.lock` from git history
2. Revert `pyproject.toml` to Poetry format
3. Run `poetry install`

However, uv is the recommended approach going forward.
