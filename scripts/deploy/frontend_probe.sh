#!/usr/bin/env bash
# Frontend readiness for the staging probe (#756). Runs ON THE BOX via
# `ssh host "DEPLOY_PATH=… bash -s" < scripts/deploy/frontend_probe.sh` from
# staging-health.yml and deploy.yml, after the backend probe.
#
# The frontend container shares MONGODB_URI and NEXTAUTH_SECRET with the backend, and
# a stale value there breaks sign-in while every page still renders. Its
# /api/health/ready (apps/frontend/lib/health/readiness.ts) opens a fresh Mongo
# connection and has the backend verify a token it signed. The edge sends /api/health*
# to the backend, so the route is asked from inside the container.
#
# Output lands in a public issue and a public run log: one line, the route's own
# report (statuses and error class names, by construction) or a fixed phrase. The
# exit code is the verdict.
set -u
cd "${DEPLOY_PATH:-/opt/narrative-modeling-app/staging}" 2>/dev/null || { echo "frontend: unhealthy (no deploy directory)"; exit 1; }
compose() { docker compose -f docker-compose.staging.yml --env-file .env.staging "$@"; }

answer=$(compose exec -T frontend curl -sS -m 30 -w '\n%{http_code}' http://localhost:3000/api/health/ready 2>/dev/null) || {
  echo "frontend: unhealthy (the frontend container did not answer)"
  exit 1
}
code=${answer##*$'\n'}
body=${answer%$'\n'*}

# An image built before the route existed: nothing to ask yet, and not a failure.
if [ "$code" = 404 ]; then
  echo "frontend: skipped (this image has no readiness route)"
  exit 0
fi

# Only the route's own report is repeated; anything else is named, not printed, and
# is a failure whatever the status code says.
case "$body" in
  '{"status":'*) echo "frontend: $body" ;;
  *) echo "frontend: unhealthy (the readiness route answered $code with no report)"; exit 1 ;;
esac
[ "$code" = 200 ]
