# E2E Testing Guide

Playwright specs in `apps/frontend/e2e/` drive the real stack: Next.js dev server,
FastAPI backend, MongoDB and LocalStack S3, with real NextAuth sign-in. Backend unit and
integration tests: [TEST_INFRASTRUCTURE.md](TEST_INFRASTRUCTURE.md).

## Prerequisites

- MongoDB on `localhost:27017` (`MONGODB_URI` overrides; database `narrative-modeling-test`).
- LocalStack on `localhost:4566`. Upload-dependent specs fail without it:
  ```bash
  docker compose -f apps/backend/docker-compose.test.yml up -d localstack
  ```
- Backend dependencies (`cd apps/backend && uv sync`) and frontend dependencies
  (`cd apps/frontend && npm install`).
- A browser: `cd apps/frontend && npx playwright install chromium` (`--with-deps` on a
  fresh Linux box).

## Running

Always go through `test-e2e.sh` (the `test:e2e*` scripts call it). It frees ports 3010
and 8000, exports the test environment, starts the backend, seeds MongoDB with
`apps/backend/scripts/seed_e2e_data.py`, starts the frontend on 3010, runs Playwright with
any extra arguments, then stops both servers.

```bash
cd apps/frontend
npm run test:e2e:smoke                                 # @smoke on chromium-smoke (the CI gate)
npm run test:e2e:full                                  # every spec on chromium-full
npm run test:e2e:all                                   # chromium, firefox and webkit
npm run test:e2e:perf                                  # @perf on chromium-full
npm run test:e2e -- e2e/workflows/train-form.spec.ts --project=chromium-full   # one file
npm run test:e2e:ui                                    # Playwright UI mode
npm run test:e2e:debug                                 # Playwright inspector
npm run test:e2e:report                                # open the last HTML report
```

Logs: `/tmp/backend-e2e.log`, `/tmp/frontend-e2e.log`. Wait budgets:
`E2E_BACKEND_WAIT_SECONDS` (90), `E2E_FRONTEND_WAIT_SECONDS` (120).

What `test-e2e.sh` sets, and why:

