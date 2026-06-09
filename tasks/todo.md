# Staging deploy fix — Atlas Mongo + real GH CI deploy

## Problems found
1. `docker-compose.staging.yml` hardcodes `MONGODB_URI` to a local `mongodb` container and gates backend startup on it — but staging uses MongoDB Atlas (`mongodb+srv://` in `.env.staging`).
2. Compose never passes `MONGODB_DB`, which `apps/backend/app/main.py` requires.
3. `deploy.yml` runs compose with no `--env-file`; `.env.staging` values are only picked up today because a duplicate `.env` copy exists.
4. Port conflict: podcaststudiohub (separate app, `PORT=3010` in its own .env.production) occupies 3010; narrative frontend + nginx upstream also claim 3010. → Move narrative frontend to **3011** (verified free), don't touch the other app.
5. API path mismatch: frontend expects `NEXT_PUBLIC_API_URL` to include `/api/v1` (fallback `http://localhost:8000/api/v1`), but server env has `.../api` AND nginx strips `/api` (trailing-slash proxy_pass) while backend routes start with `/api/v1`. → nginx should NOT strip; env should be `https://dev.briaanalytics.com/api/v1`.
6. GH secrets `STAGING_*` not set → deploy workflow no-ops.

## Plan
- [ ] Repo branch `fix/staging-deploy-atlas`:
  - [ ] compose: drop mongodb service/volumes/depends_on; `MONGODB_URI`/`MONGODB_DB` from env; frontend host port 3011
  - [ ] deploy.yml: `--env-file .env.staging` on compose commands
  - [ ] nginx-staging.conf (repo copy): upstream 3011; `/api/` proxy without prefix strip
  - [ ] .env.staging.example: Atlas URI example, MONGODB_DB, NEXT_PUBLIC_API_URL with /api/v1
  - [ ] STAGING_DEPLOYMENT_GUIDE.md: reflect Atlas + env-file + ports
- [ ] PR → CI green → merge
- [ ] Server: fix NEXT_PUBLIC_API_URL in .env.staging; remove stale narrative-staging-mongodb container; install updated nginx conf (nginx -t, reload); pull main
- [ ] Set GH secrets (STAGING_SSH_PRIVATE_KEY/HOST/USER); workflow_dispatch deploy.yml; verify /health via 8010 + https://dev.briaanalytics.com
