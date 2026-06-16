# Issue #157 — Stabilize flaky performance smoke tests (thresholds + timing)

## Root cause
Wall-clock timing assertions (`Date.now()` deltas around page loads / API calls) live
inside the **blocking `@smoke` gate** (`smoke-tests.yml`, runs on every PR). On shared
2-core GitHub runners those measurements are contention-sensitive, so identical code
passes and fails across runs. Functional smoke value (page loads, prediction works) is
worth keeping in the gate; the *timing* assertions are not.

## Decisions (confirmed with user)
1. **Split, don't retune** — re-tag timing tests `@perf`, remove `@smoke`.
2. **Dedicated non-blocking perf CI job** — new `perf-tests.yml`, records numbers, never blocks.
3. **Single-prediction SLO target = 1000ms** (was a 2000ms stability margin; ~180ms local).

## Plan

### 1. Introduce a `@perf` tag (test tagging)
- `e2e/workflows/performance.spec.ts`:
  - **Dashboard load test** (~line 33): remove `test.fixme` → `test`, swap `@smoke` → `@perf`,
    calibrate threshold to a CI-realistic **5000ms** (documented as a TTI ceiling for a
    2-core runner, not a tuned target). Keep the functional assert.
  - **Single-prediction test** (~line 182): swap `@smoke` → `@perf`, set
    `SINGLE_PREDICTION_BUDGET_MS = 1000` with a comment documenting the SLO rationale.
    Functional prediction smoke coverage already exists in `predict.spec.ts:136 @smoke`,
    so the blocking gate loses no functional coverage.

### 2. Transform contention (item 3)
- The two `transform.spec.ts @smoke` tests already carry `test.slow()` (landed in #156).
  Keep them in `@smoke` (they assert *functional* transformation, not timing); `test.slow()`
  triples their per-test timeout so 2-core worker contention no longer times them out.
- No worker-count change needed: removing the two heavy `performance.spec.ts` timing tests
  from `@smoke` (training + prediction were the core-pegging culprits per the issue) is what
  actually relieves the contention that flaked the transform specs.

### 3. Dedicated non-blocking perf CI job
- New `.github/workflows/perf-tests.yml`: mirrors `smoke-tests.yml` infra (Mongo + MinIO +
  backend + frontend), runs `@perf` on `chromium-full`, **`continue-on-error: true`** on the
  test step (records numbers, never fails the PR). Uploads the perf-results artifact.
- Add `test:e2e:perf` script to `apps/frontend/package.json` (`--grep @perf --project=chromium-full`).

### 4. Docs sync
- `e2e/README.md`: document the `@perf` tag, the non-blocking perf job, and that perf
  assertions are no longer in the blocking smoke gate. Update smoke listing.
- `CLAUDE.md`: add an issue #157 note under the testing section.

## Out of scope (YAGNI)
- No change to `playwright.config.ts` worker counts.
- No new PerformanceMonitor capabilities. No backend changes.

## Verification
- `npx playwright test --grep @smoke --project=chromium-smoke --list` → the two perf tests
  are **gone** from the smoke set; transform/predict smokes remain.
- `npx playwright test --grep @perf --project=chromium-full --list` → both perf tests collected.
- `npm run type-check` (tsc) green.
- Demo (Phase 11): smoke grep list before/after + the perf grep list as outcome evidence.
