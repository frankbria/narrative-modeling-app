# Issue #447 — [P0.4] [security] Cross-tenant exfiltration on version creation

Branch: `fix/447-version-create-cross-tenant`

## Problem
`POST /api/v1/datasets/{dataset_id}/versions` reads `DatasetMetadata` and the latest
`DatasetVersion` filtered on `dataset_id` alone, then copies that content into a new
version written with `user_id=current_user_id`. An authenticated tenant can therefore
POST against any `dataset_id` and land the victim's data in their own account, readable
afterwards through legitimately-scoped endpoints. The write is correctly scoped, which
is what makes the unscoped reads easy to miss.

## Plan

1. **Extract `require_owned_dataset(dataset_id, user_id) -> DatasetMetadata`** — this is
   the third call site (`get_quality_trend`, `list_dataset_versions` from #446, and now
   `create_dataset_version`), which is the trigger I recorded on the issue during #446.
   Module-level helper in `versions.py`; 404 for unknown and foreign alike; raised
   outside each handler's `try` so the broad `except Exception` cannot mask it.
2. **RED** — route tests in `tests/test_api/test_versions.py`:
   - tenant A POSTing against tenant B's `dataset_id` → 404
   - **and no new `DatasetVersion` document exists afterwards** (AC4 — a status-only
     assertion would pass against a variant that copies then 500s)
   - the victim's version count is unchanged
   - the owner's own create path still works (regression guard on the refactor)
3. **GREEN** — `create_dataset_version`:
   - metadata lookup via `require_owned_dataset` (AC1, AC2)
   - scope the latest-version lookup with `user_id` too (AC3)
   - pass `current_user_id` through where the service accepts it
4. Repoint `get_quality_trend` and `list_dataset_versions` at the helper; their existing
   tests are the regression check that behaviour is unchanged.
5. Gate: pytest, ruff, mypy, cross-family review, demo.

## Autonomous decisions
- Plain async helper, not a FastAPI dependency — `get_quality_trend` ignores the return
  value while `create_dataset_version` needs the document, and a helper covers both
  without a second dependency shape.
- `get_version_content(version_id)` takes no `user_id` (the signature in
  `SECURITY_OWNERSHIP_CHECKS.md` is stale). Not widening the service signature here —
  scoping the two route-level reads closes the hole. Doc line corrected in docs-sync.

## Acceptance criteria
- [ ] AC1 `DatasetMetadata` lookup filters on `current_user_id`
- [ ] AC2 404 before any content is read
- [ ] AC3 latest-version lookup scoped too
- [ ] AC4 test proves 404 **and** no `DatasetVersion` created
- [ ] AC5 `async_authorized_client` + real documents
