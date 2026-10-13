# Issue #790: DEPLOY_PATH is written inside quotes in the remote command string

## Plan
- [ ] `scripts/deploy/on_box.sh`: the one way a workflow runs something on the staging box.
      The value goes into the remote environment shell-quoted (`printf %q`), never between
      quotes in a string; the body travels on stdin, from a repo script or a QUOTED heredoc,
      and reads `"$DEPLOY_PATH"`. The remote side saves the body to a file and runs it with
      stdin at /dev/null, so no command in it can eat the rest of it (#756's failure, by
      construction).
- [ ] RED (pytest, with a fake `ssh` that parses the command string the way the far shell
      does): a `DEPLOY_PATH` holding a quote, a space and a command substitution arrives as
      one value and runs nothing; a body that reads stdin still runs to its end; the exit
      code comes back.
- [ ] All eight `ssh` call sites in `deploy.yml` and `staging-health.yml` go through it. A
      wiring test fails on a raw `ssh` or a `'$DEPLOY_PATH'` in either workflow.
- [ ] Verified on staging before merging by dispatching both workflows from the branch.
- [ ] A note in the deploy guide.

# Issue #778: the upload page has no jest suite that renders it

## Plan
- [x] A suite that renders `UploadPage`, selects a small CSV through `file-input` and clicks
      `upload-button`, with `fetch` answering as the backend does. Tests only: the page
      itself does not change.
- [x] `/upload/secure`: success (preview, file id, the stage completed, Next goes to
      `/explore/{id}`); a 402 `quota_exceeded` puts the error in the `planLimit` store and
      shows the backend's sentence; another failure shows its own detail or the fallback
      and opens no dialog; a 200 of an unknown shape is an error.
- [x] `/upload/confirm-pii-upload`: the warning, both choices (`mask_pii` true and false),
      then the same three outcomes.
- [x] Mutation check: each `apiError` line reverted to a plain `Error`; its tests must fail.
- [x] Mutation result: with `/upload/secure`'s `apiError` replaced by a plain `Error`, its
      plan-limit and backend-detail tests fail (2 of 11); the same for the PII confirmation.


# Issue #810: a URL assertion passes at push time, before the stage guard bounces

## Plan
- [x] `e2e/helpers/landing.ts::expectLandedOnStage(page, url, stage)`: the address, then the
      stage bar naming that stage as current (it follows the workflow state the guard
      reads), then, once the network is quiet, no guard banner and the same address.
- [x] The onboarding sample spec uses it after "Use This", and asserts the dataset preview.
- [x] RED by mutation: take out the #807 fix (the sample load completing Data Loading). The
      spec passed with it missing before; it must fail now.
