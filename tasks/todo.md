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
