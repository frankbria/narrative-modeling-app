# Issue #608 — [P3.25] [security] A column named 'ssn' is rated medium-risk, never high — the name match short-circuits the value check

Plan source: self-authored. Approved autonomously — AC2 asks for a deliberate boundary decision: name-only evidence stays medium (a label is a hint, values are proof); values decide high. No fork.

## Findings
- `detect_pii_in_dataframe` `continue`s after a name match, so values are never examined for the honestly-named column; `_check_column_name` returns 0.8 and the report's high threshold is `> 0.8` — name-only lands exactly on the boundary and is always medium.
- `/upload/secure` gates confirmation on `risk_level == "high"`, so a plainly-named SSN column skips the gate that a neutrally-named one triggers.

## Design
1. Always run the value check; when both signals exist, keep one detection per column carrying the stronger confidence (pattern match rate is the stronger evidence for real values).
2. Named constants: `NAME_MATCH_CONFIDENCE = 0.8`, `HIGH_RISK_CONFIDENCE = 0.8` (strictly greater → high), with the decision written next to them.
3. Tests: identical SSN values → same risk regardless of column name; `ssn` column of SSNs → `risk_level == "high"`; name-only (no matching values) stays medium; the `/upload/secure` gate returns `requires_confirmation` for an `ssn` column.
4. Blast radius (AC4): uploads whose PII-named column actually holds PII-shaped values move from medium to high → the confirmation route (which charges an upload unit only when it stores). Stated in the PR.

## Steps
- [x] RED tests
- [x] detector change (+ best-pattern-wins, named floor, coupled constants after review)
- [x] gate → PR #649 → demo → CI → merge
