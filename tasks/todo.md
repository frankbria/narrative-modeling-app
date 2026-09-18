# #767 — P0.38 Plan-limit (402) experience + checkout confirmation

Plan source: self-authored (no plan comment on the issue). Branch: `feature/issue-767-plan-limit-402-experience`.

## Design decisions (autonomous, no architectural fork)
- **One error type**: `lib/services/apiError.ts` — `ApiError { status, detail }` and `QuotaExceededError extends ApiError` (metric, limit, used, tier, resets_at, upgrade_available; all but `metric` nullable so the thin `{error, metric}` variant parses). `apiError(response, fallback)` builds the right error from a `Response`; message = `detail.message` / string `detail` / fallback, so existing callers' messages are unchanged.
- **Dialog fires structurally, not per call site**: `apiError()` hands a `QuotaExceededError` to a tiny external store (`lib/billing/planLimit.ts`, `useSyncExternalStore`) that a single `PlanLimitDialog` mounted once in the authenticated root layout renders. Any surface that throws through `apiError` gets the dialog for free; the throw still happens so existing inline error text keeps working.
- **Chat proxy** passes the backend's 402 body through unchanged so the client parses it with the same helper (other upstream failures stay generic).
- **80% warning**: `UsageWarningBanner` (sibling of `StageGuardBanner` in the layout) fetches `/billing/status` once per mount and links to `/settings/billing`. Silent on any fetch failure.
- **Checkout confirmation**: billing page reads `?checkout=` via `useSearchParams` (Suspense-wrapped), shows success/cancel copy, polls status every 2s (max 15) until `tier` leaves the initial value, then reloads and clears the param via `router.replace`.
- **Contract test direction** follows the repo idiom: backend pytest reads the frontend TS constant `QUOTA_DETAIL_FIELDS` and asserts it equals the real 402 detail's keys.
- **E2E real 402**: FREE ceilings are lifted process-wide for the shared user (test-e2e.sh), and limits are per tier, so the only tenant that can hit a small ceiling is the second identity on a *different* tier: seed `test-admin-12345` a PRO `Subscription` in `seed_e2e_data.py` and set `PLAN_PRO_UPLOADS=2` in test-e2e.sh (the only sanctioned override surface). The spec uploads via the UI until the dialog appears (≤3 tries, counters persist across runs) and asserts the backend numbers + the action link. Deviation from AC5's "FREE user": the FREE branch (Upgrade → /settings/billing) is jest-covered.
- Prediction/batch calls live in `lib/services/model.ts`, not `production.ts` (which is API keys/metrics, unmetered) — model.ts is adopted wholesale; production.ts is adopted too so the class of hand-rolled throws shrinks.
- `/recommend-tools` and `/stage-guidance` have no frontend caller — nothing to adopt.

## Steps
1. [ ] `lib/services/apiError.ts` + `lib/billing/planLimit.ts` (+ `__tests__/lib/apiError.test.ts`): full 402 → QuotaExceededError with backend numbers + store populated; thin variant tolerated; non-402 → ApiError with status; message fallback preserved.
2. [ ] `components/billing/PlanLimitDialog.tsx` mounted in `app/layout.tsx` (+ test): metric words, used/limit, reset date, action by tier (free→Upgrade link `/settings/billing` with price; pro→mailto Contact us; enterprise→"highest plan").
3. [ ] Adopt: `lib/hooks/useChunkedUpload.ts` (init/chunk/complete/resume), `app/upload/page.tsx` (secure + confirm-pii), `lib/services/model.ts` (all sites), `lib/services/production.ts`, `lib/services/data-issues.ts`, `components/AIInsightsPanel.tsx`, `lib/hooks/useFeatureSuggestions.ts`, `components/AIChat.tsx` + `app/api/chat/route.ts` passthrough. Per-surface jest: a 402 body populates the store with the backend numbers.
4. [ ] `components/billing/UsageWarningBanner.tsx` in layout (+ test): ≥80% non-unlimited metric → amber `role="status"` banner with link; nothing when under, unlimited, or fetch fails.
5. [ ] `app/settings/billing/page.tsx` checkout param (+ tests): success → confirmation + bounded poll + param cleared; cancelled → notice + Upgrade button kept.
6. [ ] Backend: `tests/test_api/test_quota_enforcement.py` contract test parsing `QUOTA_DETAIL_FIELDS` from the TS file.
7. [ ] E2E: `scripts/seed_e2e_data.py` PRO subscription for admin; `test-e2e.sh` `PLAN_PRO_UPLOADS=2`; `e2e/workflows/plan-limit.spec.ts` (@smoke).
8. [ ] CLAUDE.md convention paragraph; run full frontend jest + lint + tsc, backend gate subset.

## Acceptance criteria
- [ ] AC1 one error type with status + parsed body; QuotaExceededError on 402, thin variant tolerated
- [ ] AC2 one PlanLimitDialog on upload (chunked + secure), training, batch + single prediction, every ai_calls surface; chat proxy adopts the copy
- [ ] AC3 ≥80% warning in the workflow shell with billing link
- [ ] AC4 checkout=success|cancelled handled on the billing page (bounded poll, param cleared)
- [ ] AC5 jest per surface, contract test vs enforcement.py, e2e real 402
- [ ] AC6 upgrade button shows price (already shipped in #775; unchanged)
