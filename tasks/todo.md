# Issue #468 — [P0.25] [bug] Every model export format is broken — load_model called with wrong arity and wrong return shape

Plan source: self-authored; approved autonomously (no architectural fork; the issue's own split (a)/(b)/(c) is followed).

## Design
- (a) `ModelExportService` calls `model_storage.load_model(model.model_id, user_id)` and unpacks `(model, feature_engineer)`;
  the user_id is the authenticated caller (tenant scoping). Missing/foreign model → `NotFoundError` → 404 on every route;
  an unavailable format → `ExportFormatUnavailable` → 501. Routes stop mapping every ValueError to 400/404 blindly.
- (b) Docker ZIP carries `model.pkl` and `feature_engineer.pkl` (pickled from the loaded artifacts, the shape `inference.py`
  loads), `requirements.txt` pins the running scikit-learn/pandas/numpy; verified by building the produced image once.
- (c) ONNX: opt-in `export` dependency group (`skl2onnx`, `onnx`), NOT in default-groups; `get_export_formats` advertises
  only what is importable; PMML needs a Java runtime → stays 501 with a clear message (no group). No UI calls these routes.
- Tests rewritten against the real signature (mocked `load_model` returns a tuple; the test that patched the method under
  test is deleted); route-level 404 for a foreign model against a real MLModel; an end-to-end python/docker export from a
  real trained model saved through `model_storage` (S3 mocked at the storage seam).

## Steps
1. [x] RED: service tests on the real signature; foreign-model 404; ZIP contents
2. [x] GREEN: load call, typed errors, route mapping, ZIP artifacts, formats advertisement, dependency group
3. [ ] Docker build of an exported ZIP (demo)
4. [ ] Docs: CLAUDE.md gotcha

## Acceptance criteria
- [ ] AC1 load_model(model_id, user_id), tuple unpacked
- [ ] AC2 authenticated user; foreign → 404
- [ ] AC3 tests on the real signature; self-patching test gone; mutation-checked
- [ ] AC4 ONNX/PMML: optional group + 501 when absent
- [ ] AC5 Docker ZIP complete; image built once
