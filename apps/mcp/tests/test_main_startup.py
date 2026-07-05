"""Regression: the server module must import without the vendored fastmcp.

Before #255, main.py added `fastmcp/src` to sys.path and imported a vendored
FastMCP that calls `importlib.metadata.version('fastmcp')` — but nothing
pip-installs `fastmcp`, so it raised PackageNotFoundError and main.py exited(1).
We now import FastMCP from the installed `mcp.server.fastmcp`.

Run in a subprocess with cwd=apps/mcp so `import mcp` resolves to the installed
SDK (under pytest's `pythonpath=..`, the bare name `mcp` would otherwise shadow
to the local app package).
"""

import subprocess
import sys
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parent.parent  # apps/mcp


def test_main_imports_without_vendored_fastmcp():
    result = subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=MCP_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "PackageNotFoundError" not in result.stderr
    assert "MCP startup failed" not in result.stdout
