# Staging deployment guide

Staging runs on a shared VPS (`dev.briaanalytics.com`; resolve it with
`dig +short dev.briaanalytics.com`, the IP has changed before) from
`docker-compose.staging.yml`: `backend`, `frontend` and `redis` containers. MongoDB
is a managed Atlas cluster; S3 is real AWS. After the first deploy, every push to
`main` deploys through `.github/workflows/deploy.yml` (Step 5).

| Service | Container | Host port (127.0.0.1 only) |
|---|---|---|
| backend | `narrative-staging-backend` | 8010 |
| frontend | `narrative-staging-frontend` | 3011 |
| redis | `narrative-staging-redis` | 6381 |

All commands on the box run from the deploy path, `/opt/narrative-modeling-app/staging`
by default, and always pass `--env-file .env.staging`: compose only auto-reads a file
literally named `.env`.

---

## Prerequisites Checklist

- [ ] SSH access to the box (port 22 is open only to the home subnet and the tailnet)
- [ ] DNS for the staging hostname pointing at the box
- [ ] AWS S3 bucket for staging, and an IAM user with object access to it
- [ ] MongoDB Atlas cluster, with the box's public IP in the project's IP Access List
- [ ] OpenAI API key
- [ ] Google and GitHub OAuth apps (callback `https://<host>/api/auth/callback/google` and `/github`)
- [ ] A Tailscale OAuth client with `tag:ci` scope, and a tailnet ACL letting `tag:ci` reach the box on port 22 (for CI deploys)

---

## Step 1: Install Docker Compose Plugin

```bash
ssh root@dev.briaanalytics.com
apt-get update
apt-get install docker-compose-plugin -y
docker compose version   # expect v2.x
```

---

## Step 2: Create Deployment User (optional)

CI deploys as `DEPLOY_USER`, which defaults to `root`. The deploy applies the nginx
config (Step 6), which writes `/etc/nginx/sites-available/narrative-staging.conf` and
runs `systemctl reload nginx`, so a non-root deploy user needs those rights too.
Only create a separate user if you also grant them and set `DEPLOY_USER`.

```bash
adduser narrative-deploy --disabled-password --gecos "Narrative Modeling Deployment"
usermod -aG docker narrative-deploy
mkdir -p /opt/narrative-modeling-app/staging
chown -R narrative-deploy:narrative-deploy /opt/narrative-modeling-app

# CI key: generate locally, then authorise the public half for the deploy user.
#   ssh-keygen -t ed25519 -C "github-actions-staging" -f ~/.ssh/narrative-staging
#   (on the box, as the deploy user) append it to ~/.ssh/authorized_keys, mode 600
```

---

## Step 3: Generate Secrets

```bash
# Redis password: hex, NOT base64. It is embedded in a redis:// URL, and base64's
# / + = characters break URL parsing.
openssl rand -hex 32   # REDIS_PASSWORD
openssl rand -hex 32   # NEXTAUTH_SECRET
```

`MONGODB_URI` is the `mongodb+srv://` string from Atlas (Database → Connect →
Drivers), with no database path. Record every value in the operator's private
secret record as well as on the box (`docs/ops/CREDENTIAL_ROTATION.md`).

---

## Step 4: Clone the Repository and Create `.env.staging`

```bash
mkdir -p /opt/narrative-modeling-app/staging
cd /opt/narrative-modeling-app/staging
git clone https://github.com/frankbria/narrative-modeling-app.git .
git checkout main

cp .env.staging.example .env.staging
chmod 600 .env.staging
# edit .env.staging; the example documents every variable
```

**Required** (a `${VAR:?}` guard in compose, checked by the preflight below):

