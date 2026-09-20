# #594 (P1.37) — Deploy the nginx edge config

The repo's `nginx-staging.conf` is applied by nothing; the live file was last touched
2026-07-01 and is missing the security headers, the #273 request-id map, `/api/health`,
the #456 webhook block (hand-applied later) and #768's auth rate limit. Editing the repo
file ships nothing, and nothing says so at runtime.

## Steps

1. **Template the two placeholders out of `nginx-staging.conf`** — `${NGINX_SERVER_NAME}`
   (both server blocks) and `${NGINX_CERT_DIR}` (the three cert paths). Those placeholders
   are why the file could never be applied verbatim. Nothing else changes, so the three
   existing guard tests keep parsing it.
2. **`scripts/deploy/apply_nginx_conf.sh`** — runs on the box over `ssh … bash -s`, same
   shape as `backend_state.sh`:
   - reads `NGINX_SERVER_NAME` / `NGINX_CERT_DIR` from `.env.staging`;
   - **unset ⇒ no-op with a warning, exit 0** — nothing touches the live edge until the
     operator provisions them, which is also how the deploy-secret preflight behaves;
   - renders with `envsubst '${NGINX_SERVER_NAME} ${NGINX_CERT_DIR}'` (the explicit var
     list is load-bearing: a bare `envsubst` eats `$remote_addr`, `$host`, `$req_id`);
   - identical to live ⇒ prints "no change" and does not reload;
   - otherwise backs the live file up to `<target>.bak-<utc>`, writes, `nginx -t`, and on
     failure **restores the backup and re-tests** before exiting non-zero;
   - symlinks into `sites-enabled` if missing, then `systemctl reload nginx`;
   - `--check` diffs only (exit 1 on drift), `--self-check` runs the parsing/rendering
     assertions locally, following `preflight_staging_env.sh`'s convention.
3. **`deploy.yml`** gains an "Apply nginx edge config" step between the deploy and the
   health check, piping the script over ssh with `DEPLOY_PATH`.
4. **Test** `apps/backend/tests/test_security/test_nginx_template.py`: no `yourdomain.com`
   placeholder survives; every `${…}` in the config is in the script's substitution list
   (a new placeholder that `envsubst` is not told about renders literally into live nginx);
   `deploy.yml` actually invokes the script.
5. **Docs**: rewrite Step 6 of `STAGING_DEPLOYMENT_GUIDE.md`, update the CLAUDE.md
   "edge config is not deployed by anything" bullet.
6. **Operator follow-up issue**: provision the two variables, run the first apply, diff the
   backup against the rendered file and confirm nothing live-only was lost (AC2's other
   half — the live file is not readable from an agent session).

## Decisions (autonomous)

- **The repo file becomes authoritative** on first apply, with the live copy backed up in
  place. The alternative — merge live into repo first — needs the live file, which no agent
  session can read; the backup plus the operator diff covers the same ground without
  blocking the mechanism.
- **Fail-safe by omission**: no variables ⇒ no write. A first deploy after merge changes
  nothing on the box, so this cannot break a shared VPS on the way in.
- **`.env.staging`, not compose**, carries the two variables: nginx runs on the host, not
  in a container, so the compose contract (#457) does not reach it.

## Known limitation

`nginx -t` validates the *whole* server config, so a pre-existing unrelated error on the
box makes the apply refuse and roll back — correct, but it will read as this step's failure.
