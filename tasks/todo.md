# #460 (P0.17) — batch-job retry re-runs every prediction with no quota reservation

## Verified against the code

- `POST /api/v1/batch/jobs/{job_id}/retry` (`batch_prediction.py:348`) has **no** `quota`
  dependency and no reserve. It calls `BatchPredictionService.retry_job`, which resets the
  job and calls `_spawn_processing`. Every prediction re-runs free.
- Creation does it correctly (`:133-183`): `dependencies=[Depends(quota("predictions"))]`
  reserves 1 at admission, then `reserve(request, user, "predictions", rows - 1)` charges
  the remainder **before** the job is created, because creation `auto_start`s processing.
- **The input survives.** `_prepare_input_data` uploads the CSV to
  `batch-jobs/{user}/{model}/{ts}/input.csv` in S3, so the temp file `create_batch_job`
  unlinks is irrelevant and a retry genuinely re-executes the work. This is not a dead path.
- **`progress.total_records` is reliable at retry time.** Set at creation
  (`batch_prediction.py:249`), and `retry_job` resets `processed_records` / counters but
  **not** `total_records`.

### One correction to the issue

The issue says "repeated retries give unlimited free predictions". It is **bounded at 3**:
`can_retry()` requires `status == FAILED and retry_count < max_retries` (3), and
`mark_failed` increments `retry_count`. So the ceiling is 3 free re-runs per job — which,
against `MAX_BATCH_PREDICT_RECORDS` of 1,000,000 and a FREE ceiling of 1,000, is still up
to 3,000× a monthly plan on one job. P0 stands; the word "unlimited" does not.

## Plan (TDD — RED first per step)

### 1. Reserve on retry, mirroring creation exactly (AC1, AC2)
- Add `dependencies=[Depends(quota("predictions"))]` to the retry route — reserves 1 at
  admission, and the refund middleware returns it on any >= 400 (unknown job, not
  retryable, quota denial).
- In the handler, load the job scoped to the caller, then
  `reserve(request, user_id, "predictions", total_records - 1)` when `total_records > 1`,
  **before** calling `retry_job` (which spawns processing immediately, same as creation).
- `reserve` appends to the reservation list rather than replacing, so the two charges
  accumulate — AC2 is a property of `reserve`, and gets a test rather than a change.

### 2. Denial is not silent (AC3)
- Quota denial raises 402 carrying metric/limit/used/resets_at/upgrade_available, and the
  job stays `FAILED` — it was not retried, which is the honest state.
- **Deliberately not** overwriting `job.error_message` with a quota message: that field
  holds why the job failed, and replacing it destroys the diagnostic the next retry needs.
  The 402 is the message naming the limit.
- The existing `400 "Job cannot be retried"` conflates three cases — unknown job, wrong
  status, retry budget exhausted. Split so a denied retry says which, since AC3 is about a
  denial being legible.

### 3. AC5 — is there an automatic retry?
- An explorer is sweeping for any non-user-triggered path that re-runs a job
  (`_spawn_processing` callers, background tasks, startup recovery, per-chunk retry loops).
  Findings fold into the plan before implementation; a chunk-level retry inside processing
  would be the same bug with no user in the loop.

### 4. Tests (AC4)
- Retry at the cap → **402**, and **no predictions executed** (job stays FAILED, status
  unchanged, nothing spawned) — asserting the 402 alone would not catch a version that
  denies *and* runs anyway.
- A retry under the cap charges `total_records`, not 1 — the whole point of the issue.
- Both reservations land (admission + remainder) rather than the second replacing the first.
- A denied retry refunds nothing extra and leaves usage exactly at the cap.

## Out of scope
- P1.14 (#486, the CSV row-count bug that can make a reservation 0) — named in the issue's
  Dependencies as a separate fix.
- #484 (no stale-job recovery) — unless the explorer finds a recovery path that re-runs
  predictions, in which case it is AC5's answer and comes into scope.
