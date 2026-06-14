# Issue #156 — /api/v1/ml/train 404 + trainModel fixture masking

> Previous plan (issue #155 — prepare-page crash / data-preparation spec) was
> completed and merged in PR #194.

## Verify-before-fix findings
- **AC1 (train 404) — already fixed by #76.** `model_training.py:186-199` coerces
  the dataset id string to `PydanticObjectId` before lookup. Live e2e confirms
  `POST /api/v1/ml/train → 200`.
- **AC2 (fixture masking) — still valid.** `trainModel` returned `'mock-model-id'`
  on any failure, so downstream tests broke at predict with a misleading error.
- **AC3 (perf single-prediction smoke test) — still valid.** Was `test.fixme`.
  Re-enabling exposed a deeper issue: the 6-row `sample.csv` makes AutoML detect
  problem type "unknown" and fail (`ufunc 'divide' not supported`), so no model
  is ever saved. The fixme also referenced #157 (unrealistic 100ms threshold).

## Done
1. [x] **trainModel fixture fails loudly** (`e2e/fixtures/index.ts`): submit with
   bounded retries; throw with status+body on non-ok train, missing model id, or
   a ~60s poll timeout. No more `mock-model-id`.
2. [x] **Use a trainable dataset**: `uploadTestDataset` now accepts a relative
   path and uploads under its basename; the single-prediction test trains on
   `ai-test-datasets/binary-classification-small.csv` (200-row stratified subset
   of the 999-row binary `churned` set — the full file pegs a CI core and flakes
   neighbors, see #157). Fixed the `uploadTestDataset` fixture **type** to accept
   the optional filename.
3. [x] **Re-enable the perf single-prediction @smoke test** with a real predict
   payload (full feature record), a functional assertion (predictions array of
   length 1), a CI-safe 2000ms latency ceiling (~180ms observed locally; tight
   tuning deferred to #157), and `test.setTimeout(120000)` for train+poll.
4. [x] **Verified**: passes in `chromium-smoke` and `chromium-full`, stable across
   runs; `tsc --noEmit` clean; `next lint` (CI) clean.

## Acceptance criteria
- [x] `POST /api/v1/ml/train` accepts the upload dataset id string (coerce to ObjectId) — #76
- [x] `trainModel` E2E fixture fails loudly instead of returning a mock id
- [x] The fixme'd perf single-prediction smoke test is re-enabled and passes

## Out of scope (follow-up filed)
The loud fixture surfaces that other **manual `chromium-full`** tests
(error-scenarios, model-config, other performance tests) still train on the
un-trainable `sample.csv` and were vacuously passing / now fail loudly at train.
Not in the PR gate (those aren't @smoke). Follow-up issue: migrate them to a
trainable dataset. The batch-prediction test also targets a separate
`/api/v1/models/{id}/predict-batch` endpoint — left untouched.