- `MONGODB_URI`: Atlas connection string, bare (no database path)
- `REDIS_PASSWORD`: from Step 3 (do **not** set `REDIS_URL`; compose builds it)
- `S3_BUCKET_NAME`: the staging bucket; compose fans it out to every bucket name the backend reads
- `BACKEND_CORS_ORIGINS`: explicit origin(s), e.g. `https://<host>`; the backend refuses `*` in production-like envs
- `NEXTAUTH_SECRET`: from Step 3; shared by both halves
- `SIGNUP_MODE`: `invite` or `open` (#768). The preflight refuses any other value (#780). `open` admits any Google/GitHub account; do not switch to it before the #768 backstops and #769 telemetry are live in production.
- `INVITE_ALLOWLIST`: comma-separated invitee emails. Required by the preflight while `SIGNUP_MODE=invite`; see [Managing beta invitees](#managing-beta-invitees).

**Needed for a working site** (not guarded):

- `MONGODB_DB`: database name for both halves (compose defaults to `narrative_modeling-staging`)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`
- `OPENAI_API_KEY` (without it the app runs on rule-based fallbacks and the health probe fails)
- `NEXT_PUBLIC_API_URL`: `https://<host>/api/v1`; must include `/api/v1`. Baked into the frontend image at build, and also passed to the backend as `PUBLIC_API_URL`.
- `NEXTAUTH_URL`: `https://<host>`
- `ALLOWED_ORIGINS`: frontend page-middleware CORS allowlist; may be empty
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_ID`, `GITHUB_SECRET`
- `NGINX_SERVER_NAME`: set only once the certificate exists (Steps 6 and 7)

**Optional:** `ADMIN_EMAILS` (unset = nobody is admin), `NEXT_PUBLIC_INVITE_REQUEST_URL`,
`SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `APP_VERSION`, the backstops
`AI_CALLS_DAILY_CEILING` (default 500 model calls/day across all tenants) and
`SIGNUP_ALERT_THRESHOLD_24H` (default 100 new accounts/day before the probe fails),
and the four Stripe values `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
`STRIPE_PRICE_PRO`, `STRIPE_PRICE_ENTERPRISE`. Without Stripe, billing is inert and
every tenant gets FREE limits (ADR-002). Provision the four together: a secret key
with no webhook secret takes money and entitles nobody.

> **No inline comments in `.env.staging`.** `VAR=value  # note` makes the comment part
> of the value, because `docker compose --env-file` does not support them. Put
> comments on their own line.

Check the file before every hand-run deploy:

```bash
bash scripts/deploy/preflight_staging_env.sh docker-compose.staging.yml .env.staging
```

It prints the complete list of missing required variables, and refuses an invalid
`SIGNUP_MODE` or `invite` with an empty allowlist.

---

## Step 5: Deploy Application Code

### Option A: Manual (first deploy)

```bash
cd /opt/narrative-modeling-app/staging
bash scripts/deploy/preflight_staging_env.sh docker-compose.staging.yml .env.staging
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build --remove-orphans
docker compose -f docker-compose.staging.yml --env-file .env.staging ps
```

### Option B: Automated (GitHub Actions)

`deploy.yml` runs on every push to `main` and on `workflow_dispatch`. It joins the
tailnet, SSHes to the box, and runs in the deploy path:

1. `git fetch --prune origin && git checkout main && git reset --hard origin/main`
2. `scripts/deploy/preflight_staging_env.sh`
3. `docker compose ... up -d --build --remove-orphans`
4. `scripts/deploy/apply_nginx_conf.sh` (Step 6)
5. the health gate: waits for `http://localhost:8010/health/ready`, then runs
   `python -m app.health_probe` in the backend container and
   `scripts/deploy/frontend_probe.sh`
6. on failure, `scripts/deploy/backend_state.sh` (container status and exception class names)

**One-time setup.** Add these as environment secrets on the GitHub Environment
`Development` (Settings → Environments → Development), not as repository secrets:

| Secret | Value |
| --- | --- |
| `SSH_KEY` | Private key authorised for the deploy user (Step 2) |
| `HOST` | The box's **tailnet** MagicDNS name (`….ts.net`) or 100.x address; the public name hangs because port 22 is firewalled |
| `SSH_KNOWN_HOSTS` | Pinned host key, labelled with the same `HOST` value: `ssh-keyscan -H <tailnet-host> \| gh secret set SSH_KNOWN_HOSTS --env Development` (verify the fingerprint out of band) |
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client id (`tag:ci`) |
| `TS_OAUTH_SECRET` | Tailscale OAuth client secret |
| `DEPLOY_USER` | Optional; defaults to `root` |
| `DEPLOY_PATH` | Optional; defaults to `/opt/narrative-modeling-app/staging` |

Until the five required secrets are set, the job is a **no-op that succeeds with a
warning** naming the missing ones. Application secrets stay in `.env.staging` on the
box and never pass through CI. The checkout must already exist at `DEPLOY_PATH`
with `origin` pointing at this repo (Step 4). The same secrets drive
`staging-health.yml`, which runs the probes hourly.

**Adding a step that runs on the box.** Every step in `deploy.yml` and
`staging-health.yml` reaches the server through `scripts/deploy/on_box.sh`, never
its own `ssh` line (#790):

```yaml
run: |
  scripts/deploy/on_box.sh scripts/deploy/my_step.sh      # a script in the repo
  scripts/deploy/on_box.sh <<'REMOTE'                     # or a short inline body
  cd "$DEPLOY_PATH"
  docker compose -f docker-compose.staging.yml --env-file .env.staging ps
  REMOTE
```

The body reads `"$DEPLOY_PATH"` from its environment; do not write the value into
the command (`ssh host "cd '$DEPLOY_PATH'"`), because ssh hands the far shell one
string to parse and a quote in the value ends the quoting. Keep the heredoc
quoted (`<<'REMOTE'`), or the runner expands it before it is sent. The wrapper
also saves the body on the box before running it, so a command that reads stdin
(`docker compose exec`) cannot swallow the rest of it.
`apps/backend/tests/test_security/test_deploy_on_box.py` fails on a raw `ssh` in a
workflow.

---

## Step 6: Configure Nginx Reverse Proxy

The edge config is **deployed, not pasted** (#594). `nginx-staging.conf` is a template;
`scripts/deploy/apply_nginx_conf.sh` renders it and installs it as
`/etc/nginx/sites-available/narrative-staging.conf`, and `deploy.yml` runs it on every
deploy. Two variables in `.env.staging` drive it:

```bash
NGINX_SERVER_NAME=dev.sheetpredict.app
# Optional; defaults to /etc/letsencrypt/live/$NGINX_SERVER_NAME, which is what
# certbot creates. Set it only if the cert lives somewhere else.
# NGINX_CERT_DIR=/etc/letsencrypt/live/dev.sheetpredict.app
```

**Until `NGINX_SERVER_NAME` is set, the script is a no-op that exits 0** and the live
file is not touched. Nothing is written to `/etc/nginx` until someone provisions the
value. Set it only after the certificate exists (Step 7). An inline comment on its
line produces a malformed `server_name` that fails `nginx -t` and rolls back.

```bash
cd /opt/narrative-modeling-app/staging
bash scripts/deploy/apply_nginx_conf.sh --check   # diff live vs rendered; exit 1 on drift; changes nothing
bash scripts/deploy/apply_nginx_conf.sh           # apply by hand (the deploy does this)
```

What the apply does, in order: render → compare with live (identical ⇒ no write, no
reload) → **back the live file up to `<target>.bak-<utc>`** (the five newest are kept)
→ install → `nginx -t` → on failure **restore the backup** and exit non-zero →
symlink into `sites-enabled` if it is not there → `systemctl reload nginx`. Only this
site's file is touched. The repo file is authoritative: anything worth keeping from a
backup belongs in `nginx-staging.conf`, not back on the box.

> **The Stripe webhook needs its own `location`.** The backend mounts
> `POST /webhooks/stripe/webhook` *outside* `/api/v1` (so the rate limiter cannot 429
> Stripe's small IP pool, #367), so `location /api/` does not cover it and it would
> fall through to the frontend, losing the event silently (#456).
> `nginx-staging.conf` carries that block and its `client_max_body_size` cap: the
> endpoint is unauthenticated and the backend reads the whole body before verifying the
> signature. `apps/backend/tests/test_security/test_nginx_webhook_route.py` pins it.

---

## Step 7: Setup SSL Certificate (Let's Encrypt)

Use `certbot certonly`, never bare `certbot --nginx`: without `certonly` certbot's
installer edits the live nginx file, which the next deploy reports as drift and
overwrites (#594).

The certificate has to exist **before** `NGINX_SERVER_NAME` names the host. The rendered
config points at `/etc/letsencrypt/live/<name>/`, so without it `nginx -t` fails and the
apply restores the previous file. Until that config is live, port 80 does not serve the
webroot for the new name either, so the first certificate comes from certbot's nginx
authenticator and renewal moves to the webroot afterwards:

```bash
apt-get install certbot python3-certbot-nginx -y    # if not already installed
mkdir -p /var/www/letsencrypt

# 1. First certificate. DNS for the name must already point at this box. The
#    authenticator adds a temporary challenge block and removes it.
certbot certonly --nginx -d dev.sheetpredict.app

# 2. Set NGINX_SERVER_NAME in .env.staging and deploy (Step 6).

# 3. Renew through the webroot the rendered config now serves, and prove it.
certbot reconfigure --cert-name dev.sheetpredict.app \
  --webroot --webroot-path /var/www/letsencrypt
certbot renew --dry-run --cert-name dev.sheetpredict.app
```

A webroot renewal does not reload nginx on its own. The box's
`/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh` does that for every certificate;
check it exists on a new box, or the renewed certificate is never served.

### Moving to a new hostname

Every line of `.env.staging` that carries the old name changes together:
`NGINX_SERVER_NAME`, `NEXTAUTH_URL`, `NEXT_PUBLIC_API_URL`, `BACKEND_CORS_ORIGINS` and
`ALLOWED_ORIGINS`. `NEXT_PUBLIC_API_URL` is baked into the frontend image, so the move
needs a deploy that rebuilds it, not a restart. The OAuth providers' callback URLs
(`https://<host>/api/auth/callback/google` and `/github`) and the Stripe webhook endpoint
(`https://<host>/webhooks/stripe/webhook`) must name the new host. Change them
immediately before triggering the deploy: sign-in on the old name stops working the
moment the callback is edited. A GitHub OAuth app allows one callback URL, so there is
no window in which both names sign in.

The template serves one name. The old one is not redirected: once nothing renders it,
delete its certificate (`certbot delete --cert-name <old>`) so renewal stops.

### Staging is never indexed

Every response carries `X-Robots-Tag: noindex, nofollow` unless the request's host is the
production name listed in the template's `map $host $narrative_robots_tag` (#830).
Production renders the same template, so the header is keyed on the hostname and a host
that is not listed stays unindexable. Check it with
`curl -sI https://<host>/ | grep -i x-robots-tag`.

---

## Step 8: Configure Firewall (UFW)

```bash
ufw status numbered
```

Expected: 80/443 open; 22 allowed only from the home subnet and `on tailscale0`
(CI connects over the tailnet). No app port needs a rule: nginx proxies to the
frontend (3011) and backend (8010) on localhost, and Redis (6381) is internal.

Do **not** `ufw allow` 3011/8010/6381 (#258). Compose publishes them on 127.0.0.1
only, and that loopback bind is the real control: Docker's iptables DNAT rules are
evaluated before UFW, so a public bind would leak past the firewall anyway.

---

## Step 9: Verify Deployment

```bash
cd /opt/narrative-modeling-app/staging
docker compose -f docker-compose.staging.yml --env-file .env.staging ps
# narrative-staging-backend    Up (healthy)
# narrative-staging-frontend   Up (healthy)
# narrative-staging-redis      Up (healthy)

curl -fsS http://localhost:8010/health/ready   # {"status":"ready",...}; 503 until Mongo answers
curl -fsS http://localhost:3011 >/dev/null && echo frontend ok

# Per-subsystem probe on fresh connections (Mongo, S3, OpenAI, signups_24h).
# Every line must read healthy; the exit code is the verdict.
docker compose -f docker-compose.staging.yml --env-file .env.staging exec -T backend python -m app.health_probe
bash scripts/deploy/frontend_probe.sh            # frontend: {"status":"healthy",...}

# Through the edge
curl -fsS https://<host>/api/health              # backend liveness: {"status":"alive",...}
curl -fsS https://<host>/ >/dev/null && echo edge ok
```

From a workstation, `gh workflow run staging-health.yml` runs the same probes.

---

## Step 10: Smoke Tests

In a browser, at `https://<host>`:

- [ ] The sign-in page loads
- [ ] Sign in with an allowlisted Google or GitHub account
- [ ] Upload a test dataset and see it on the dashboard
- [ ] `docker compose -f docker-compose.staging.yml --env-file .env.staging logs --tail=100 backend` shows no errors

---

## Monitoring and Maintenance

`staging-health.yml` runs the probes hourly; a failing run opens or comments on a
`[P1] [ops] Staging health probe is failing` issue and the next green run closes it.

### View Logs

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging logs -f
docker compose -f docker-compose.staging.yml --env-file .env.staging logs -f backend
docker compose -f docker-compose.staging.yml --env-file .env.staging logs --tail=100 backend
```

### Restart Services

Compose injects env at container **creation**. After any change to `.env.staging`,
recreate; `restart` keeps the old values:

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --force-recreate backend frontend
```

`restart` is only for a process that is stuck with correct config. Rotating a
credential follows `docs/ops/CREDENTIAL_ROTATION.md`.

### Update Application

Push to `main` (or dispatch `deploy.yml`). By hand, the same sequence:

```bash
cd /opt/narrative-modeling-app/staging
git fetch --prune origin && git checkout main && git reset --hard origin/main
bash scripts/deploy/preflight_staging_env.sh docker-compose.staging.yml .env.staging
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build --remove-orphans
bash scripts/deploy/apply_nginx_conf.sh
```

Then run the Step 9 checks.

### Database Backup

Atlas Cloud Backup and S3 versioning are the backup controls; enabling, verifying and
drilling them is `docs/ops/DATA_ERASURE_AND_BACKUP_RUNBOOK.md` (sections 2–5).

---

## Troubleshooting

### Container won't start

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging logs backend
docker compose -f docker-compose.staging.yml --env-file .env.staging ps -a
DEPLOY_PATH=/opt/narrative-modeling-app/staging bash scripts/deploy/backend_state.sh
```

`backend_state.sh` prints restart count, OOM flag, exit code, health and a histogram
of exception class names from the last 200 log lines. A climbing `RestartCount`
with `ExitCode=137` is a boot loop; compose aborting at `up` names the first missing `${VAR:?}`, so run the
preflight for the full list.

### MongoDB (Atlas) connection issues

```bash
docker exec narrative-staging-backend python -c "import os,pymongo; pymongo.MongoClient(os.environ['MONGODB_URI']).admin.command('ping'); print('atlas ok')"
```

Common causes: the box's IP missing from the Atlas IP Access List; a rotated
password (a running process keeps its pool, so this surfaces at the next recreate);
SRV lookups failing (`dig SRV _mongodb._tcp.<cluster-host>`). `MONGODB_DB` must be
the same for both halves (#545).

### Nginx issues

```bash
nginx -t
tail -f /var/log/nginx/narrative-staging-error.log
bash scripts/deploy/apply_nginx_conf.sh --check
```

### Network issues

```bash
docker exec narrative-staging-backend python -c "import redis,os; print(redis.Redis.from_url(os.environ['REDIS_URL']).ping())"
```

---

## Rollback Procedure

The durable rollback is a revert on `main`: the next deploy resets the box to
`origin/main`, so a hand checkout lasts only until then.

```bash
# Immediate, on the box
cd /opt/narrative-modeling-app/staging
git log --oneline -n 10
git checkout <previous-commit>
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build --remove-orphans
bash scripts/deploy/apply_nginx_conf.sh
# Step 9 checks, then revert the bad commit on main through a PR
```

A failed nginx apply needs no rollback: the script restores the previous file itself.

---

## Managing beta invitees

The beta is **free and invite-only** (ADR-001). OAuth admits any Google/GitHub
account, so signup is gated by an email allowlist (#261) while `SIGNUP_MODE=invite`.

**How it works:**
- `INVITE_ALLOWLIST` is a comma-separated list of invitee emails, passed to both
  the frontend and backend services.
- The **NextAuth `signIn` callback** (`apps/frontend/auth.ts`) is the primary
  gate: a non-listed email never gets a session and lands on the
  **"Invite Required"** page (`/auth/error?error=AccessDenied`) with a
  *Request access* button.
- The **backend** (`apps/backend/app/auth/nextauth_auth.py`) mirrors the check on
  the API token's `email` claim and returns **403** for a non-listed email. It reads
  the list per request, so a revocation takes effect within the token TTL (1 hour).
- In `invite` mode an **empty** `INVITE_ALLOWLIST` admits nobody, so the preflight
  fails the deploy if it is unset. In `open` mode the list is ignored. Compose itself
  does not check the list: a hand-run `up` with `SIGNUP_MODE=invite` and no list
  starts cleanly and locks every user out. Run the preflight first.

**To add an invitee:**
1. Append the email to `INVITE_ALLOWLIST` in `.env.staging`
   (e.g. `INVITE_ALLOWLIST=alice@example.com,bob@example.com`).
2. Run the preflight, then recreate both services (no rebuild; it is a runtime variable):
   ```bash
   bash scripts/deploy/preflight_staging_env.sh docker-compose.staging.yml .env.staging
   docker compose -f docker-compose.staging.yml --env-file .env.staging up -d backend frontend
   ```

**To revoke access:** remove the email and recreate the same way. A live session
token stops working at the backend within the token TTL.

> **API keys are not re-checked.** Model-serving routes authenticate with an API key
> (`X-API-Key`, `verify_api_key`) and do not consult `INVITE_ALLOWLIST`. Only an
> invited user can create one, but de-allowlisting a user does not disable their
> keys: revoke them (`DELETE /api/v1/production/api-keys/{key_id}`, as that user)
> or erase the account's data, which deletes its API keys.

**Optional:** `NEXT_PUBLIC_INVITE_REQUEST_URL` sets the *Request access* link
(a mailto by default).

---

## Security Checklist

- [ ] `SIGNUP_MODE=invite`, and `INVITE_ALLOWLIST` set to the intended beta cohort
- [ ] `ADMIN_EMAILS` lists only the operators
- [ ] Atlas IP Access List restricted to the staging box (no 0.0.0.0/0)
- [ ] Redis requires a password (compose enforces `REDIS_PASSWORD`)
- [ ] Certificate valid and renewal dry run passing (Step 7)
- [ ] `ufw status` matches Step 8; app ports bound to 127.0.0.1 (`ss -ltnp | grep -E ':(3011|8010|6381)'`)
- [ ] `.env.staging` mode 600 and not in git
- [ ] `apply_nginx_conf.sh --check` reports no drift
- [ ] `staging-health.yml` green; backup posture verified (`docs/ops/DATA_ERASURE_AND_BACKUP_RUNBOOK.md` section 4)
