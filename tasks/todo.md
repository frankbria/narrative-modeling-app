# #493 [P1.25] — e2e smoke gate runs with SKIP_AUTH=true, so it cannot catch an isolation regression

Plan source: the issue's analysis comment (2026-09-14). Adapted against the code on 2026-09-14.

## Why it is small
- The frontend e2e already runs real NextAuth; only the **backend** is started with
  `SKIP_AUTH=true` (`test-e2e.sh`). Two real identities already exist end to end:
  `test-user-12345` (ordinary) and `test-admin-12345` (admin, #613), each with a minted
  HS256 `session.apiToken` the backend verifies when SKIP_AUTH is off.
- Every UI-driven request already goes browser -> Next proxy -> backend with that token.
  What breaks under real auth is the set of **direct** backend calls in e2e that send a
  made-up bearer (`e2e-test-token`, `dev-user-default`): fixtures (`trainModel`,
  `cleanupDataset`, `cleanupModel`), `helpers/mlApi.ts`, `helpers/seedWorkflow.ts`, and
  inline seed helpers in predict / data-preparation / beta-journey / performance /
  model-config / ai-recommendations specs.

## Steps
1. `e2e/helpers/apiAuth.ts` — one helper: `apiAuthHeaders(request)` reads
   `/api/auth/session` (same-origin, uses the context's stored session) and returns
   `{ Authorization: Bearer <apiToken> }`; fails loudly when the session has none.
   Plus `signInAs(browser, baseURL, email, password)` — a fresh context logged in via the
   dev credentials provider (lifted from admin-guard.spec) — so a spec can act as the
   second tenant.
2. Replace every fake bearer with the real token (files above). `ML_AUTH` constant
   becomes `mlAuth(request)`. `cleanupModel` also gets the right URL (`/ml/{id}` on the
   backend; it was a relative `/api/v1/models/...` that never reached anything).
3. `test-e2e.sh` — drop `export SKIP_AUTH=true`; keep `RATE_LIMIT_ENABLED=false` and the
   `PLAN_*` lifts (still one shared ordinary user). Fix comments that explain SKIP_AUTH.
   `scripts/seed_e2e_data.py` — own the optional `--with-data` sample by `TEST_USER_ID`
   (the credentials id / token `sub`), not the NextAuth Mongo `_id`.
4. New `e2e/workflows/tenant-isolation.spec.ts` (`@smoke`): tenant A (stored session)
   uploads a dataset through the UI (UserData space) and seeds a `DatasetMetadata` via
   `POST /datasets/upload` (which also creates a base `DatasetVersion`), seeds a
   workflow, trains a model. Assert A reads each (proves the token path), then sign in
   as B (admin creds) and assert B cannot read A's dataset (both id-spaces), version
   list + version, workflow, or model — non-2xx and no dataset name in the body.
   RED first: with `SKIP_AUTH=true` still exported the spec must FAIL (B == A).
5. Docs: e2e README / CLAUDE.md notes that say "SKIP_AUTH collapses every e2e identity".

## Acceptance criteria
- [ ] AC1 e2e runs with real auth, two distinct users seeded (A = test user, B = admin)
- [ ] AC2 a @smoke test asserts A's dataset / model / version are unreadable by B
- [ ] AC3 no e2e subset keeps SKIP_AUTH (none needs it; `transformation-preview.spec`'s
      cookie hack is inert and stays out of smoke)
- [ ] AC4 stage-gated pages seed the real backend workflow under the real user

## Verification
- `cd apps/frontend && npm run test:e2e:smoke` locally (Mongo :27017 + LocalStack :4566)
  green; the isolation spec red under SKIP_AUTH=true (mutation check).
- `npm run lint`, `npm run type-check` (e2e is in lint scope).