- [x] Audit of every `waitForURL` / `toHaveURL` in `e2e/`: which are followed by work on the
      landed page (safe), which end on the address (fix), which sit in specs that cannot
      fail anyway (#921, #991).
- [x] Mutation result on the real stack: with the stage completion taken out of the sample
      loader, the spec as it is on main passes; the new one fails with
      `Received string: "http://localhost:3010/upload"`.
- [x] Audit: 31 address assertions in `e2e/`. Safe (followed by work on the landed page):
      the 12 in `stage-transitions` and `beta-journey` before their last step,
      `features-stage`, `predict`, and the upload fixture (it already waits for the dataset
      heading). Fixed: the onboarding sample spec and `stage-transitions`' last step
      (`/deploy`). Left, in specs that cannot fail for other reasons: `train.spec:54`,
      `evaluate.spec:255` (a `.catch`), `error-scenarios.spec:192`, both in
      `recipes/recipe-management.spec`, and `UploadPage.waitForUploadComplete` (#921, #991).


# Issue #756, second pass: the frontend probe printed nothing and passed

## Plan
- [x] Read the first real run (the deploy after PR 1007): the backend probe's lines, then
      nothing, step green. The deployed route itself answers healthy when asked directly.
- [x] Cause: the workflows feed the script to `bash -s` over ssh, and `docker compose exec`
      inside it reads the rest of the script from that stdin. Bash meets end of file and
      exits 0. The tests ran the script as a file with a `docker` that ignored stdin.
- [x] RED: the tests feed the script on stdin with a `docker` that drains it: `(0, '')`.
- [x] `</dev/null` on the exec. Both workflows fail the step when no verdict line was
      printed, and the deploy gate captures the exit code by redirect (no pipefail there).
- [x] Verified by dispatching `staging-health.yml` from this branch before merging: the run
      prints `frontend: {"status":"healthy",…}` after the backend probe, exit status 0.

# Issue #756: the staging probe does not cover the frontend container

## Plan
- [x] RED (jest): a readiness report for the frontend's two shared secrets.
      `mongo`: a NEW connection with this process's `MONGODB_URI` and a ping of `MONGODB_DB`
      (the adapter's own pool stays authenticated on a rotated credential, so only a fresh
      connection sees a stale value, the same reasoning as the backend probe).
      `api_token`: a token minted with this process's `NEXTAUTH_SECRET`, sent to the
      backend; 401 means the two halves disagree. Failures carry a class name or a fixed
      phrase, never a message (a Mongo error names the cluster).
- [x] `GET /api/health/ready` returns it, 200 or 503. The edge sends `/api/health*` to the
      backend, so the route answers only on the container's loopback port.
- [x] `scripts/deploy/frontend_probe.sh` asks it from inside the frontend container;
      `staging-health.yml` and `deploy.yml` run it after the backend probe, so a failure
      fails the same run and lands on the same alert issue. An image that predates the
      route answers 404: reported as skipped, not as a failure.
- [x] RED (pytest wiring): both workflows run the script; the script prints statuses only.
- [x] Runbook: the manual sign-in after a rotation becomes optional.
- [x] Checked on a production build (`next build`, `next start`) against the real backend:
      healthy; a secret the backend does not share is a 503 naming it; a stale Mongo
      credential is `MongoServerError AuthenticationFailed` while `/pricing` still answers 200.


# Issue #809: the onboarding sidebar is crushed at desktop widths

## Plan
- [x] RED: an e2e check on the real stack at 1024, 1280 and 1440px, as the isolated
      `onboarding` user with one achievement earned: no step title is cut off, and no badge
      or label in the progress card leaves its box or overlaps its neighbour.
- [x] The grid is keyed to the viewport (`lg:grid-cols-4`), while the page sits beside the
      256px app sidebar: at 1280 the progress column is about 120px. Key it to the container:
      stacked until the page itself is 48rem wide, then a fixed 16rem column. Titles wrap
      instead of truncating; when stacked, the steps sit two to a row.
- [x] `OnboardingProgress`: the points badge row and the two count labels wrap.
- [x] Neither file can take an edit as it is: the page reads as zero functions to the
      complexity gate (451 lines, one component), `OnboardingProgress` has cc 14. Split both;
      the page becomes a shell over `components/onboarding/`. Held by the page's 5 tests,
      `OnboardingProgress`'s 14, and the two real-stack onboarding smoke tests.
- [x] Measured on main: the progress card is 78px wide at 1024 (30 problems), 142px at 1280
      (13), 182px at 1440 (9). On the branch: 384, 640 and 256px, no problems at any width.
      The page is not the viewport minus one sidebar: the shell also reserves 320px on the
      right for the chat panel.
- [x] The step rows were clickable `div`s; they are buttons now, with `aria-current`.


# Issue #753: the tenant-isolation smoke spec covers column stats, batch jobs and B's own data

## Plan
- [x] Tenant B becomes an isolated e2e user (`tenant-b`, #743) instead of the admin: the
      admin tenant may not upload (its PRO plan has a two-upload ceiling that
      `plan-limit.spec` depends on), and the issue asks for a B-owned upload.
- [x] Column stats for A's upload: A 200, B 404.
- [x] A batch job from the model the spec already trains (3-row CSV, no extra training):
      B gets 404 on read, progress, download, cancel and delete; A's job is untouched.
- [x] `POST /batch/jobs/{id}/cancel` answers 400 "cannot be cancelled" for a job that is
      not the caller's or does not exist. RED: 404 for both, 400 kept for the caller's own
      finished job (the convention since #751).
- [x] B uploads its own dataset while A's exist: each tenant's list holds its own file only.
- [x] Found by the new column-statistics assertion: A's own read answered 500. pandas counts
      bool as numeric, so a true/false column went to the quartile code and numpy refused
      it. Any dataset with such a column failed. Bool is classified first now (backend test
      red first), and the type function is a table plus `_text_kind` for the gate.
- [x] Mutation check: with the cancel fix undone the spec fails on "B must not cancel A's
      batch job" (400 for 404).


# Issue #825: StatisticsDashboard fetched a route that does not exist

## Plan
- [x] RED: the suite's two tests of the fetch path (loading, error) go; in their place the
      component is shown to make no request, and `statistics` is required at the type level
      (`@ts-expect-error` on a render without it, which `tsc` fails while the prop is optional).
- [x] Remove `useAsyncData`, the fetch and the loading/error cards; `statistics` is required.
- [x] The complexity gate could not read the component (typed destructured parameter) and it
      holds four tabs of conditionals in one function. Take `props`, and split: tiles, the
      two overview cards, one card per numeric and per categorical column, the correlations
      tab. Behaviour held by the existing 14 tests.
- [x] The explore page passes `dataset.statistics` inside `<Present when=…>`; it needs the
      same cast its schema line has.
- [x] Found on the way: a column with over 10% missing and a zero outlier share showed
      "15.0% missing0" (`{0 && …}` renders the 0). The issue text is built as a string now.
- [x] The gate still read zero functions after the split. Bisected with lizard: an inline
      object type as a generic argument (`ComponentType<{ className?: string }>`) blinds its
      TypeScript reader for the whole file, and `a > 50 ? 'x' : 'y'` followed by `?.` leaves a
      function unclosed. Both written another way.
- [x] Real browser, real upload: the tab's text is identical on main and on the branch.


# Issue #743: specs that change account state get their own e2e user

## Plan
- [x] RED (jest): an isolated identity resolves only with `TEST_ISOLATED_USERS=1`, only for a
      plus-addressed form of `TEST_USER_EMAIL` with a safe slug and the test password, and
      its id cannot collide with the shared user's or the admin's. The provider's
      `authorize` is exercised through the mocked provider factory.
- [x] `lib/test-credentials.ts::resolveIsolatedTestUser` + `resolveExtraTestIdentity` (admin,
      then isolated); `auth.ts` calls the latter. Dev/test builds only, like the provider.
- [x] `e2e/isolatedUsers.ts` names the users (`onboarding`, `erasure`); global setup signs
      each in and saves its session; a spec opts in with `test.use({ storageState })`, so
      every fixture (`page`, `request`, `authenticatedPage`, `trainModel`) is that user.
- [x] `onboarding.spec` runs as `onboarding` and rejoins the main projects: the two
      `-onboarding` projects and their `dependencies` go.
- [x] `account-erasure.spec` gains the account-level erase, as `erasure` (AC2).
- [x] AC1 proof on the real stack: on main the spec's reset turns the shared user's
      finished onboarding back to first-time and its dashboard bounces; on the branch the
      reset lands on `test-isolated-onboarding` and the shared user stays where it was.
      The whole smoke project (40 tests) passes with the onboarding spec in parallel.
- [x] Fixture diagnostic stays (AC3), its comment says what can still cause a bounce.

# Issue #999: 72 e2e tests drove a legacy Prepare page no user can reach

## Plan
- [x] Baseline: run the five specs on the real stack as they are. 31 pass, 36 fail, 5 never
      run (a serial suite stops at its first failure).
- [x] `transform`, `data-versioning`, `transformation-config`, `complete-ai-workflow`: every
      test either fails (the page object clicks controls that exist nowhere: 19 of its 21
      selectors match nothing in the app) or passes inside a `try/catch` or an `if visible`.
      None can fail on a regression. Deleted, with the page objects only they used.
- [x] `data-preparation`: the one spec with real assertions, on the legacy page's own header.
      Rewritten against `/prepare` (the stage a user gets): default view, a step shared by
      both views, the chain view's accessible names, both views on a phone and a tablet.
      Dropped: assertions that cannot fail (`|| true`, `>= 0`, either-or) and the legacy
      header, Back link and error card.
- [x] The legacy page's UI is deleted with the `showViewToggle` prop only it passed. Its address
      stays as a redirect to `/prepare?datasetId=…`: the legacy engineer page (#738, owner's
      call) still links there, and editing that page's links means splitting a 240-line
      untested component for the CRAP gate (review finding).
- [x] Mutation check: default the pipeline to Visual, three of the new tests fail.
- [x] Lint ceiling 228 -> 190 (the deleted specs carried 34 warnings).

# Issue #620: the MCP server and its backend client move to the mcp 2.x SDK

## Plan
- [x] Server (`apps/mcp`): `FastMCP` is `MCPServer` in 2.x (`mcp.server.mcpserver`); `sse_app()`
      and `tool()` keep their shape. Pin `mcp>=2,<3`, full `uv lock --upgrade` (no yanked pin).
- [x] Client (`apps/backend`): the two apps speak SSE to each other, so they move together
      (Dependabot PR 758 widened the range without a relock; this replaces it). 2.x renames
      the result fields to `is_error` / `structured_content`; the client read the 1.x names
      through `getattr` with a default, so on 2.x a failed tool call would have been returned
      as a result. RED: unit tests on the SDK's own `CallToolResult`, and a real failed tool
      call over SSE in the round-trip test.
- [x] Relocking the backend for mcp 2.x also moves pydantic 2.11.5 -> 2.13.5 on Python 3.13
      (mcp 2.x needs the newer one; the lock had forked by Python version). Full gate + mypy.
- [x] Live SSE smoke recorded (`curl -N` with the bearer -> `event: endpoint`), docs.

# Issue #712: charts read the whole dataset to use one or two columns

## Plan
- [x] RED: each chart reads its own columns from a Parquet-backed dataset (the reads are
      watched, not replaced); a CSV is parsed with the others skipped.
- [x] `s3_service.read_columns_from_bytes(content, columns)`: Parquet by column, CSV with a
      callable `usecols` (a name the file lacks is left out, never an error), anything else
      read whole and narrowed.
- [x] Histogram and box plot read their one column; the correlation matrix still reads all.
- [x] Scatter, line and time series: the column set is the chart's columns plus the ones the
      parsed filter list names. The three handlers were at cc 9, 13 and 7 and repeated one
      flow, which is now `_chart`; each keeps its own payload builder.
- [x] Found on the way: a line chart's numeric x was sent as text (pandas hands plain ints,
      the numpy checks never matched). Numbers stay numbers.
