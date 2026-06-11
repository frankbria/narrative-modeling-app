# Issue #76 — Demo / Acceptance Evidence

PR #187 · branch `feature/issue-76-training-progress-monitoring` · demo executed 2026-06-11 against
local backend (:8000, SKIP_AUTH dev mode, local MongoDB `narrative_demo`) + frontend dev (:3000),
real S3 uploads, real AutoML training runs (15k×12 and 49k×80 datasets). Full narrated Showboat
demo with screenshots: `/tmp/demo-issue-76/demo.md` (artifacts intentionally not committed).

Each acceptance criterion mapped to **outcome evidence** (not just "rendered" / "exited 0").

| # | Criterion | Action | Outcome evidence | Status |
|---|---|---|---|---|
| 1 | Dashboard of in-flight jobs | Started a 49k×80 cv-30 job; opened `/training` | Live card with target, dataset, status badge, progress bar, Cancel button; `GET /ml/jobs?status=running` returns the job | VERIFIED |
| 2 | Progress %, stage, live metrics, elapsed + ETA | Polled status mid-run | `running, 50%, XGBoost, stage=training, elapsed=205.9s, ETA=205.9s`; per-candidate cv/test scores stream into `model_comparison` and logs as each finishes | VERIFIED |
| 3 | Log panel (info/warning/error) | Expanded "Show Logs" during a UI-started run | Timestamped, stage-badged, level-styled entries with filter toggles; logs API returned the 11-entry lifecycle (start → download → stages → per-candidate scores → completion) | VERIFIED |
| 4 | Completion & failure notifications | UI run completed; a real failed job | Success alert "Training complete — Best model: Logistic Regression (CV score 0.892)" + plain-language explanation + Model Evaluation stage unlocked; failure alert rendered for a failed run; failed job has `status=failed` + error log entry | VERIFIED |
| 5 | Cancel-training control | Dashboard card → Cancel Training → confirm dialog | Flag acknowledged immediately (`cancellation_requested=true` while running); job → `cancelled` after the in-flight algorithm finished (3m 24s); log trail: "Cancellation requested" → RF finishes → "Training cancelled by user"; second cancel → HTTP 409 | VERIFIED |
| 6 | Historical runs browser | History table + status filter | Rows show status/duration/best algorithm/score/date; "Cancelled" filter re-queries backend and shows the cancelled run keeping partial results (best score 0.783 from finished candidates) | VERIFIED |
| 7 | Graceful fallback to polling | Deleted the job document mid-run (forced real 404s) | Exponential backoff (2s→4s→8s, max 30s); after 3 consecutive failures: "Connection lost — retrying" + manual Retry button | VERIFIED |

## Bugs found and fixed during the demo (all committed to the PR)

1. **Build Model target dropdown always empty** — page fetched `/datasets/{id}/schema` with a
   UserData id (404 in the real upload flow); now reads `data_schema` from `/user_data/{id}`.
2. **`POST /ml/train` 404 for every real dataset** — `UserData.id` (ObjectId) was compared to the
   raw request string; existing tests masked it by patching `find_one`. Now coerced, with an
   unpatched regression test.
3. **Event loop blocked during training** — sklearn fit/CV/predict ran inline in the async
   background task, freezing every API request (status polls and the cancel endpoint) for the
   duration of each fit. Now `asyncio.to_thread`; cancellation acknowledgment went from
   "queued behind the whole run" to immediate.

## Reviewer feedback addressed pre-demo
- **codex (cross-family), 2 Major**: final cancel check before finalization; history must filter
  before paginating (backend comma-status filter).
- **Internal review, 1 Major**: `$push` log appends + re-read before terminal saves (the demo's
  cancelled-job log trail shows the fix working live).
- **CodeRabbit, 4 inline**: 2 applied (in-flight dedupe by model_id; stale-response guard on
  history fetch — mutation-verified), 2 rebutted ('warn' vs 'warning' — backend literal IS
  'warning'; logs tail-paging — volume bounded by candidate count, documented limitation).
