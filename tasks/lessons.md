# Lessons

## 2026-06-08 — issue #75 (core AutoML pipeline)

- **Trust the code, not the issue's "Current State".** The ticket (and its
  Traycer plan) described `POST /ml/train` as a stub and the engine as missing;
  in reality the engine, problem detector, feature engineer, algorithm selector,
  explanation service, S3/Mongo storage, and real background training already
  existed. Always Explore the actual files before scoping — the beta-roadmap
  tickets' "verified" state notes drift quickly. Scope to the *unmet* acceptance
  criteria, and post a correction comment on the issue.
- **Auto-generated plans (Traycer/CodeRabbit) over-scope.** The plan said to
  "create" files that already existed and pulled in WebSocket/ARIMA/SMOTE/modes
  the issue itself defers to other tickets. Drive from the acceptance criteria,
  not the plan's file list.
- **`showboat exec` execs directly — no shell.** Shell builtins (`echo`),
  pipes, redirects, and env-var prefixes all fail. Wrap in `bash -c '...'`, or
  pass a real binary (`cat <file>`). It was also flaky/slow under `uvx` here;
  the demo *driver script* + a captured evidence file is the reliable fallback
  when the markdown-packaging tool hangs.
- **pytest-cov + narrow multi-`--cov=<module>` selection can spuriously fail**
  unrelated tests in the same run. Use a single broad `--cov=app` to generate
  coverage.xml for diff-cover; the failures vanished without coverage.

## 2026-06-06 — issue #160 (backend test-suite repair)

- **`str()` is not an enum-to-value guard.** For `class X(str, Enum)`,
  `str(member)` returns `'X.MEMBER'`, not the value. Use
  `getattr(v, "value", v)` (or `.value` directly). Caught by a PR reviewer
  after I shipped `str()` as a "guard" — verify enum coercions empirically,
  don't assume.
- **"Service-free" claims must be verified with the service actually absent.**
  I verified a fixture was IO-free by pointing config env vars at a
  nonexistent host — but the fixture hardcoded `localhost:27017`, and local
  MongoDB masked the IO. CI (no Mongo) exposed it. When proving something
  needs no service, make the service unreachable on the exact code path
  (or run in an environment without it), not just via config knobs.
- **Beanie `init_beanie()` always performs IO** (`buildInfo` command), even
  with `skip_indexes=True`. For service-free Document binding in unit tests,
  use `mongomock-motor`.
- **`load_dotenv(override=True)` at import time clobbers pre-set env vars.**
  Test env overrides must be applied AFTER importing the module that calls
  it (app/main.py), not before.

## 2026-06-06 (issue #166)
- **Mutation-check scripts must NOT restore files with `git checkout --`** when the working tree has uncommitted fixes — it silently reverts them to HEAD (lost the HistogramChart auth-token fix mid-gate). Restore via `cp` backups, or commit before mutating.
- **Verify sed mutation patterns actually matched** before trusting a "survived" result — a non-matching pattern is a no-op mutation and a false survivor (model.ts `/models/predict` vs actual `/ml/${id}/predict`).
- Coverage-driven tests written "to hit lines" tend to assert only "didn't throw" — pair every diff-coverage push with a mutation pass on the new tests (caught the StatisticsDashboard placeholder test).

## 2026-06-08 (issue #150 — CI pipeline)
- **After `ruff check --fix --unsafe-fixes`, review EVERY changed file, not just `app/` source.** F841 unsafe-fix rewrites `x = pure_expr()` → `pure_expr()`, leaving a dead no-op statement. I cleaned these in `app/` but skipped the ~20 touched test files; a reviewer then caught a bare `datetime.utcnow()` in a test (and a sweep found a sibling `transform_data.get(...)`). Tests don't fail on a no-op, so the suite stays green and hides it — grep the whole diff for added bare-expression lines. Side-effecting calls (`await foo()`, migrations) are correctly preserved; only pure expressions are dead.
- **A newly-populated workflow file won't run if its placeholder was `disabled_manually`.** Empty `ci.yml`/`deploy.yml` had been disabled in the repo; populating them wasn't enough — `gh workflow enable` + a fresh trigger (close/reopen PR) was required before CI ran.
- **LocalStack is unreliable on GitHub runners** — across runs it either failed the Docker Hub image pull (auth-token timeout) or never reached `healthy` in 120s. Don't make it a hard gate: use GitHub `services:` containers for the must-haves (Mongo, Redis) and start LocalStack best-effort (`|| warning`) so S3 tests skip rather than fail the pipeline.
- **`-m integration` silently deselects unmarked tests in `tests/integration/`** (upload/workflow/OpenAI) — codex flagged that the "integration gate" then covers far less than it appears. Document the scope boundary in the workflow.

