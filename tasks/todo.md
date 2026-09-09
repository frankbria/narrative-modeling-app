# Issue #457 — [P0.14] No STRIPE_* or PLAN_* variables reach the backend container

Branch: `fix/457-staging-stripe-env`

## Problem (verified)
- `docker-compose.staging.yml` backend `environment:` block has zero `STRIPE_*` / `PLAN_*` keys.
- `grep -rn STRIPE .env.staging.example .env.production.example apps/backend/.env.example docs/deployment/` → **no hits**.
- Effect: `stripe_client.is_configured()` false → `/billing/checkout` 503, webhook 400 on every event,
  `BillingStatus.configured=false`. All silent — degrading gracefully is deliberate (ADR-002).

## Decisions (stated for the PR)
- **AC2 — optional, not `${VAR:?}`.** Real Stripe keys are not yet provisioned on the box
  (issue comment: `printenv | grep STRIPE_` returns nothing). A `${VAR:?}` guard would make
  `scripts/deploy/preflight_staging_env.sh` fail the *next* deploy and take staging down.
  So: `${VAR:-}` passthrough now, with an in-file comment naming the exact one-line switch
  to `${VAR:?}` once the keys exist. The switch is filed as a follow-up issue.
- **AC4 — `PLAN_*` not passed; `plans.py` defaults are intended.** The defaults are placeholders
  (ADR-002, #474/P0.31), but the fix for that is real numbers in `plans.py`, one place, applied
  everywhere. 12 env passthroughs would add 12 drift surfaces on a box whose config is
  hand-maintained (#594). `_env_int` already falls back on a bad/empty value, so nothing is lost.
- **`STRIPE_PUBLISHABLE_KEY` not passed.** Read into `Settings` but no code reads it back
  (`grep` → config.py only) and the frontend has no Stripe code — checkout is hosted.

## Steps
1. **RED** — `apps/backend/tests/test_security/test_staging_billing_env.py`: parse the real
   compose + the real env examples. Assert the backend service passes the four vars, that
   they are interpolated from the env file (not hardcoded), and that both env examples
   document each one. Follows the `test_staging_ports.py` / `test_nginx_webhook_route.py`
   precedent of parsing real artifacts.
2. **RED** — startup-visibility test: a production-like env with no `STRIPE_SECRET_KEY`
   logs a warning naming the missing vars. This is the "checklist that would catch the
   omission" the issue asks for, and the only mechanism that survives a hand-edited box.
3. **GREEN** — compose: add the four vars to the backend `environment:` block.
4. **GREEN** — `.env.staging.example` + `apps/backend/.env.example`: document all four,
   the `PLAN_*` decision, and the Stripe dashboard endpoint URL.
5. **GREEN** — `app/main.py` lifespan: log billing configuration state next to the existing
   "Auth mode" line.
6. Verify: full backend gate suite, ruff, mypy, `preflight_staging_env.sh --self-check`.
7. Demo: render the compose file with a fake `.env.staging` and show the four values landing
   in the resolved backend env; run the app locally with those values and show
   `/billing/status → configured: true` and a signed webhook writing an entitled Subscription.

## Known limitation (carried into the PR)
**AC5 cannot be closed in this PR.** It needs (a) real Stripe test keys written into
`.env.staging` on the box and (b) SSH to the staging VPS — this session has neither
(SSH is blocked here). The code change is the whole of AC1–AC4; AC5 is an operator step,
and a follow-up issue carries it with the exact commands.
