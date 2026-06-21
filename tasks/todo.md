# Issue #195 — Migrate trainModel-based e2e tests off un-trainable sample.csv

Test-only PR. 8 manual `chromium-full` tests train on the 6-row `sample.csv`
(`purchased`) which AutoML can't fit; migrate to `binary-classification-small.csv`
(`churned`, 200 rows — the #157 light-training subset) and fix broken API
contracts. Not in the CI gate, so no merge-risk; demo = run them green on the live stack.

## In-repo exemplar (replicate this)
`performance.spec.ts` single-prediction test (already migrated in #157):
- `uploadTestDataset('ai-test-datasets/binary-classification-small.csv')` + `trainModel(id,'churned')`
- `const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'`
- `POST ${apiBase}/ml/${modelId}/predict` with `{ data: [ {9 cols} ] }`, header `Authorization: Bearer e2e-test-token`
- asserts `body.predictions` (array)
9 feature cols: age, tenure, monthly_charges, contract_type, has_internet, has_phone, payment_method, total_charges, support_calls.

## Shared helper (new)
`e2e/helpers/binaryClassificationData.ts`: `BINARY_CLASS_ROW` (one valid 9-col obj) + `makeBinaryClassRows(n)` generator. Refactor the exemplar test's inline payload to use it (DRY).

## Per-test changes
**performance.spec.ts (5):**
- batch (255): dataset+churned; **broken** `POST /api/v1/models/{id}/predict-batch` + `{features:batchData}` → `${apiBase}/ml/{id}/predict` + `{data: makeBinaryClassRows(100)}` + auth; assert `body.predictions.length===100`.
- metrics (355): dataset+churned; **broken** `GET /api/v1/models/{id}/metrics` → `${apiBase}/ml/{id}` + auth; assert `body.metrics`.
- confusion (419) + ROC (440): **DESCOPED** → `test.fixme` + follow-up issue **[P4.12]**. Evaluate page is stage-gated (needs WorkflowContext `state.modelId`, only set by full UI-workflow training, not the trainModel API fixture; evaluate.spec hedges with soft guards). Out of scope for this PR.
- concurrent (518): dataset+churned; `POST /api/v1/models/{id}/predict` (wrong prefix) + `{features:{age,income}}` → `${apiBase}/ml/{id}/predict` + `{data:[BINARY_CLASS_ROW]}` + auth.

**error-scenarios.spec.ts (1):** `:172/:173` dataset+churned. Pure client-side form-validation test (clicks predict unfilled) — no payload change. Remove any vacuous guard so the validation error is asserted.

**model-config.spec.ts:** `:701` metrics → in-test binary-class upload + churned + `GET ${apiBase}/ml/{id}` asserting `metrics` (clean API). `:253` compare → **DESCOPED** to [P4.12]: its compare UI lives on the stage-gated `/evaluate` Compare tab (#79), same gating class as the render tests; vacuous `if(visible)else log` today.

## DESCOPED to follow-up [P4.12] (all /evaluate-stage-gated UI)
confusion render, ROC render, compare → `test.fixme` + a [P4.12] issue for the workflow-seeding/evaluate-gating work.

## Final scope THIS PR = 5 tests
4 clean API (perf batch/metrics/concurrent, model-config metrics) + 1 seeded-UI (error-scenarios:171 predict, reuse predict.spec's `seedPredictionWorkflow` pattern → assert make-prediction button **disabled** when fields empty).

## Cross-cutting
- Remove vacuous `if (response.ok())` / `if (visible)` guards so tests assert (the issue's whole point).
- Perf timing budgets were set vs vacuous behavior; against real inference some are unrealistic (esp. 200ms/10-concurrent). → relax to realistic SLOs + `@perf` (non-blocking), per #157.
- Keep all tests **manual chromium-full** (do NOT promote to @smoke) — real training starves 2-core CI (#157). Document.

## Verify (demo)
Run migrated specs green on full live stack (backend+Mongo+MinIO+frontend, seeded e2e): `npx playwright test --project=chromium-full performance.spec.ts model-config.spec.ts error-scenarios.spec.ts`. Show before(red/vacuous)→after(green, real assertions).

## Out of scope (file separately if hit)
Backend bugs surfaced by now-real assertions → own issues (keep this test-only).
