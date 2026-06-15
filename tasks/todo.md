# Issue #152 — [P4.2] Beta launch readiness: onboarding integration, user docs, feedback collection

**Plan source:** CodeRabbit comment plan, adapted to the actual codebase.
**Branch:** `feat/152-beta-launch-readiness`

## Acceptance Criteria (from issue)
- [ ] AC1: Onboarding flow triggers for new users and records completion via `/api/v1/onboarding/*`
- [ ] AC2: User-facing quickstart guide (upload → profile → prepare → features → train → evaluate → predict)
- [ ] AC3: In-app feedback mechanism wired to storage
- [ ] AC4: Full user-journey integration test (the 10 beta acceptance criteria in `BETA_ROADMAP.md`)
- [ ] AC5: Performance sanity check: p95 API < 500ms on the journey's endpoints

## Adapted Steps (TDD: RED → GREEN → REFACTOR)

### Step 1 — Backend: Feedback collection endpoint  → AC3
- `apps/backend/app/models/feedback.py`: `Feedback(Document)` — `feedback_id` (indexed), `user_id` (indexed), `rating` (1–5), `category` (enum), `message`, `page_context` (optional), `created_at`. `Settings.name = "feedback"`.
- Register `Feedback` in `apps/backend/app/models/registry.py`.
- `apps/backend/app/schemas/feedback.py`: `FeedbackCategory` enum (bug, feature_request, general, onboarding), `FeedbackRequest`, `FeedbackResponse`.
- `apps/backend/app/api/routes/feedback.py`: `POST /api/v1/feedback` (auth via `get_current_user_id`, 201; 422 on validation).
- Register router in `apps/backend/app/main.py`.
- Tests: `apps/backend/tests/test_api/test_feedback.py` (mongomock, mirrors `test_onboarding.py`): 401 unauth, 201 valid, 422 invalid rating/category, persistence.

### Step 2 — Frontend: Onboarding flow integration  → AC1
- `apps/frontend/app/auth/new-user/page.tsx`: both OAuth `callbackUrl: '/'` → `'/onboarding'`.
- `apps/frontend/middleware.ts`: add `/onboarding` to `protectedRoutes`.
- `apps/frontend/lib/hooks/useOnboardingStatus.ts`: fetch `GET /api/v1/onboarding/status` → `{ isComplete, isLoading, currentStepId }` (uses `getAuthToken`/`API_URL`).
- `apps/frontend/app/dashboard/page.tsx`: redirect to `/onboarding` if incomplete, with a "Skip for now" bypass persisted to localStorage so returning users aren't trapped.
- Tests: `apps/frontend/__tests__/lib/hooks/useOnboardingStatus.test.tsx`.

### Step 3 — Frontend: Quickstart guide + doc-link fixes  → AC2
- `apps/frontend/app/quickstart/page.tsx`: static doc page covering the 8 stages (purpose / key actions / expected outcome / nav hint each) with anchor navigation; Card/Accordion + lucide icons.
- Fix `/docs` links → `/quickstart`: onboarding completion screen, `OnboardingStep` Help buttons, dashboard help section.
- Test: `apps/frontend/__tests__/app/quickstart.test.tsx` (renders all 8 stages).

### Step 4 — Frontend: Feedback widget  → AC3
- `apps/frontend/components/FeedbackWidget.tsx`: floating bottom-right button → expandable form (star rating, category select, message textarea); POST `/api/v1/feedback` with `page_context = location.pathname`; inline success/error states (no new toast dep).
- Mount in `apps/frontend/app/layout.tsx` inside the authenticated session block.
- Tests: `apps/frontend/__tests__/components/FeedbackWidget.test.tsx` (open, validate, submit success/error).

### Step 5 — E2E: Beta journey + performance + feedback  → AC4, AC5
- `apps/frontend/e2e/workflows/beta-journey.spec.ts` (`@beta-acceptance`):
  - Onboarding routing scenarios (new → onboarding; returning-incomplete → onboarding; completed → dashboard) — backend mocked via `page.route` (stage-transitions pattern).
  - Full journey mapped to the **10 `BETA_ROADMAP.md` criteria** (reuse `WorkflowOrchestrator`).
  - Feedback widget: open → fill → submit → success + error handling.
  - p95 < 500ms assertions (extend `PerformanceMonitor`) for `/api/v1/onboarding/status`, `/api/v1/datasets`, `/api/v1/ml/train`, `/api/v1/ml/{id}/predict`.
- Note: E2E suite is **not** in the CI gate (manual `workflow_dispatch`).

## Deviations from the original CodeRabbit plan
1. **`BETA_ROADMAP.md` exists** — integration test maps to its real 10 criteria (CodeRabbit assumed it was missing and substituted the 8-stage list).
2. **Icons: `lucide-react`** to match the existing codebase (CLAUDE.md's "Hugeicons, never lucide" applies to new Nova projects, not this legacy app).
3. **No toast dependency** — widget uses inline success/error states (YAGNI; no Sonner/Toaster in the app today).
4. **Feedback persisted via a dedicated Beanie `Feedback` model** registered in `registry.py` (backend convention), not a raw collection insert.
5. **Corrected perf-test endpoint paths** to the real routes: `/api/v1/ml/train`, `/api/v1/ml/{id}/predict` (plan said `/api/v1/models/...`).
6. **Onboarding skip-persistence** added so the dashboard redirect doesn't trap returning users.
