# Issue #191 — Fix drifted e2e upload fixture (uploadTestDataset)

> Previous plan (issue #79 — model evaluation dashboard) was **completed** and merged in PR #190
> (commit 78e5f7d); see `git log tasks/todo.md`.

Plan source: CodeRabbit Coding Plan comment (2026-06-12), adapted after codebase exploration.

## Adapted Plan

1. **Reproduce & diagnose (evidence first)**
   - Start backend (port 8000, SKIP_AUTH=true) + frontend (port 3010) per `scripts/test-e2e.sh` env
   - Run `e2e/workflows/upload.spec.ts` happy-path test; capture the actual failure: network response of POST /upload/secure, page state (error toast text vs stuck "Scanning for PII...")
   - Evidence so far: stale test artifact shows the upload POST never resolving (button stuck "Scanning for PII..."); issue body reports 200 + error toast. Root cause NOT yet confirmed — CodeRabbit's assumed workflow-state race is unsupported.
   - Files: none (diagnosis)

2. **Fix the actual root cause (app bug, if present)** — bug-ownership rule
   - Candidates: backend hang/slow path in `/upload/secure` (S3 upload, PII scan), invalid JSON from NaN in `df.head(5).to_dict('records')`, frontend response handling in `app/upload/page.tsx`, workflow gating race in `WorkflowContext`/explore page
   - TDD: write a failing test capturing the bug before fixing
   - Files: TBD by diagnosis (`apps/backend/app/api/routes/secure_upload.py`, `apps/frontend/app/upload/page.tsx`, `apps/frontend/lib/contexts/WorkflowContext.tsx`)

3. **Add error-state testids to upload page**
   - `data-testid="upload-error"` on error container, `data-testid="upload-error-message"` on error text
   - Files: `apps/frontend/app/upload/page.tsx`

4. **Harden `uploadTestDataset` fixture**
   - Wait for success text + `file-id` visibility before next-step click
   - Post-navigation stability check: URL stays on `/explore/{id}` (not redirected back to `/upload`), explore page content visible
   - Contextual failure messages: capture current URL + visible `upload-error` text in thrown errors
   - NO `networkidle` waits (Playwright anti-pattern) — explicit signals only
   - Retry-click fallback ONLY if diagnosis proves an unfixable race
   - Files: `apps/frontend/e2e/fixtures/index.ts`

5. **Sync UploadPage POM**
   - `waitForUploadComplete()` mirrors fixture success detection (file-id)
   - `continueToExplore()` gets the same stability check
   - New `hasUploadError()` via `[data-testid="upload-error"]`
   - Files: `apps/frontend/e2e/pages/UploadPage.ts`

6. **Fixture smoke spec (early drift detection)**
   - `apps/frontend/e2e/workflows/upload-fixture-smoke.spec.ts` (named/tagged to run early)
   - Happy path: valid dataset ID returned, URL contains `/explore/{id}` matching ID, explore content renders
   - Error path: invalid file → `upload-error` visible, stays on `/upload`, no `next-step-button`
   - Files: new spec

7. **Verify**
   - Run `upload.spec.ts` (expect the 8 fixture-blocked tests recovered), `evaluate.spec.ts` (6 tests reach dashboard), smoke spec green
   - `npm run type-check`, lint

## Acceptance Criteria (from issue)

- [ ] `uploadTestDataset` fixture works against the current upload UI
- [ ] `upload.spec.ts`: fixture-caused beforeEach failures eliminated (previously 3 passed / 8 failed)
- [ ] `evaluate.spec.ts`: all 6 tests reach the dashboard (no longer blocked in beforeEach)
- [ ] Smoke assertion that the fixture itself works runs as an early spec
- [ ] Error state assertable via data-testid

## Deviations from CodeRabbit plan

- Added Step 1 (reproduce/diagnose) — CodeRabbit chose "workflow-state race" without evidence; the stale failure artifact instead shows the upload request never resolving
- Added Step 2 (fix app root cause) — the issue may be an app bug, not just fixture drift; hardening the fixture alone could mask it
- Dropped `networkidle` waits and made the retry-click fallback conditional on proven need
