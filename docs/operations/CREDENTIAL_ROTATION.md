# Credential rotation runbook (staging)

Issue #552. Rotating a credential and updating the thing that holds it were two
procedures coupled only by memory, and the gap was invisible: a backend that
authenticated to Atlas before the rotation keeps its pooled connections (SCRAM
authenticates per connection), so the running process serves normally and the
outage arms itself to fire at the next restart — a deploy, a host reboot, an OOM
— weeks later, during an unrelated change. The frontend shares the same URI and
fails **silently** (pages render, sign-in breaks).

This page makes rotation one procedure: every consumer of each secret, the
update, a forced recreate, and a fresh-connection probe. Host addresses, users
and cluster names are deliberately omitted — see the operator's local runbook.

## Where the secrets live

| Store | What it holds | Read by |
|---|---|---|
| `.env.staging` on the staging box (hand-edited, **not** in git) | every application secret below | `docker compose -f docker-compose.staging.yml --env-file .env.staging` — values are injected at container **creation** |
| GitHub Environment `Development` (Settings → Environments) | CI's way onto the box: `SSH_KEY`, `HOST`, `SSH_KNOWN_HOSTS`, `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET` (optional `DEPLOY_USER`, `DEPLOY_PATH`) | `deploy.yml`, `staging-health.yml` |
| GitHub repository secrets | backup verification: `AWS_ROLE_TO_ASSUME`, `AWS_REGION`, `AWS_BUCKET_NAME`, `ATLAS_PUBLIC_KEY`, `ATLAS_PRIVATE_KEY`, `ATLAS_GROUP_ID`, `ATLAS_CLUSTER_NAME` | `backup-verify.yml` |
| the operator's private secret record | the canonical copy of everything in `.env.staging` | a rebuild of the box; a value edited only on the box is lost on the next one |

## Consumers per application secret

Derived from `docker-compose.staging.yml`; `tests/test_security/test_staging_health_wiring.py`
fails if compose interpolates a secret this table does not name.

| Secret | `backend` | `frontend` | `redis` | Also | Notes |
|---|---|---|---|---|---|
| `MONGODB_URI` | yes | yes | | Atlas user/password; local `.env` if it points at Atlas | both services must be recreated; the frontend's failure is silent |
| `MONGODB_DB` | yes | yes | | | not a secret, but both halves must agree (#545) |
| `REDIS_PASSWORD` | yes (in `REDIS_URL`) | | yes | | rotate all three together or the backend cannot reach the cache |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | yes | | | IAM user | a dead key or a missing bucket shows as `s3: unhealthy` in the probe |
| `OPENAI_API_KEY` | yes | | | OpenAI dashboard | the app degrades to rule-based fallbacks; the probe still fails |
| `BACKEND_SECRET_KEY` | yes (as `SECRET_KEY`) | | | | nothing reads it today (#681) |
| `NEXTAUTH_SECRET` | yes | yes | | `ARTIFACT_SIGNING_KEY` fallback — read `docs/deployment/ARTIFACT_INTEGRITY.md` **before** rotating | rotating invalidates every session and, unless the signing key is pinned, every signed model artifact |
| `GOOGLE_CLIENT_SECRET` (`GOOGLE_CLIENT_ID`) | | yes | | Google Cloud console — redirect URI must still match `NEXTAUTH_URL` | |
| `GITHUB_SECRET` (`GITHUB_ID`) | | yes | | GitHub OAuth app | |
| `STRIPE_SECRET_KEY` | yes | | | Stripe dashboard | |
| `STRIPE_WEBHOOK_SECRET` | yes | | | Stripe dashboard → the webhook endpoint's signing secret | a trailing newline mismatches every signature (#457) |
| `SENTRY_DSN` | yes | | | Sentry project | optional |

`INVITE_ALLOWLIST`, `ADMIN_EMAILS`, the `STRIPE_PRICE_*` ids and the URL/origin
variables are configuration, not credentials; they travel the same path but need
no rotation step.

## Procedure

1. **Rotate at the provider** (Atlas, IAM, OpenAI, Stripe, the OAuth app). Where
   the provider allows two live credentials (IAM keys, Atlas users), create the new
   one first and delete the old one at step 5.
2. **Update every store** in the first table: `.env.staging` on the box **and** the
   operator's private record. Watch for a trailing newline or a quoted value —
   `preflight_staging_env.sh` checks presence, not shape.
3. **Recreate the consumers.** Compose injects env at creation, so never
   `restart`; from the deploy path on the box:

   ```bash
   docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --force-recreate backend frontend
   ```

   `--force-recreate` is deliberate: `up -d` alone recreates only when it sees a
   config change, and a process that inherits its authenticated pool proves nothing.
4. **Probe on a fresh connection.** Either dispatch the scheduled workflow
   (`gh workflow run staging-health.yml`) or run it directly on the box:

   ```bash
   docker compose -f docker-compose.staging.yml --env-file .env.staging exec -T backend python -m app.health_probe
   ```

   Every line must read `healthy`; the exit code is the verdict. Then load the
   sign-in page and sign in once — the frontend has no probe and shares
   `MONGODB_URI` and `NEXTAUTH_SECRET`.
5. **Retire the old credential** at the provider, and re-run step 4 — this is the
   check that no consumer was missed, because the old value stops working now.

## What watches between rotations

`staging-health.yml` runs the same probe hourly (secret-gated on the
`Development` environment, like `deploy.yml`). A failing run opens or comments on
a `[P1] [ops] Staging health probe is failing` issue and the next green run closes
it. `deploy.yml` runs the probe after every `up -d` as its health gate, so a
deploy-driven restart cannot pass on a dead credential either.
