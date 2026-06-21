# Issue #226 — Burn down backend mypy baseline

213 errors / 56 files in `apps/backend/mypy-baseline.txt`. CI tolerates baselined errors, fails on new ones. Done-condition: baseline empty → deletable, gate becomes plain `mypy app/`.

## Key insight
Errors cluster — far fewer than 213 distinct edits:
- `ab_testing.py`: one `metrics: dict[str, Any]` annotation clears ~10 (dict-value narrowing, not a logic bug).
- `datasets.py`: None-guards after `find_one`/`update_dataset` clear ~28 union-attr (real 500→404 fix).
- `mcp_integration.py`: 3 fields `str/int = None` → `| None` (always filled in `__post_init__`).

## Clusters (by code)
- P1 correctness: datasets union-attr (28) + arg-type (6); ab_testing (14); mcp_integration (3)
- Zero-risk mechanical: var-annotated (34, 16 files); annotation-unchecked notes (10)
- Medium: arg-type (rest), assignment (25), dict-item (12), operator, call-arg, index, return-value, list-item, misc, attr-defined

## Done
Baseline burned to zero and deleted; CI gate is now a plain `uv run mypy app/`
(the `mypy-baseline` tool was removed). `uv run mypy app/` → Success, 152 files.

## Verify
Full backend suite stays green (the None-guards change error semantics 500→404).