## 2026-06-07 (issue #165 — xlsx → exceljs)
- **Frontend CI runs Node 18** (`.github/workflows/unit-tests.yml`), but local dev is Node 24. The global `File` constructor only exists from Node 20+, so a `new File([buf], name, {type})` test helper passed locally and failed CI with `ReferenceError: File is not defined`. Build upload fixtures as `Blob` and append with a filename — `formData.append('file', blob, name)` — which undici turns into a proper File entry (`.name`/`.arrayBuffer()`) on Node 18 and 24. Verify Node-18-specific code by actually running under `nvm use 18`.
- **`Buffer.from(arrayBuffer)` fails `tsc` with this repo's `@types/node`** (`Buffer<ArrayBuffer>` not assignable to the exceljs-declared `Buffer`, TS2345). Two separate reviewers suggested it; it's generically valid but wrong here. Cast to `Parameters<typeof fn>[0]` instead. Re-verify "obvious" type suggestions against the actual toolchain before accepting.
- **Reviewer rounds can contradict each other.** codex R2 (don't let stray cells add phantom columns → key off header) directly conflicted with R3 (don't drop data columns with blank headers). They're structurally identical inputs; no rule satisfies both. Resolved by using the sheet used-range (`worksheet.dimensions`), matching the prior `sheet_to_json({header:1})` `!ref` and prioritizing no-data-loss over a cosmetic phantom column. Don't mechanically apply each review round — reconcile against the real contract and rebut with proof.
- **`worksheet.eachRow` callback `return` does not stop iteration** in ExcelJS — it only skips that row's work. True early-termination needs `getRow(i)` or the streaming reader.

## Issue #185 (2026-06-10): overflow-x-auto is not enough — check min-width:auto up the flex chain
`overflow-x-auto` + `min-w-0` on a flex item only zeroes its minimum *inside its own flex row*.
The element's intrinsic min-content still propagates to ancestor flex items (here `<main>` in
`display:flex` body), whose default `min-width:auto` then forces whole-page horizontal scroll.
Jest/jsdom cannot catch this (no layout) — the browser demo gate did. When fixing overflow,
verify every flex ancestor has `min-w-0` (or measure `scrollWidth` in a real browser at the
target viewports before claiming the criterion is met).

## Issue #188 (2026-06-11)
- `gh api -X DELETE` is deny-listed in user settings: plan approval does not cover destructive GitHub API calls — ask explicitly, then use the authorized equivalent.
- `codex review` CLI: `--base <branch>` cannot be combined with a positional prompt; use `codex review --base main --title "..."` alone.
- `pull_request`-triggered workflows execute from the PR merge ref, so a PR that hardens a workflow live-tests its own changes — use those runs as demo outcome evidence.

## Issue #79 (2026-06-12)
- Parallel worktree agents that npm-install new deps leave the main tree's node_modules stale — run `npm install` on the integration branch after merging package.json before judging "failures".
- Demoing against the live stack surfaces pre-existing integration bugs the test suites can't (UserData.file_type never set; /evaluate/{datasetId} 404; e2e fixture drift → #191) — budget demo time for bug-fixing.
- Local backend demo in WSL: .env's Atlas mongodb+srv URI fails SRV DNS — override MONGODB_URI=mongodb://localhost:27017 on the command line.

## Issue #191 (2026-06-12): verify bot-plan root causes against failure artifacts
CodeRabbit's coding plan asserted a "workflow-state race" root cause for the e2e upload fixture failures; the actual Playwright failure artifacts (test-results/*/error-context.md) showed the upload POST never resolving — missing S3 storage, an environment problem. Lesson: before adapting an AI-generated plan, pull the cheapest primary evidence (stale test artifacts, logs) and let it veto the plan's diagnosis. Hardening the fixture alone would have masked the real bug.

## Issue #155 (2026-06-13): a stale bug — the fix already landed; the real work was the tests
The issue (and its CodeRabbit plan) blamed a `TransformationConfigDialog` props-contract crash. Live browser reproduction against current `main` showed the prepare page already renders fine — #166's TS-error cleanup had fixed the props, and that dialog never even mounts on initial load (`editingIndex` is null). Lesson: reproduce first. A bug filed weeks ago may already be dead; verify before writing a fix for a crash you can't reproduce.
The actual work was repairing the e2e spec, where re-enabling the `fixme`'d tests exposed: (1) a **#87 regression** — the backend became the workflow hydration source-of-truth, so `addInitScript` localStorage-only seeds no longer grant stage access; seed the real backend workflow (`PUT/POST /workflows/{id}` with `Bearer dev-user-default` under SKIP_AUTH). (2) **Broad locators masked by the crash** — assertions like `toContain('default')` (shadcn active variant is `bg-primary`, no literal "default"), bare `text=/rows/` (sidebar copy collides), and `a:has-text("Back")` matching a link-wrapped button. When a long-disabled test is re-enabled, expect its never-run assertions to be stale too.
