# #653 — batch admission: an exact per-tenant cap and a wall clock per job (P1.63)

Self-authored plan (the issue has acceptance criteria for both halves, no plan).

## Decisions made here
- **A slot index, not a counter.** A live job holds one numbered slot of its tenant
  (`admission_slot` in `0..cap-1`); the unique partial index `user_live_slot_unique`
  covers only PENDING/RUNNING rows. A create tries each slot and is refused when all
  collide. A counter document would need a decrement on every path to a terminal state
  (finish, failure, cancel, the reaper, a crash), and one missed path locks a tenant out;
  here the status write itself frees the slot. The issue offered a counter or a claim
  row; this is the claim row, with the job as its own claim.
- **The claim is made when the job row is written, after the upload.** The count stays
  as the early refusal before the upload (#515), so the common case still uploads
  nothing. A create that then loses the race for the last slot deletes the input it
  just uploaded (the key is the job's own).
- **`retry_job` claims a free slot**, not the number the failed job once held, which
  another live job may hold by now.
- **The wall clock is one setting**, `BATCH_JOB_WALL_CLOCK_SECONDS` (default 3600), not
  per tier. On expiry the job is written FAILED only if it is still RUNNING, and the
  records it never reached are refunded, as a cancel does.
- **`asyncio.wait`, not `wait_for`:** the run fires the completion webhook from its own
  `finally`. With `wait_for` that webhook would report RUNNING.
- `_run_batch_job` (cc 24) is not touched.
- From the cross-family review: **a run's remainder is refunded once**
  (`BatchJob.remainder_refunded`, claimed in `_refund_remainder`). A cancel is refunded by
  the run when it notices; a hung run never notices, so the wall clock makes that refund,
  and the marker stops the two from both doing it. The queue's skip of a job cancelled
  before it started now refunds too (it returned without one).
- The create route stored the input size with a full `job.save()` after processing was
  spawned. It is a one-field write now, which meant splitting the handler (cc 10) into
  `_require_csv`, `_reserve_rows` and `_create_job_from_upload`.
- The partial index filter uses `$in`, which needs MongoDB 6.0 or later (CI runs 7.0,
  local 8.0).

## Acceptance criteria (from the issue)
- [x] AC1: per-user admission is atomic; a same-tenant burst cannot exceed
      `MAX_CONCURRENT_BATCH_JOBS_PER_USER`.
- [x] AC2: a test spawns N concurrent creates for one tenant and at most the cap are
      admitted.
- [x] AC3: a run is under a wall clock; a timeout marks the job FAILED with a clear
      reason and releases the execution slot.
- [x] AC4: a test: a job whose processing never returns is failed within the bound and
      does not hold the semaphore.

## Steps
1. Tests first: a burst of 8 against a cap of 3; a finished job frees its slot; a retry
   takes a free slot; a hung run is failed and frees the semaphore; a cancel is not
   overwritten; a quick run is untouched.
2. `BatchJob.admission_slot` and the index.
3. `_admit`, `_discard_input`, `_claim_retry`; `_process_batch_job` and
   `_fail_at_wall_clock`; `_finalize_if_running` reports whether it wrote.
4. CLAUDE.md: the batch concurrency paragraph.
