# Issue #453 — [P0.10] [security] Version lineage and comparison endpoints are unscoped cross-tenant reads

Plan source: **self-authored** (issue had no plan comment). No architectural fork — proceeding.

## Context found in Phase 2

- `apps/backend/app/api/routes/versions.py` already has an in-file ownership helper
  `require_owned_dataset(dataset_id, user_id)` (added by #446), documented to be called
  **outside** a handler's `try` because the module's broad `except Exception` blocks
  would otherwise convert the 404 into a 500.
- `delete_version` (#448 / PR #560) scopes with the direct predicate
  `DatasetVersion.version_id == vid AND DatasetVersion.user_id == uid`. `DatasetVersion.user_id`
  is server-set on creation and indexed — this is the established owner predicate.
- `compare_versions` has **no** `except HTTPException: raise` clause, so any 404 raised
  inside its `try` becomes a 500. The ownership check must be raised before the `try`.
- `versioning_service.get_lineage_chain` walks `parent_version_id` calling
  `get_version(..., user_id=None)` — unscoped. Only two callers: the lineage route and
  `_find_lineage_path`.

## Steps

1. **RED** — add cross-tenant route tests to `apps/backend/tests/test_api/test_versions.py`,
   reusing the existing `foreign_dataset_with_versions` fixture / `make_version` / `OTHER_USER`:
   - A cannot read B's lineage → 404, no `OTHER_USER` in body.
   - Unknown version id and foreign version id answer identically (no existence oracle).
   - A cannot compare two of B's versions → 404.
   - A cannot compare one of their own against one of B's → 404 (both orderings:
     foreign as version1 and as version2 — checking only one still leaks the other).
   - Regression guards: owner path for lineage and compare still 200.
2. **GREEN** — `apps/backend/app/api/routes/versions.py`:
   - Add `require_owned_version(version_id, user_id) -> DatasetVersion` beside
     `require_owned_dataset`, same 404-for-unknown-and-foreign semantics, same
     "call outside the try" docstring warning.
   - `get_version_lineage`: call the helper before the `try`; drop the unscoped
     `DatasetVersion.find_one` existence check.
   - `compare_versions`: call the helper for **both** ids independently before the `try`.
   - `delete_version`: replace its inline scoped lookup with the shared helper
     (identical predicate and 404 detail string — this is the "single shared helper"
     the issue asks for).
3. **GREEN** — `apps/backend/app/services/versioning_service.py`: give
   `get_lineage_chain` an optional `user_id: str | None = None` and pass it into the
   `get_version` walk, so the returned chain is provably in-tenant rather than relying
   on `parent_version_id` never crossing datasets. Route passes `current_user_id`.
4. Quality gate: `pytest tests/test_api/test_versions.py tests/test_services/test_versioning_service.py`,
   then the PR-gate selection, ruff, mypy. Mutation-check the new tests.
5. PR → demo → CI → merge.

## Acceptance criteria (from issue)

- [x] AC1 — Both handlers resolve their version(s) with an owner predicate and return 404 for a non-owner.
- [x] AC2 — `compare_versions` checks **both** version ids independently (both orderings tested).
- [x] AC3 — Route tests cover: A cannot read B's lineage; A cannot compare two of B's
      versions; A cannot compare one of their own against one of B's.

## Second round — pre-PR cross-family review (opencode / GLM) found three real defects

The first fix scoped the lineage *walk* through `versioning_service.get_version(user_id=...)`,
which was not enough:

1. **HIGH — the per-hop check fell open on an orphaned version.** `get_version` authorizes by
   joining to `DatasetMetadata` and reads `if dataset and dataset.user_id != user_id`, so a hop
   whose dataset row is gone skipped the check entirely and its lineage record — B's columns,
   row counts and transformation parameters — landed in a 200.
2. **MEDIUM — `compare_versions` never threaded the caller down to `_find_lineage_path`,**
   so both of its `get_lineage_chain` walks ran unscoped. Owning both endpoints does not make
   the path between them the caller's: B's `lineage_id`s reached `lineage_path` and B's
   transformations were counted in `transformation_count`.
3. **LOW — predicate mismatch truncated the owner's own chain.** The route authorizes on
   `DatasetVersion.user_id` while the walk re-authorized the same entry hop on
   `DatasetMetadata.user_id`; a drifted or missing dataset row answered 200 with an empty
   chain — a silent wrong answer.

All three collapse into one change: walk on `DatasetVersion.user_id` (the predicate the routes
already use) and thread `user_id` through `compare_versions` → `_find_lineage_path` → both
walks. Three more tests added, each verified to fail against the first fix.

## Autonomous decisions

- Owner predicate is `DatasetVersion.user_id`, not a `DatasetMetadata` join — matches the
  predicate #448 shipped for `delete_version`, is indexed, and avoids the second round trip.
  (`versioning_service.get_version`'s dataset-join check has an `if dataset and ...`
  fallthrough that admits a version whose dataset row is missing; the direct predicate has no
  such hole. Not changing that service method here — out of scope, no route in this issue uses it.)
- Ownership check raised **before** the `try` in every handler, per the existing helper's docstring.
