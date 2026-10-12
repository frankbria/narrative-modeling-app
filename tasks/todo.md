# #901 — a training job waiting for a slot is alive, and a reaped one does not train (P2.62)

Self-authored plan. Both defects reproduced first, in tests that fail on main.

## Decisions made here
- **Pump over the wait.** `_training_slot(training_job)` is an async context manager that
  logs the wait, runs `heartbeat_pump` while it waits for the semaphore, and releases the
  slot on exit. The run keeps its own pump inside, as before.
- **Re-read on taking the slot.** `_require_in_flight` raises `TrainingCancelledError`
  for a cancellation (as the inline check did) and `TrainingNoLongerInFlight` for a job
  already in a terminal state. The pump makes a reap during the wait rare, not
  impossible: a stalled worker misses beats too.
- **The handler for a job ended elsewhere writes nothing.** The reaper has set FAILED
  and refunded the run; any write from the task would overwrite that.
- **The waiting line is a partial write** (`_log_waiting_for_slot`).
- `train_model_task` itself stays over the complexity ceiling (the #842 exemption); the
  three helpers are small and tested.

## Steps
- [x] Failing tests: a queued job is not reaped; a job reaped while queued does not
      train and keeps the reaper's verdict; the waiting line keeps a cancellation; the
      on-slot check for each status and for a failed read.
- [x] The three helpers and the handler.
- [ ] Gate, cross-family review, PR, demo, CI, merge.
