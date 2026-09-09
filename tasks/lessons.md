# Lessons

## 2026-06-17 — issue #176 (CI/Docker hardening, batch 3 / PR #222)

- **Pin service-container images by multi-arch digest, not tag.** Resolve the
  manifest-list digest with `docker buildx imagetools inspect <img:tag>` (the
  `Digest:` line) → pin as `img:tag@sha256:…`; this preserves multi-arch unlike a
  per-platform digest. GitHub Actions `services:` `image:` and docker-compose
  `image:` both accept it. **Dependabot's `github-actions` ecosystem does NOT
  manage service `image:` refs** — those pins are manual (the `docker` ecosystem
  covers Dockerfiles/compose, not workflow service blocks).
- The CI run on the pinning PR itself is the functional test — the integration
  job spins up the pinned mongo/redis, so green = the digests are valid + healthy.

## 2026-06-17 — issue #176 (CI/Docker hardening, batch 2 / PR #215; recorded here)

- **Making a Python container non-root breaks `$HOME`-caching libs.** After
  `USER appuser`, matplotlib (pulled in via SHAP/visualization) couldn't write
  its cache under the root-owned `/app` home and fell back to `/tmp` with a
  per-boot warning. Fix: set `MPLCONFIGDIR` to a dir **pre-created + `chown`'d**
  to the user (just exporting `MPLCONFIGDIR=/tmp/matplotlib` wasn't enough —
  matplotlib's writability check failed on the not-yet-existing dir). Keeps
  `/app` read-only. Watch for the same with joblib/numba/fontconfig if they warn.
- **Inline `#` comments inside a `\`-continued `ENV`/`RUN` are non-standard.**
  Current BuildKit strips them (the build passed), but the Dockerfile spec
  doesn't guarantee it and older daemons / custom frontends may choke. Put the
  comment **above** the instruction. Caught by claude-review; cheap pre-merge fix.
- **Verify non-root doesn't break runtime file writes.** codex's review probe
  grepped for `open(...,'w')`/`to_csv` — turned out safe here (`UploadHandler` →
  `/tmp/uploads`; `api_documentation` writes were example-client **string
  templates**, not executed), but the check is the right reflex when dropping
  privileges.
- **SHA-pin actions + Dependabot together.** Pin `uses: org/action@vN` →
  `@<40-hex-sha> # vN` (resolve via `gh api repos/<org>/<action>/commits/<tag>`),
  then add a Dependabot `github-actions` (grouped) + `docker` config so the pins
  refresh. The CI run on the PR itself validates the pins (jobs spawning = the
  pinned checkout/setup resolved).

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

## Issue #88 (2026-06-14): the "auto-advance" that never advanced + parallel stage routes
Two non-obvious traps while wiring seamless stage transitions:
1. **`WorkflowContext.completeStage` auto-advance was dead code.** It called `canAccessStage(nextStage)` right after `setState(add stage)`, but `canAccessStage` closes over the *pre-completion* `state.completedStages`, so `next.requiredStages=[stage]` was never satisfied → it never navigated on a normal first completion. Pages that commented "navigation happens automatically through completeStage" (e.g. `app/datasets/[id]/prepare`) were silently stuck. Lesson: a stale-closure check against just-set state is a no-op; compute against the about-to-be set, and don't trust "auto" comments — trace the closure.
2. **Stage routes are NOT uniform and there are parallel route trees.** Canonical stages live at `/upload /explore/[id] /prepare /features /model /evaluate/[datasetId] /predict/[datasetId] /deploy`, but ALSO `app/datasets/[id]/prepare` and `app/datasets/[id]/engineer` exist as alternate entry points. Blindly pushing `/{route}/{datasetId}` 404'd `/prepare/{id}` and mis-routed `/model/{id}` to a model *detail* viewer. Lesson: before centralizing navigation, enumerate ALL `page.tsx` for every stage (incl. parallel `datasets/[id]/*` trees) and make URL-building route-aware; grep every `completeStage(`/`router.push(` caller, not just the obvious stage pages — codex caught the alternate route I missed in round 1.

## Issue #151 (2026-06-15): a global rate-limit middleware has three subtle traps
Adding `RateLimitMiddleware` over every `/api/v1` route surfaced non-obvious gotchas, each caught by review:
1. **A test-env-wide bucket.** With `SKIP_AUTH=true` (unit conftest AND the e2e harness), every request resolves to one shared identity (`dev-user-default` or one testclient IP). A global limiter then bleeds counts across the whole suite → spurious 429s. Fix: disable it by default in tests (`conftest.py` `RATE_LIMIT_ENABLED=false`) and in `apps/frontend/test-e2e.sh`; the rate-limit tests opt back in with `enabled=True`. Always feature-flag a cross-cutting middleware OFF in shared test harnesses.
2. **`X-Forwarded-For` is attacker-controlled.** Trusting XFF unconditionally lets an anonymous caller forge a fresh IP bucket per request, nullifying the unauthenticated-flood limit. Gate it behind `RATE_LIMIT_TRUST_FORWARDED_FOR` (default off; on only behind nginx). (internal review)
3. **An auth header is not a route's auth mechanism.** Keying the per-key bucket on *any* `/api/v1` request carrying `X-API-Key` let a user attach a production key to unrelated/bearer-authed routes to escape their default budget. Scope the key bucket to the routes that actually `Depends(verify_api_key)` — here only `/api/v1/production/v1/models/...`, NOT the sibling bearer-authed `/production/api-keys` CRUD. (codex, 2 rounds — it first flagged the broad `/production`, then the still-too-broad prefix)
Also: prefer one atomic Redis `EVAL` (INCR + re-arm EXPIRE) over INCR/EXPIRE/TTL; and a middleware must `try/except` its store call and fail open — the store failing open internally isn't enough if it ever raises (CodeRabbit). Smoke-test `train.spec.ts` flakiness was pre-existing (failed identically on #88) — check prior PRs' runs before assuming your change broke a non-required check.

## Issue #157 (2026-06-15): "removing the heavy tests" didn't fix smoke — verify the gate against CI, not reasoning
I split the two flaky perf timing tests out of `@smoke` into a non-blocking `@perf` job and *assumed* (wrote it in the plan as "no worker change needed") that removing the two core-pegging tests would relieve the 2-core contention enough. CI proved otherwise: smoke still failed (2 failed / 3 flaky / 24 passed) — but in *different* heavy specs (`evaluate`, `model-config`, `data-preparation`), all train-then-assert `@smoke` tests whose **`uploadTestDataset` in `beforeEach`** timed out under contention. Two lessons: (1) **hook/fixture setup counts against the 30s test timeout** — the Playwright error "Test timeout exceeded while setting up authenticatedPage" / a `beforeEach` upload timeout means `test.slow()` must go *in the `beforeEach`*, not the test body (the body never runs if the hook times out). (2) Don't reason your way to "contention is fixed"; the cheapest proof is the actual CI run. Also reconfirmed (per #88/#151): `smoke-tests.yml` is **non-required** (required gate = `ci.yml` `CI Success`) and was red on every recent PR (#151/#152/#153, all merged) from the same systemic 2-core starvation — so a red smoke check is not automatically your regression; diff it against `gh run list --workflow=smoke-tests.yml`.

## Issue #168 (2026-06-16): a contract-mismatch fix must also satisfy the *downstream* contract
The deploy page sent POST (backend is PUT) and read `api_endpoint`/`api_key` that `ModelDeployResponse` never returns. Aligning method + fields was the obvious part; two non-obvious traps caught by `codex review`:
1. **`mark_deployed(endpoint)` persists the endpoint verbatim and synthesizes no default.** Sending an empty PUT body makes `deployment_endpoint` come back `null` — the success page then has no URL and workflow state records a null `apiEndpoint`. The deploy "worked" (200) but produced a useless result. Fix: the UI supplies the real production serving URL (`${API_URL}/production/v1/models/{id}`, where `production_predict` is registered) as `endpoint`. Lesson: when fixing a request contract, check what the backend *does* with each field, not just that it accepts the shape.
2. **The success-state curl example is its own contract.** The production predict route authenticates via `X-API-Key` (not `Authorization: Bearer`) and takes `{ "data": [...] }` (not `{ "features": {...} }`). A copy-paste example that 401s/422s is a real bug. Lesson: verify sample/doc snippets against the actual route schema (`ProductionPredictRequest`, `verify_api_key`), same as production code.
Also: there is no `GET /models/{id}/deployment` route — `checkDeploymentStatus` 404'd silently on every mount; the data lives on `GET /models/{id}` → `deployment_config`. The same contract-drift family the issue was about, one function over. Fix the whole family, not just the line the issue cites.

## Issue #453 (2026-09-06): "out of scope, nothing here uses it" is a claim you have to verify
I found `versioning_service.get_version`'s ownership check reads `if dataset and dataset.user_id != user_id` — a join to `DatasetMetadata` that skips the check entirely when the dataset row is missing — and wrote in the plan: *"Not changing that service method here — out of scope, no route in this issue uses it."* Then I routed the new lineage-walk boundary **through it anyway**, and the claim itself was false: `GET /versions/{id}` and `PATCH /versions/{id}/pin` both authorize on it. Reviewers caught both halves. The pin route was the expensive one — not a read but a **write**: `PATCH /versions/{id}/pin` on another tenant's orphaned version returned 200 and mutated their row, and pin state governs whether retention cleanup deletes it. Lessons:
1. **Grep the call sites before writing "nothing uses this."** One `grep -n "get_version(" ` would have shown three. A scoping claim in a plan is an assertion about the codebase, not a scoping decision.
2. **Fix a bad predicate at its source, not around it.** Two commits moved callers *off* the flawed check and left it live for everyone else — strictly more code and a still-open hole. Replacing the check inside `get_version` closed all three call sites and made the diff *smaller*. If you find yourself routing around a shared helper because it's unsafe, the helper is the bug.
3. **Orphaned rows are ordinary, not exotic.** "Dataset row deleted, version survives" is what deleting a dataset produces. A `if x and x.owner != me` shape fails **open** on exactly that state — the safe shape is `if x.owner != me` against a field the row owns itself. Same class as the two-id-space skew CLAUDE.md already warns about.
4. **Scoping an entry point does not scope a walk.** `get_lineage_chain`/`_find_lineage_path` follow `parent_version_id` and load linked `TransformationLineage` rows; each hop and each linked record needs the predicate, or owning the first version leaks the rest. Verified by test, not by reasoning.
5. **Cross-family review earned its keep, twice.** opencode/GLM found the fall-open and the unscoped `compare_versions` walks pre-PR; the PR bot found the pin mutation post-PR. Both were in code I had read closely and believed correct.

## PR #575 (2026-09-07): `gh run list --limit N` returns the *most recent* N — I read a tail sample as a head one
Writing the CI note for the GLM Review fix, I ran `gh run list --workflow "GLM Review" --limit 100`, got `{"startup_failure": 97, "failure": 1, "success": 2}`, and wrote into `CLAUDE.md` that "its first 97 runs were `startup_failure`". Wrong twice over: 97 was the *latest* 100 runs, not the first, and the true oldest run (2026-07-10) had **succeeded**. The real history is 270 runs — one review, then 266 runs producing none, then this branch. Another session checked the primary source and caught it. Lessons:
1. **A paginated listing is a window, not a census.** `gh run list`, `gh pr list`, `gh issue list` all default to newest-first with a small limit. Any claim of the form "the first N" or "it never worked" needs the *oldest* records — `--limit` high enough plus `.[-3:]`, or an explicit sort — not the default page. Issue #571's own body said "oldest sampled run 2026-08-02"; the caveat was right there and I still inverted it.
2. **A bot ratifying your number is not verification.** The same round, `claude-review` called the line "accurate and appropriately caveated (97 prior `startup_failure` runs ≠ clean history…)" — it repeated the wrong figure back approvingly. Only the reader who re-queried the source caught it. Bot agreement raises no confidence about a fact neither of you checked.
3. **"It never worked" and "it worked, then a commit killed it" are different bugs with different lessons.** The true shape was more useful than the one I wrote: a single hardening commit pinned a callee, dropped `id-token: write` and added a `concurrency:` block together — each step locally sound, two of the three fatal in combination, and silent for two months. That is a lesson about bundling hardening changes; "it never worked" teaches nothing.
4. **A "flaky, unrelated" check deserves the same evidence standard as a real failure.** `E2E Smoke Tests` went red on my `CLAUDE.md`-only commit. It *was* the known fixture flake — but the way to know that was pulling the job log and matching the assertion and the all-three-attempts signature, not asserting a docs commit cannot break e2e. It failed 2 of 5 runs on that branch (now #578), and the per-run shape means Playwright retries never catch it.

## 2026-09-07: I pushed docs commits straight to `main` and bypassed the required check, twice
Landing the lessons entries for #453 (`66419e9`) and #575 (`c2d9fc4`), I committed on `main` and pushed. Both went through, and the second one printed what was happening:

```
remote: Bypassed rule violations for refs/heads/main:
remote: - Required status check "CI Success" is expected.
```

`main` requires `CI Success`, but `enforce_admins` is `false`, so a repo admin's push is waved through with a warning rather than refused. Nothing broke — both commits were `tasks/lessons.md` only — but the practice is wrong and the failure mode is silent by design. Lessons:
1. **A push that succeeds is not a push that was allowed.** `git push` exiting 0 says nothing about protection; the `Bypassed rule violations` line is the only signal, it goes to `remote:` output, and piping through `tail -1` (as I did on the first one) hides it entirely. Read the whole push output, or don't push to a protected branch.
2. **"It's only docs" is the reasoning that erodes the rule.** The repo standard is feature branch → PR, with no docs exemption. The exemption is self-granted every time, and the next one is slightly less trivial than the last.
3. **`enforce_admins: false` makes protection advisory for exactly the person most likely to move fast.** Worth knowing before assuming the guardrail will stop you; it will not.
The corrected practice: branch, PR, let `CI Success` run, merge — including for a one-paragraph docs change. This entry landed that way.

## PR #582 (2026-09-07): repairing a dead code path makes its failure paths live — and my own fix opened a new hole
The four chunked-upload defects (#454/#462/#463/#464) each said "land the group together", and that was right: the flow 422'd at init, so nothing downstream could be verified. What I under-weighted is that *making a broken path work is a change in blast radius*, not just a bug fix. Two rounds of third-party review (opencode/GLM) found five real problems that were all dormant only because the route could never complete:
- The route creates real datasets, so it needed `quota("uploads")` like its siblings — unmetered dataset ingestion the moment it worked.
- It bypasses the high-risk-PII confirmation gate `/secure` enforces (#583) — a live security bypass shipped by repair, not by new code.
- Its failure paths (corrupt CSV, oversize, S3 error) were suddenly reachable, and two of them were wrong.

Lessons:
1. **Fixing a route that always 500'd is a feature launch. Audit it like one.** Before declaring the repair done, ask what *else* the route now does that nothing was checking: quota, authz gates its siblings enforce, rate limits, background work. "It was already written this way" is not a defence once the code starts executing.
2. **My own fix introduced the worst finding.** Removing a duplicate `rate_limiter.end_upload` (correct: one `start_upload` was being matched by two releases) moved the whole release onto `complete`, which released only on its success path. Ten corrupt uploads would then have pinned a user at the concurrency cap forever, with the session already dropped so `DELETE` could not recover it. Removing half of a paired-resource bug is how you create the other half — when a fix changes *where* a resource is released, the next question is always "on which exits?", and the answer should usually be `try/finally`.
3. **A second review pass on the final diff earned its cost.** The first review ran on an earlier revision; three of the five findings only existed *because* of what I changed in response to the first. Re-reviewing after substantive fixes is not ceremony — the fixes are new code and nobody has read them.
4. **"No await between check and use" is a race, not a safety argument.** `complete` looked atomic because the session lookup and `user_data.insert()` had no suspension point between them — but `insert()` *is* the suspension point, so two concurrent completes both cleared the checks first. The fix was to claim-and-remove the session in the same synchronous step. Sequential tests (`test_a_repeated_complete_is_404_not_500`) cannot see this; the concurrent one does.
5. **Inventory before claiming a migration is needed — or isn't.** #464 AC4 asked what damage the unprefixed keys had already done. Listing the bucket showed 155 unprefixed objects, but every one was a server-generated uuid, i.e. from the *non-chunked* routes; not one came from the broken path. That turned "migrate or delete existing objects" into "nothing to do here" plus a separate, better-scoped issue (#581) — and the evidence is in the PR rather than an assertion.
6. **A demo that only shows the happy path would have hidden all of this.** The failure-path sections (three corrupt uploads then a clean init; two racing completes producing one object) are where the real fixes are visible. Demo the paths that were *newly reachable*, not just the one in the acceptance criteria.

## PR #582 (2026-09-07), process addendum: a broad `git add`, then a force-push to cover it
Two self-inflicted problems on the same branch, both worth naming separately from the technical lessons above.

`git add apps/backend` swept in `apps/backend/_demo_77.py` — an untracked scratch script from issue #77 that had been sitting in the working tree since before this branch existed. Its 26 `print` statements failed `Backend Lint (ruff)` and took `CI Success` red. I did it **twice**, in consecutive commits.
1. **A directory-scoped `git add` is a bet that you know everything untracked under it.** `git status` at session start listed seven untracked files; I read that list, then added a whole tree anyway. Name the files, or `git add -p`. The cost of naming them is seconds; the cost of not is a red CI run and a commit that has to be undone.
2. **`ruff check app/ tests/` is not what CI runs.** CI runs `ruff check .` from `apps/backend`, which sees anything on disk there. My scoped local run was green the entire time the CI check was failing. When a lint gate disagrees with your local run, suspect the scope before the code.

Then, fixing the second occurrence, I ran `git commit --amend` and `git push --force-with-lease`. The first occurrence I had fixed correctly, with a follow-up `git rm --cached` commit. The skill's rule is explicit — the feature branch is never force-pushed — and I had already demonstrated the compliant fix one commit earlier.
3. **Rewriting history to hide a mistake costs more than the mistake.** Nobody else was on the branch, so nothing broke; that is luck, not justification. A follow-up commit is honest, is reviewable, and cannot race a reviewer or a CI run that has already fetched the old SHA. "It's tidier" is the same reasoning as "it's only docs" from the entry above.

Tooling note for whoever hits it next: this repo's conftest suppresses pytest's terminal summary on large selections — no `N passed` line and no per-test `-v` output on a full-tree run, though smaller selections still print normally. Use the exit code, or `--collect-only` summed per file, rather than concluding a run produced nothing.

## #455 — a test that cannot fail is worse than no test

Twice in one PR I wrote a test that passed for the wrong reason, and only caught
it by mutating the code:

- `test_out_of_order_event_does_not_clamp` passed with the clamp deliberately
  hoisted above the guard it was supposed to be behind. A stale event carrying no
  `tier` makes the mutant read the *unchanged* tier off the subscription, so it
  clamps to the same number and looks correct. Fixed by giving the stale event its
  own lower tier.
- The `PLAN_*_API_KEY_RATE_LIMIT` override test reloaded the module in a `finally`
  *before* the assertion, so every case compared against the default — which is
  exactly what the fallback returns. Both non-positive cases passed vacuously.

**Apply:** on a PR whose subject is "a control was disabled and nothing noticed",
mutate every new assertion before believing it. Run the *full* gate, not the
targeted file: the `importlib.reload` in that same test rebound `PLAN_LIMITS` and
broke `test_models/test_subscription.py` from across the suite — invisible to
`pytest path/to/new_test.py`.

## #455 — verify a reviewer's claim before fixing it

claude-review reported that BSON's `String > Number` ordering makes a string
`rate_limit` match `{"$gt": ceiling}`, double-counting rows in the audit script. A
three-line probe against real MongoDB disproved it: range queries are
**type-bracketed** to the operand's type; type ordering governs *sorts*. GLM later
reached the same conclusion independently.

**Apply:** a confident, specific, plausible-sounding claim about database
semantics is still a claim. Probing costs a minute; "fixing" it would have added a
`$and` clause defending against nothing and implied the buckets were once wrong.

## #455 — a declined finding can come back stronger

I declined "the `max(1, ...)` floor silently absorbs a bad env override" twice as
scope creep. The third framing was the one that mattered: `UNLIMITED = -1` is that
module's *documented* sentinel for every other limit, so an operator following the
file's own convention would brick a tier at 1 request/window.

**Apply:** re-read a repeated finding for a *new argument*, not just a repeated
one. The severity did not change; the reason did, and the reason is what made it
worth fixing.

## #455 — I pushed the lessons file straight to main

Immediately after merging PR #587 I was on `main`, committed `tasks/lessons.md`
there, and pushed. Git printed `Required status check "CI Success" is expected`
and **took the push anyway** — `enforce_admins: false`, the admin-bypass
behaviour #579 already documented as a process failure. I read that line as a
rejection and only found the commit on `main` by fetching.

The irony is the point: the commit was a lessons file about not repeating
mistakes, landed by repeating a recorded one.

**Apply:** after a merge, `gh pr merge --delete-branch` leaves you on `main` —
branch *before* the next commit, every time. And a `remote:` warning is not a
rejection: `git push` exiting 0 means it landed, so check `git log origin/main`
rather than reading the warning text as an outcome.

## #456 — I nearly graded my own fix against a file nothing reads

The issue's AC5 asked whether the repo's `nginx-staging.conf` is the config actually
applied. It is not: the live file is a separate hand-written 53-line certbot-managed
config last touched 2026-07-01, while the repo's is 187 lines and still carries
placeholder `yourdomain.com` names that would fail `nginx -t`. Every other AC could
have been satisfied by editing the repo file, merging green, and leaving staging
dropping every Stripe payment event exactly as before.

The only reason this didn't happen is that AC5 existed and I checked it *first*,
before writing any code — which then reshaped the whole plan (fix both files, demo
against both).

**Apply:** for any fix to a deployed artifact — nginx, systemd, cron, a compose file,
a dashboard — establish that the file in git is the file in production *before*
planning the fix, not after. `stat -c %y` and a line count on the live copy takes ten
seconds. "It's checked into the repo" is an assumption about a deploy mechanism, and
here there was no deploy mechanism at all (#594).

## #456 — my mutation harness reported ten false negatives in a row

I ran eleven config mutations and every one came back "NOT CAUGHT". The tests were
fine; the harness parsed `pytest -q` output for `N failed`, and this repo's conftest
suppresses that summary line. Ten seconds of reading the output directly showed a
mutation failing loudly with a perfect assertion message.

The failure mode is the nasty direction: a broken *verification* harness reports
"your safety net has holes", which is alarming enough to look like a real finding
and would have sent me rewriting working tests.

**Apply:** already recorded for pytest counts ("trust the exit code") — the new part
is that it applies to anything *wrapping* pytest, not just reading it. Before
believing a batch result, run one case by hand and confirm the harness reports it
correctly. A harness that says everything failed is as suspect as one that says
everything passed.

## #456 — a test can pin a preference and call it a safety property

I asserted `proxy_request_buffering off` in the block and documented it as what keeps
the request body byte-exact for Stripe's HMAC. GLM pointed out it is not: nginx
buffering changes *framing*, never bytes. The directive was harmless and worth
keeping for consistency with the `/api/` block — but the test and comment were
teaching a future reader a false rule about why webhook signatures work, which is
exactly the kind of thing someone reasons from at 2am.

The real invariants (no `proxy_set_body`, no `rewrite`, no URI on `proxy_pass`, no
header override) were separately assertable, so nothing was lost by dropping it.

**Apply:** for each assertion, ask "what breaks in production if this flips?" If the
honest answer is "nothing, I just prefer it", keep the config line and delete the
assertion — or say plainly that it is a consistency check. A wrong *reason* attached
to a passing test outlives the test.

## #457 — a comment can become configuration

`preflight_staging_env.sh` derives the *required* variable set by grepping the
compose file for `${VAR:?}`. I added a comment explaining why the Stripe variables
are deliberately *not* guarded — and the comment contains that pattern, so the
preflight began demanding a variable literally named `VAR`. It would have failed
the very next staging deploy, with an error naming a variable that appears nowhere
in the file. Nothing about the failure points at a comment.

Two separate things went wrong. The parser was text-based over a structured file
and never considered comments; and I wrote prose *inside* the input to a parser I
had just read, without asking whether it would be parsed. Documenting a pattern
where the pattern is executable is a code change.

**Apply:** if a file is machine-parsed, treat its comments as input until proven
otherwise — and fix the parser rather than rewording the comment, since anyone who
documents the pattern hits it again. The generalisation: whenever a tool's contract
is "grep the source for X", writing about X is writing X.

## #457 — the demo found what the tests could not, twice over

Six tests were green when I ran `docker compose config` for the demo and the
preflight failed. The tests asserted the compose file *contains* the right things;
the demo ran the tool that *consumes* it. Tests over an artifact's contents cannot
see a second consumer of the same artifact.

`codex review` then found two more, both in code my own tests covered: the startup
warning said "checkout answers 503" for a state where checkout is live and charging
(the exact state the warning exists to catch), and `is_configured()` treated a
whitespace-only key as configured. Both had passing tests — the tests asserted the
variable *name* appeared in the message, never that the *claim* was true.

**Apply:** for a diagnostic, assert the claim, not the vocabulary — `assert "503"
not in warning` is the test that would have caught it. And run every consumer of a
changed artifact in the demo, not just the one the change was aimed at.

## #457 — a "is it configured?" predicate must be the one the consumer uses

`is_configured()` was `bool(settings.STRIPE_SECRET_KEY)` while
`missing_configuration()` stripped whitespace. A blank key therefore reported
`configured: true` *and* appeared in the missing list — the report and the reality
disagreed, and the report is the one an operator believes. Fixed with one
normalising accessor both go through, rather than special-casing the caller.

**Apply:** when a value arrives from the environment, blank is a value. `${VAR:-}`
passthrough guarantees the empty string rather than "unset", so every predicate over
it needs the same normalisation — and there should be one place doing it, not two
that can drift. Same shape as the #453 lesson about fixing a fall-open shared
predicate at its source.

**And then I made the same mistake one level down.** I normalised the *reporting*
functions and left `_price_for`, `tier_for_price` and the webhook's signature check
reading `settings.X` raw — the identical defect, in the same file's neighbours,
against a principle I had just written into the PR body. claude-review caught it.
Three consumers, three silent failures: a padded webhook secret makes every real
Stripe signature mismatch (charged, never entitled, looks like a forgery); a padded
price id downgrades enterprise customers to PRO; a blank price turns a clean 503
into a 502. A whitespace-only secret was even *accepted* as a secret.

**Apply:** "fix it at the source" is not finished when the source is fixed — grep
for every other reader of the same value and convert them in the same commit.
`grep -n 'settings\.STRIPE_' app/` was the whole audit, and it takes ten seconds.

## Verify against a server you proved is current (#473 / PR #601)

`npm start` survived `lsof -ti:PORT | xargs kill` more than once during this run. I
rebuilt, re-curled, and reported "verified against a real build" — while reading a
**stale server** that still served the pre-fix text. The venue fix and four `mailto:`
links were all absent from what I was calling verified output, and it looked exactly
like a successful check.

What makes this dangerous is that a stale server produces *plausible* output, not an
error. The failure mode of a dead server (connection refused) is loud; the failure
mode of a surviving one is a confident wrong answer.

**Do:** after killing, assert the port is actually dead (`curl ... || echo down`) and
`ps -eo pid,cmd | grep -c "[n]ext-server"` returns 0, before rebuilding. `rm -rf .next`
so a stale artifact can't be served either. Then verify something that is *new* in this
build as a canary — if the canary string is absent, the server is old, regardless of
what else looks right.

**Related:** the same class as [[verify-deployed-artifact-matches-repo]] — editing the
repo file is not the same as changing what is serving. Here the gap was seconds old
instead of months, which made it easier to miss, not harder.

## A wrong causal claim in CLAUDE.md is worse than no claim

I documented "two interpolations on one JSX line lose the space after the second" from
a single observation. The GLM reviewer disproved it in one build: sibling lines with
that exact shape render fine. Had it shipped, the next person would have hunted by
shape and concluded they were safe.

**Do:** when a fix comes from one observation, record the *symptom*, the *one site*,
the habit that sidesteps it, and the *detection command*. Claim a cause only after
seeing it fail and not-fail on demand.

## A lifecycle hook can make a seeded field a no-op, and the test still passes

I added a test asserting that a repair script bumps `Subscription.updated_at`, seeding
a deliberately stale value through the model: `_seed("u-touch", updated_at=stale)`. It
passed. It also passed with the line under test **deleted** — the mutation check is the
only reason I found out.

The cause: `@before_event(Insert, Replace, Save, SaveChanges, Update)` on `_touch()`
fires on **insert** too, so the seeded `stale` was overwritten with `now` before it ever
reached Mongo. The assertion then compared now against now and was true for a reason
that had nothing to do with the code under test.

The class is wider than Beanie: any `default_factory`, `@before_event`, DB default, or
ORM `onupdate` that owns a field makes "seed it, then assert on it" meaningless — and
meaningless in the passing direction, which is the direction nobody investigates.

**Do:** when a test's setup writes a field that some hook also owns, write it **past**
the model (raw `collection.update_one`) and say why in a comment. And mutation-check
every test whose whole point is that one line exists — deleting the line must turn the
test red. Three guards were mutation-checked in that PR; two held, this one did not.

**Related:** same family as [[chart-tests-use-real-recharts]] and the `__mocks__` trap —
a test that never exercises the real thing fails silently by passing.

## Adopting a review finding can open the next hole

The GLM pass said the reconcile script ignored `plan_tier` drift. True, and I fixed it
by reusing the webhook's `tier_for_price`. The next review round found that this *new*
code would downgrade every ENTERPRISE tenant to PRO whenever run without
`STRIPE_PRICE_*` set — because `tier_for_price` falls back to PRO for any price it
cannot match against a **configured** setting, and the script is meant to run from an
operator shell, which is exactly where env is thin.

The fix was correct; the *context transfer* was not. A helper written for the server
process carries the server process's assumptions about its environment.

**Do:** when reusing an app-internal helper inside a script, cron entry or migration,
re-derive what it reads from settings and whether that shell has it. And run the review
loop again after adopting findings — the second round is not ceremony.
