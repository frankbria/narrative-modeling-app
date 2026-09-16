# #552 [P1.33] — A credential rotation can leave staging dead for weeks with nothing detecting it

Plan source: self-authored (no plan comment on the issue). Authored against the code on 2026-09-15.

## What the code already asserts (AC2, confirmed)
- `/health` = liveness only (no I/O). `/health/ready` = MongoDB ping only, **by design** (#503:
  unauthenticated, LB-polled, no outbound third-party calls). S3 + OpenAI live behind auth at
  `GET /api/v1/health/dependencies`. `deploy.yml` curled bare `/health`, so a deploy passed with
  dead Atlas credentials as long as the worker booted — and `/health/ready` passes with S3 gone.
- Deepening readiness itself would reopen #503; the fix is a probe that *consults* the
  per-subsystem checks on a schedule and after every restart.

## Steps
1. `apps/backend/app/health_probe.py` — `python -m app.health_probe` (under `app/` because the
   runtime image copies nothing else). GETs the running service's `/health/ready`, then runs
   `check_s3_access` / `check_openai_api` in-process (fresh connection, container env). Exit 0
   only when every status is `healthy`; `not_configured` is a failure on staging. T20 exemption
   in `pyproject.toml`. Tests: `tests/test_scripts/test_health_probe.py` (MockTransport for the
   HTTP half, stubbed checks; one test against the real app + real Mongo via ASGITransport).
2. `.github/workflows/staging-health.yml` — hourly cron + dispatch; same secret gate, tailnet and
   SSH steps as `deploy.yml`; runs the probe via `docker compose exec -T backend`; on failure
   opens/comments a `[P1] [ops] Staging health probe is failing` issue, on success closes it.
3. `deploy.yml` health step — poll `/health/ready` (not `/health`), then run the probe in the
   freshly recreated container = the restart-after-rotation smoke step (AC4).
4. `docs/operations/CREDENTIAL_ROTATION.md` — every store + every consumer per secret (from
   compose + workflows, no hosts/users), the recreate-then-probe procedure (AC3).
5. `tests/test_security/test_staging_health_wiring.py` — parses the real files: runbook names
   every secret-like `${VAR}` compose interpolates; the health workflow has a schedule, the
   probe and `gh issue`; the deploy gate runs the probe and never curls bare `/health`.
6. Docs: link the runbook + probe from `docs/deployment/STAGING.md`; one CLAUDE.md bullet.

## Acceptance criteria
- [ ] AC1 scheduled check independent of deploys, failures reported where seen (step 2)
- [ ] AC2 checks connection-dependent health per subsystem, not liveness (steps 1, 3)
- [ ] AC3 rotation runbook enumerates every consumer (step 4, guarded by step 5)
- [ ] AC4 restart-after-rotation smoke step (step 3 for deploys; runbook step 3–4 for manual)

## Decisions made autonomously
- Probe is in-process for S3/OpenAI rather than minting a JWT for `/health/dependencies`: no
  impersonated user, no invite-allowlist email to fake, and a fresh connection by construction.
- Scheduled workflow over tailnet+SSH, per the issue ("does not need a monitoring stack").
- Hourly cadence: one ssh per run; MTTD was "until the next deploy".
- The operator half (the box must have `docker compose` + the rebuilt image before the probe
  exists there) lands with the next deploy; nothing here needs a hand-run on the box.
