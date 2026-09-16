# #757 — Staging health probe alert: dedupe survives retitling, report carries container state

Bot-filed duplicate of #755 (retitled `[P1.51] …` → the workflow's exact-title search
missed it and opened #757). The box itself (backend not serving since 2026-09-15) is
operator work tracked on #755; this PR makes the alert correct and actionable.

## Steps
1. [x] `scripts/deploy/backend_state.sh` — run over `ssh … bash -s`: `docker compose ps backend`,
       `docker inspect` (RestartCount/OOMKilled/ExitCode/StartedAt/Health), and an exception-CLASS
       histogram of the last 200 backend log lines. Never raw log lines (repo is PUBLIC; a pymongo
       auth error carries the cluster hostname). Test: fake `docker` shim on PATH → output has
       `OperationFailure`, not `mongodb.net` / the URI.
2. [x] `staging-health.yml`: checkout; capture probe stdout/stderr separately; report leads with the
       exit status (137 → "killed under a restarting container"), then the verdict, then the state
       dump, stderr in `<details>`; dedupe search on the stable phrase (prefix-agnostic), comment on
       the oldest match, recovery closes EVERY open match.
3. [x] `deploy.yml`: same state dump step on Health-check failure (log + step summary).
4. [x] `analytics_result_in.py`: `schema_extra` → `model_config = ConfigDict(json_schema_extra=…)`
       (one of the four stderr warnings).
5. [x] `test_staging_health_wiring.py`: dedupe phrase carries no priority prefix and matches a
       retitled title; both workflows invoke the state script; script never emits raw log lines.
6. [x] CLAUDE.md #552 paragraph: one sentence on the state dump + prefix-agnostic dedupe.
7. [x] Demo: `gh workflow run staging-health.yml --ref <branch>` (Development env has no branch
       policy) → the run's report shows the container state; post the summary on #755.

## Acceptance criteria
- [ ] A retitled `[P1.51] [ops] Staging health probe is failing — …` is found by the dedupe search (test).
- [ ] A failing run's issue comment shows exit code + container state + exception classes, no raw log lines.
- [ ] Recovery closes every open alert issue, not `.[0]`.
- [ ] Existing wiring tests still pass; ruff/mypy clean.

## Result of the live demo (dispatched from this branch)
- Run 35146007041: `RestartCount=3448 OOMKilled=false`, `Worker failed to boot`, `is not writable (NoSuchBucket)` →
  the bucket named in `.env.staging` does not exist; #495's fail-fast refuses every boot. Operator fix posted on #755.
- The report commented on #755 (oldest open alert), not #757 — dedupe fix verified live.
