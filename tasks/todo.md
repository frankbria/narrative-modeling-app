# Issue #446 — [P0.3] [security] IDOR: dataset version listing trusts a client-supplied user_id query param

Branch: `fix/446-versions-list-idor`

## Problem
`GET /api/v1/datasets/{dataset_id}/versions` takes `user_id` as a query param and passes it
to `versioning_service.list_versions()`, while the authenticated `current_user_id` is resolved
and never used. Omitting `user_id` sends `None`, which applies no owner filter at all.
The `total` count below it is also unscoped.

## Plan (self-authored from the issue's acceptance criteria; no plan comment existed)

1. **RED** — add route tests to `apps/backend/tests/test_api/test_versions.py`
   using `async_authorized_client` + real Mongo docs (never `mock_async_client`):
   - tenant A requesting tenant B's `dataset_id` → **404**
   - tenant A passing `?user_id=<B>` → still **404** (param is gone/ignored)
   - a foreign dataset that has versions does not leak `total`
   - existing owner-path tests still pass (list + pagination)
   - unknown `dataset_id` → **404**, identical to the foreign case (no existence oracle)
2. **GREEN** — `apps/backend/app/api/routes/versions.py::list_dataset_versions`:
   - delete the `user_id: str | None = None` query parameter (AC1)
   - add the same ownership guard `get_quality_trend` already uses two handlers below:
     `DatasetMetadata.find_one({"dataset_id": ...})`, 404 when missing or foreign
   - pass `user_id=current_user_id` to `list_versions` (AC2)
   - scope the `total_count` query with `user_id == current_user_id` (AC3)
3. Update `test_list_versions_nonexistent_dataset` (currently asserts 200 + empty list) to 404.
4. Quality gate: pytest, ruff, mypy, review.

## Autonomous decisions
- **Unknown dataset now 404s instead of 200-empty.** AC4 requires foreign → 404; leaving
  unknown at 200-empty would make the pair an existence oracle (404 = "exists, not yours").
  Matches `get_quality_trend` in the same file.
- Ownership guard inline in the handler, mirroring `get_quality_trend` — no new helper
  (the other handlers in this file are P0.4/P0.5/P0.10's scope, out of scope here).
- `versioning_service.list_versions` keeps its optional `user_id` signature; only the route
  changes. Other callers: none.

## Acceptance criteria
- [ ] AC1 `user_id` query param removed from the signature
- [ ] AC2 handler filters on `current_user_id`
- [ ] AC3 total-count query scoped the same way
- [ ] AC4 route test: A → B's dataset = 404; `?user_id=<B>` does not change the result
- [ ] AC5 tests use `async_authorized_client` + real Mongo documents
