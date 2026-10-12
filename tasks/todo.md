# Issue #936: a training job erased while it runs is written back by the task

## Problem
`train_model_task` holds its `TrainingJob` in memory. Its terminal handlers call
`_refreshed_job`, which returns that copy when the row is gone, then `save()` it, and a
Beanie `save()` of a missing document inserts it. An erasure of the dataset or account
during a run is undone: the job row comes back, and on success a model is stored too.

## Decision (the issue offers two)
The task stops recording, rather than erasure waiting for the task. Erasure stays
immediate; a fit in a worker thread cannot be killed anyway.

## Plan
- [ ] RED: `tests/test_api/test_training_job_erased_mid_run.py`: hold the stand-in fit
      open, erase the row, let the fit succeed / fail; and erase while the model is stored.
- [ ] After the engine returns, `_require_in_flight` (as on taking a slot): a job erased,
      reaped or cancelled during the fit builds and saves nothing.
- [ ] `_refreshed_job`: a row that is gone raises `TrainingNoLongerInFlight` after removing
      any model the task already saved, so no terminal path can insert the row again.
- [ ] CLAUDE.md, gate, review, demo, PR.

## Out of scope
- Killing the fit thread (not possible), refunding an erased run.
