# Issue #530: remove the dead parallel router registry

## Problem
`app/api/routes/__init__.py` builds an `api_router` that nothing mounts. It looks like
the place to register a router, and one registered only there is dead (the whole
data-issues feature 404'd that way, #471). `app/api/v1/__init__.py` is a second
aggregator of the same kind, imported by nothing.

## Plan
- [ ] RED: a test that fails while any module under `app/` other than `main.py`
      includes a router.
- [ ] Empty `app/api/routes/__init__.py`; delete `app/api/v1/`.
- [ ] Delete `app/api/routes/trained_model.py` (legacy CRUD, mounted only on the dead
      aggregator, no caller) and its allow-list entry. The `TrainedModel` document stays:
      the model registry and the erasure cascade use it.
- [ ] Every router the aggregators listed is mounted in `main.py` (the existing walk
      test covers it once the allow-list is empty).
- [ ] CLAUDE.md, gate, review, demo, PR.
