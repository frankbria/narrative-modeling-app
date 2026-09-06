# Issue #448 — [P0.5] Any tenant can hard-delete another tenant's dataset version

Branch: `fix/448-version-delete-ownership`

## Problem
`DELETE /api/v1/versions/{version_id}` looks the version up by id alone and calls
`version.delete()` — a permanent Beanie delete. `current_user_id` appears only in the
signature. Any authenticated user can destroy any tenant's version. Separately, the
docstring claims "Soft delete", which is false and reaches OpenAPI.

## AC2 — resolved as: keep the hard delete, make the docs honest

Not implementing soft delete. Reasons, in order of weight:
1. The service's own `cleanup_old_versions` hard-deletes (Mongo row + S3 object). A
   soft-delete flag on the route only would put two deletion semantics in one model.
2. It would require auditing all 14 `DatasetVersion` read paths; the issue itself says
   a half-applied soft delete is worse than an honest hard delete.
3. It cuts against GDPR erasure (#259/#497) — rows that survive deletion are the thing
   erasure exists to remove.
Hard delete is also the reversible choice: adding soft delete later is a clean change,
removing it once read paths depend on it is not.

## Plan
1. **RED** — route tests (`async_authorized_client`, real documents):
   - tenant A deleting tenant B's version → 404, and B's document still exists (AC4)
   - a foreign **base** version → 404, not the 400 "Cannot delete base version" —
     otherwise the guard below the lookup is an existence oracle
   - the owner can still delete their own non-base, unpinned version (regression)
2. **GREEN** — add `DatasetVersion.user_id == current_user_id` to the lookup (AC1).
   Ownership is then evaluated before the base/pinned guards by construction.
3. Rewrite the docstring to say the delete is permanent, and give the route an explicit
   `summary`/`description` so OpenAPI stops advertising a soft delete (AC2).
4. AC3 is conditional on choosing soft delete — not applicable.
5. Gate: pytest, ruff, mypy, cross-family review, demo.

## Out of scope, to be filed
`version.delete()` removes the Mongo row but not the S3 object, so every user-initiated
version delete orphans an artifact — while `cleanup_old_versions` 30 lines away deletes
both. Cost/hygiene, not a security hole; no existing issue covers it (#525 is
transformations, #521 is models). File separately rather than widen a P0 security fix.

## Acceptance criteria
- [ ] AC1 lookup filters on `current_user_id`; non-owner gets 404
- [ ] AC2 docstring + OpenAPI description say permanent; no contradiction left
- [ ] AC3 n/a (soft delete not chosen)
- [ ] AC4 route test: A cannot delete B's version; B's document survives
