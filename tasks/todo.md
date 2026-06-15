# Issue #88 — [P3.4] Seamless stage transitions across the 8-stage workflow

## Reality check (verified against code, not the stale Traycer plan)
- **Backend (#87) is fully done**: `WorkflowState` model, `WorkflowService` (create/get/update/history),
  routes `POST/GET/PUT /api/v1/workflows/{dataset_id}` + `/history`, schemas, 25+ tests. Every PUT
  appends a `state_history` snapshot ⇒ transition recording already exists. **No new backend endpoint.**
- **AC3 (progress indicator)**: already done — `WorkflowBar` (global in layout) shows all 8 stages + completion.
- The Traycer plan's backend steps (1,2,3,11) and "POST /transition" are obsolete. This issue is **frontend UX polish**.
- **Routing gotcha**: stage routes are inconsistent — `explore/[id]`, `evaluate/[datasetId]`, `predict/[datasetId]`,
  `model/[id]` (a model *detail* viewer, NOT the training stage), but `prepare`/`features`/`deploy`/`model` stage
  pages have no dynamic segment. `completeStage`/`setCurrentStage` blindly push `/{route}/{datasetId}`, which 404s
  or mis-routes (e.g. `/model/{datasetId}` hits the detail viewer). Navigation must become **route-aware**.

## Acceptance Criteria
- [ ] AC1 — "Continue to next stage" CTA on each stage completion, data carried forward
- [ ] AC2 — Stage dependency guards redirect with a **helpful message** (not empty shells / silent /upload bounce)
- [ ] AC3 — Progress indicator showing 8 stages + completion state (✅ exists; verify only)
- [ ] AC4 — Back navigation restores prior stage state without losing work
- [ ] AC5 — Stage completion validation before transition
- [ ] AC6 — E2E test: complete journey upload → predict using only "Continue" CTAs

## Adapted Plan (frontend-only, TDD)

### Step 1 — Stage validation + navigation utility
- `apps/frontend/lib/utils/stageValidation.ts`: `validateStageCompletion(stage, stageData) -> {isValid, errors[]}`
  (per-stage required-field rules); `getNextStage`, `getPreviousStage`, `buildStageUrl(stage, datasetId)`
  (route-aware: only append id for parameterized routes), `getFirstIncompletePrerequisite(stage, completed)`.
- Tests: `__tests__/lib/utils/stageValidation.test.ts`

### Step 2 — WorkflowContext: navigation helpers + opt-out auto-advance + guard message
- Add `goToNextStage()`, `goToPreviousStage()` (route-aware via `buildStageUrl`).
- `completeStage(stage, data?, opts?: {autoAdvance?: boolean})` — default `true` (backward compatible);
  fix its auto-advance push to use `buildStageUrl`.
- Guard message: `guardMessage` state + `requestStageRedirect(targetStage, message)` + `clearGuardMessage()`.
- Extend `WorkflowContextType` in `lib/types/workflow.ts`.
- Tests: `__tests__/lib/contexts/WorkflowContext.navigation.test.tsx`

### Step 3 — Shared StageNavigation component
- `apps/frontend/components/workflow/StageNavigation.tsx`: Back (prev) + Continue (next stage name).
  lucide-react (ArrowLeft/ArrowRight), existing Tailwind button styling. Validates via stageValidation;
  shows errors; disabled/loading; final stage shows Finish/restart.
- Tests: `__tests__/components/workflow/StageNavigation.test.tsx`

### Step 4 — Stage guard hook + helpful-message banner
- `apps/frontend/lib/hooks/useStageGuard.ts`: gate a page; on denial redirect to nearest incomplete
  prerequisite with a helpful message (replaces silent `/upload` bounce). Respects `isHydrated`.
- `apps/frontend/components/workflow/StageGuardBanner.tsx` rendered in layout (global), reads `guardMessage`.

### Step 5 — Wire stage pages
- Adopt `useStageGuard` + `StageNavigation` on: prepare, features, model (gaps); standardize evaluate, predict, deploy.
- Set `autoAdvance:false` where an explicit Continue CTA is shown. Upload keeps its existing entry flow.

### Step 6 — E2E journey test
- `apps/frontend/e2e/workflows/stage-transitions.spec.ts`: upload → predict using only Continue CTAs;
  assert gated direct-access shows the guard message. Use a trainable dataset (ai-test-datasets), not 6-row sample.csv.

### Step 7 — Docs
- Update CLAUDE.md #88 section (backend reuse, guard message, StageNavigation, route-aware nav).

## Deviations from Traycer plan
- No new backend model/service/routes/transition endpoint — #87 already delivers persistence + history.
- WorkflowBar (AC3) already complete.
- `completeStage` auto-advance made opt-out (flag) to enable explicit Continue CTAs without breaking callers.
- Route-aware navigation added to fix latent `/{route}/{datasetId}` mis-routing.
