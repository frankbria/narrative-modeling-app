# Issue #465 — [P0.22] [bug] ~10 endpoints can never match a document (string vs ObjectId)

Plan source: self-authored; approved autonomously (no architectural fork).

## Design
- `app/utils/object_id.py::require_object_id(value, what="id") -> PydanticObjectId`, 400 on a malformed id (AC1).
- data_processing.py: six `UserData.id == file_id` sites → `== require_object_id(file_id, "file_id")`.
- transformations.py: four raw-dict `"_id": <str>` sites → `require_object_id(...)`; the four handlers also gain
  `except HTTPException: raise` — today they swallow the 404 into a 200 `{success: false}` or a 500.
- Sweep (AC2): `"_id": <var>` and `.id == <str>` across app/ — the ten sites are the whole class; `Document.get(str)`
  is coerced by Beanie and is not affected; `data_issues.py`/`model_training.py`/`ai_analysis.py` already coerce.
- Tests (AC3/AC4): `test_data_processing.py` rewritten on real seeded `UserData` docs (no `find_one` patch);
  new `test_object_id_lookups.py` asserts 200 on every previously-404ing endpoint against a real document,
  400 on a malformed id, 404 on unknown and foreign ids. `test_transformations_integration.py` stays mocked → #492.

## Steps
1. [ ] RED: real-document tests (10 endpoints × 200/400/404)
2. [ ] GREEN: helper + ten sites + re-raise in the four transformation handlers
3. [ ] Rewrite test_data_processing.py on real documents
4. [ ] Docs: CLAUDE.md gotcha (`UserData.id` is an ObjectId; coerce with `require_object_id`; handlers must re-raise HTTPException)

## Acceptance criteria
- [ ] AC1 both call-site families coerce; malformed → 400
- [ ] AC2 repo swept
- [ ] AC3 data-processing tests use real documents
- [ ] AC4 every previously-404ing endpoint has a 200-against-seeded-doc test
