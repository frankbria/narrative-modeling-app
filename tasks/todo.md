# Issue #470 — [P0.27] [frontend] Onboarding fetches relative /api/v1 URLs that 404

Plan source: self-authored; approved autonomously (no architectural fork).

## Design
- `lib/services/onboarding.ts`: one tiny client — `${API_URL}` + resource path, `Authorization: Bearer <apiToken>` from
  `getAuthToken()`, throws on `!ok` with the status. Functions for status/steps/achievements/complete/skip and the
  sample-dataset list/load. Used by `app/onboarding/page.tsx` AND `components/SampleDatasetSelector.tsx` (same class,
  same flow — found by the sweep).
- Page: `useAsyncData`'s `error` rendered (Alert + Retry); complete/skip failures shown in an Alert instead of console.
- Tests: page test asserts prefix + bearer, error state; selector test; `apiUrlConstruction.test.ts` pins the seven
  onboarding paths against the backend route table and gains a repo-wide guard against bare relative `/api/v1` literals
  (the existing guard only caught `${base}/api…` templates — this page had no base at all).
- e2e `@smoke`: reset onboarding through the backend with the session's API token, walk /onboarding to the
  Congratulations card, assert no onboarding request answered ≥ 400.

## Steps
1. [x] RED: page/selector/URL-pin/guard tests
2. [x] GREEN: service + page + selector
3. [x] e2e spec (run locally against the stack)
4. [x] Docs: CLAUDE.md NEXT_PUBLIC_API_URL bullet

## Acceptance criteria
- [ ] AC1 every onboarding fetch builds from NEXT_PUBLIC_API_URL + resource path
- [ ] AC2 requests carry the API bearer
- [ ] AC3 errors surfaced in the UI
- [ ] AC4 paths pinned in apiUrlConstruction.test.ts (+ class guard)
- [ ] AC5 e2e walks a new user to completion
