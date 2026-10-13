# Issue #787: apps/mcp/uv.lock resolves a yanked numpy

## Problem
The MCP app's lock pins numpy 2.4.0 for Python 3.11 and later. That release was yanked
upstream ("Backward compatibility bug").

## Plan
- [x] `uv lock --upgrade-package "numpy<2.5"`: 2.4.0 -> 2.4.6, the newest patch of the same
      minor (published 2026-05-18). Not the plain upgrade, which also brought in 2.5.4,
      published three days ago.
- [x] Nothing else moves: pandas stays 2.3.3, mcp stays below 2 (#620), Python 3.10 keeps 2.2.6.
- [x] The mcp suite passes (39) and its pip-audit is clean.
