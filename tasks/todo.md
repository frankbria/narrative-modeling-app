# Issue #76 — [P2.2] Real-time training progress monitoring

> Previous plan (issue #185 — WorkflowBar overflow) was **completed** and merged in PR #185
> (commit 5889331); see `git log tasks/todo.md`.

**Plan source**: CodeRabbit comment (2026-06-06, polling approach) — adapted to actual codebase state.

**Reality check (deviation from issue body)**: The issue claims the training page progress bar is a
"hardcoded animation". That is stale — `apps/frontend/app/model/page.tsx:90-153` already polls the
real `GET /api/v1/ml/{model_id}/status` endpoint every 2s (issue #75). The older Traycer WebSocket
plan is obsolete. What's actually missing: job list/dashboard, logs, cancellation, stage/ETA,
history browser, and robust poll-failure handling.

## Backend

### 1. Extend TrainingJob model (`apps/backend/app/models/training_job.py`)
- [x] `TrainingLogEntry` embedded model: `timestamp`, `level` (info/warning/error), `message`, optional `stage`
- [x] `logs: List[TrainingLogEntry]` field + `add_log(level, message, stage)` helper
- [x] `cancellation_requested: bool = False`
- [x] `current_stage: Optional[str]` on `TrainingProgress` (preprocessing / training / finalizing)
- [x] `mark_cancelled()` helper (JobStatus.CANCELLED already exists)
- [x] `elapsed_seconds` / `estimated_remaining_seconds` computed helpers (from `started_at` + progress fraction)
- Tests: `tests/test_models/` TrainingJob tests (extend)

### 2. AutoML engine: cancellation + stage/log events (`apps/backend/app/services/model_training/automl_engine.py`)
- [x] Optional `cancel_check: Callable[[], Awaitable[bool]]` param; checked before each candidate; raises `TrainingCancelledError`
- [x] Optional `log_callback` (or event callback) emitting stage transitions and per-candidate results
      (cv/test scores as each model finishes → live metrics)
- [x] Backward compatible — all params optional
- Tests: automl engine test extensions (cancellation mid-run, log emission)

### 3. Background task wiring (`apps/backend/app/api/routes/model_training.py` `train_model_task`)
- [x] Wire log callback → `job.add_log(...)` + save; wire cancel_check → re-read `cancellation_requested` from DB
- [x] Catch `TrainingCancelledError` → `mark_cancelled()` (not failed)
- [x] Emit logs: start, data download, per-stage, completion, failure
- [x] Append per-candidate comparison entries incrementally (live metrics in status response)
- Tests: `tests/test_api/test_model_training.py` background-task tests; integration test for cancel flow

### 4. New/extended endpoints (same `/api/v1/ml` router)
- [x] `GET /ml/jobs` — list user's TrainingJobs; status filter (running/completed/failed/cancelled/all) + pagination (follow `batch_prediction.py` pattern)
- [x] `GET /ml/{model_id}/logs` — paginated logs with optional level filter
- [x] `POST /ml/{model_id}/cancel` — ownership check; sets `cancellation_requested=True`; immediate ack; 409 if already terminal
- [x] Extend `TrainingStatusResponse`: `current_stage`, `elapsed_seconds`, `estimated_remaining_seconds`, `cancellation_requested`
- Tests: route tests for all new endpoints (auth, ownership, filters, 404/409)

## Frontend

### 5. Extend ModelService (`apps/frontend/lib/services/model.ts`)
- [x] `listTrainingJobs(filters)`, `getTrainingLogs(modelId, options)`, `cancelTraining(modelId)`
- [x] Extend `TrainingStatus` interface with new fields
- Tests: `__tests__/lib/services/model.test.ts`

### 6. New components (`apps/frontend/components/training/`)
- [x] `TrainingProgress.tsx` — extracted/enhanced from model page polling: progress bar, stage badge,
      current algorithm, elapsed + ETA, live comparison metrics, terminal-state Alerts
      (success w/ metrics summary, failure w/ error + view-logs, cancelled), exponential backoff on
      poll failures (2s→4s→8s→max 30s) + "connection lost" retry
- [x] `TrainingLogs.tsx` — level-styled log panel, 5s poll, level filter toggles, autoscroll
- [x] `CancelTrainingButton.tsx` — confirm via existing `Dialog` (no AlertDialog in repo), loading state, inline error
- Tests: `__tests__/components/training/*.test.tsx`

### 7. Integrate into model page (`apps/frontend/app/model/page.tsx`)
- [x] Replace inline polling block with `TrainingProgress` + collapsible `TrainingLogs` + `CancelTrainingButton`
- [x] Keep `completeStage(WorkflowStage.MODEL_TRAINING, ...)` wiring on completion
- Tests: model page test updates

### 8. Training jobs dashboard (`apps/frontend/app/training/page.tsx`) + nav
- [x] "In-Flight Training" section: live `TrainingProgress` cards w/ cancel
- [x] "Training History" table: status, duration, best score, created date; status filter
- [x] Sidebar link "Training Jobs" → `/training`
- Tests: dashboard component test

## Deviations from the CodeRabbit plan
- Training page already real-polls — extract/reuse rather than "replace fake animation"
- Endpoints under existing `/ml` prefix in `model_training.py` (not a new `/training-jobs` router) — consistent with #75
- Extend existing `ModelService` (not a new `trainingService.ts`) — `trainModel`/`getTrainingStatus` already live there
- Skip Redis progress caching (plan marked it optional; YAGNI at beta poll rates)
- `Dialog` instead of `AlertDialog` (latter not in `components/ui/`)
- Logs embedded in TrainingJob document (CodeRabbit Design Choice 2 retained)

## Acceptance criteria mapping
- [x] Dashboard of in-flight jobs → steps 4 + 8
- [x] Per model: progress %, stage, live metrics, elapsed + ETA → steps 1–4, 6
- [x] Training log panel (info/warning/error) → steps 1, 3, 4, 6
- [x] Completion/failure notifications → step 6
- [x] Cancel-training control → steps 2, 3, 4, 6
- [x] Historical training runs browser → step 8
- [x] Graceful fallback to polling → polling IS the channel; backoff + retry in step 6

## Status (2026-06-10)
All 8 steps implemented + committed. Quality gate: backend 374 affected-suite tests pass,
frontend 937 pass, tsc/ruff/black/eslint clean, frontend diff coverage 95%, 3 mutation checks
verified. Review fixes applied (codex 2 Majors: finalization cancel check, multi-status filter;
internal 1 Major: $push log appends + terminal re-fetch). Next: PR -> demo -> CI -> merge.
