#!/usr/bin/env bash
# Backend container state for the staging alert (#757). Runs ON THE BOX via
# `ssh host "DEPLOY_PATH=… bash -s" < scripts/deploy/backend_state.sh` from
# staging-health.yml / deploy.yml when the gate fails, and its output lands in a
# public issue and a public run log — so it prints status fields and exception
# CLASS names only, never a raw log line (a pymongo auth error names the Atlas
# cluster, a boto error the bucket).
set -u
cd "${DEPLOY_PATH:-/opt/narrative-modeling-app/staging}" 2>/dev/null || { echo "(no $DEPLOY_PATH)"; exit 0; }
compose() { docker compose -f docker-compose.staging.yml --env-file .env.staging "$@"; }

echo "## backend container"
compose ps backend --format '{{.Name}}  {{.Status}}' 2>/dev/null || echo "(compose ps failed)"
docker inspect narrative-staging-backend --format \
  'RestartCount={{.RestartCount}} OOMKilled={{.State.OOMKilled}} ExitCode={{.State.ExitCode}} StartedAt={{.State.StartedAt}} Health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
  2>/dev/null || echo "(inspect failed)"

echo "## exception classes in the last 200 backend log lines"
# Class names and a few fixed, hostname-free phrases; `grep -o` drops the rest of the line.
compose logs --no-log-prefix --tail 200 backend 2>&1 \
  | grep -oE '\b[A-Z][A-Za-z]*(Error|Exception|Failure)\b|An error occurred \([A-Za-z0-9]+\) when calling the [A-Za-z]+ operation|Worker failed to boot|exited with code [0-9]+|bad auth' \
  | sort | uniq -c | sort -rn
echo "(end)"