- `SKIP_AUTH=false`, explicitly (#493). The backend verifies the token the frontend mints
  with the shared `NEXTAUTH_SECRET`; an unset value would be filled from `.env`, which
  ships `SKIP_AUTH=true`. Never set it to `true` here: every identity would collapse into
  one backend user and `tenant-isolation.spec.ts` could not see a cross-tenant read.
- Dev-credentials identities: `TEST_USER_EMAIL`/`TEST_USER_PASSWORD` (the shared user),
  `TEST_ADMIN_EMAIL`/`TEST_ADMIN_PASSWORD` (the only entry in `ADMIN_EMAILS`, seeded on
  PRO), and `TEST_ISOLATED_USERS=1` (the users in `e2e/isolatedUsers.ts`).
- `RATE_LIMIT_ENABLED=false` and raised `PLAN_FREE_*` / `MAX_CONCURRENT_TRAINING_JOBS_PER_USER`
  limits, because parallel workers share one user. `PLAN_PRO_UPLOADS=2` lets
  `plan-limit.spec.ts` hit a real 402 as the admin tenant. This is the only place
  `PLAN_*` overrides are set.
- `AWS_ENDPOINT_URL=http://localhost:4566` when LocalStack answers there.

## Projects and tags

Projects (`playwright.config.ts`): `chromium-smoke` (only `@smoke`), `chromium-full`,
`firefox-full`, `webkit-full`. Retries are 2 in CI and 0 locally; traces are kept on the
first retry; screenshots and video on failure.

| Tag | Meaning | Where it runs |
|---|---|---|
| `@smoke` | critical paths | `e2e-smoke` job in `ci.yml`, every PR |
| `@perf` | performance budgets | on demand (`test:e2e:perf`) |
| `@concurrency` | concurrent load | on demand |
| `@beta-acceptance` | beta journey checks | with the full suite |

`e2e-tests.yml` runs `npm run test:e2e:full -- --grep-invert "@perf|@concurrency"` nightly
and opens or closes a `[P2] [testing] The nightly full e2e suite is failing` issue.

## Layout

```
apps/frontend/e2e/
├── global-setup.ts        # signs in the shared user (and isolated users) once
├── isolatedUsers.ts       # users for specs that change account-scoped state
├── fixtures/index.ts      # test, expect, authenticatedPage, uploadTestDataset, cleanupDataset, trainModel, aiMock
├── helpers/               # apiAuth (apiAuthHeaders, signInAs), seedWorkflow, landing, gluedText, layoutProblems, ...
├── capture/               # *.capture.ts: re-records public/how-it-works media (not a spec, never in CI)
├── pages/                 # page objects: Base, Upload, Evaluate, Predict
├── workflows/             # *.spec.ts
├── recipes/               # recipe-management.spec.ts
└── test-data/             # CSVs; ai-test-datasets/ holds trainable sets
```

## Writing a spec

```typescript
import { test, expect } from '../fixtures';
import { seedFeaturesWorkflow } from '../helpers/seedWorkflow';

test('a column left out is left out of training @smoke', async ({
  authenticatedPage: page,
  request,
  uploadTestDataset,
  cleanupDataset,
}) => {
  const datasetId = await uploadTestDataset();
  await seedFeaturesWorkflow(page, request, datasetId);

  await page.goto('/features');
  await expect(page.getByRole('checkbox', { name: 'age', exact: true })).toBeChecked();
  // ...drive the page, assert on what the backend received...

  await cleanupDataset(datasetId);
});
```

Rules (enforced by review, and by `__tests__/e2e/noEarlyReturns.test.ts` where noted):

- Import `test`/`expect` from `../fixtures`. `e2e/fixtures/auth.ts`'s `authenticatedPage`
  is deprecated.
- Assertions must be able to fail: no assertions inside `try/catch` or
  `if (await x.isVisible())`, and no bare `return;` (guarded). Seed preconditions instead
  (`seedEvaluationWorkflow`, `trainModel`).
- Assert a stage landing with `expectLandedOnStage(page, url, '<Stage>')`
  (`helpers/landing.ts`), never the URL alone.
- Locate by role and accessible name or `data-testid`, not page-global
  `button:has(svg).first()`.
- Direct backend calls take headers from `apiAuthHeaders(request)`; a second tenant comes
  from `signInAs`. A new owned surface joins the `owned` list in
  `workflows/tenant-isolation.spec.ts`.
- A spec that resets, erases or re-plans an account runs as its own user:
  `test.use({ storageState: isolatedState('<name>') })`. Never change the shared user.
- Each stage page has one spec that mocks none of its routes.
- Training needs a real dataset from `test-data/ai-test-datasets/`; the 6-row
  `sample.csv` cannot train.
- Break the behaviour a new spec covers once, and watch it fail, before trusting it.

`aiMock` serves canned AI responses when `USE_AI_MOCK=true` or `CI=true`.

## Re-recording the /how-it-works media

`npm run capture:how-it-works` (from `apps/frontend`, MongoDB and LocalStack up, `ffmpeg` on the
path) runs `e2e/capture/how-it-works.capture.ts` through `test-e2e.sh` with
`playwright.capture.config.ts`, which matches only `*.capture.ts`, so no normal run executes it.
It walks the real UI as the isolated `onboarding` user (a new account, not an admin) from the churn
sample to Deployment, writes one `public/how-it-works/<stage>.webp` per stage and the silent
`churn-walkthrough.webm` (Quick training mode, about a minute), and erases its dataset. The
signed-in account is named at the bottom of the sidebar, so every frame is cropped above it: look at
each image before committing, and keep any address out of them. The page is
`app/how-it-works/page.tsx`; its test checks that every image exists and stays small.

## When a spec fails

Read `error-context.md` and `trace.zip` under `test-results/` before retrying. A failure
that repeats across in-run retries is a real signal, not flake. `authenticatedPage` fails
with the URL it actually landed on. Check `/tmp/backend-e2e.log` for 4xx/5xx from the
backend.
