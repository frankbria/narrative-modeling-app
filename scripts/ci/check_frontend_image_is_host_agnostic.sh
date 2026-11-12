#!/usr/bin/env bash
# Prove one frontend image serves two hosts (#831):
#
#   scripts/ci/check_frontend_image_is_host_agnostic.sh <image>
#
# Starts the SAME image twice, once with staging's public settings and once with
# production's, and checks that each one's home page (and a page with nothing dynamic
# of its own) hands the browser its own API base, Sentry DSN and environment tag and
# nothing of the other's. An image with a value baked in
# at build serves that value from both containers and fails here.
set -euo pipefail
image=${1:?usage: check_frontend_image_is_host_agnostic.sh <image>}

# Named up front: home_page runs in a command substitution, so it cannot report back
# which containers it started.
containers=(narrative-host-agnostic-staging narrative-host-agnostic-production)
cleanup() { docker rm -f "${containers[@]}" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

# <environment> <public host> <local port>: prints the home page the container serves.
home_page() {
  local name="narrative-host-agnostic-$1"
  docker run -d --name "$name" -p "127.0.0.1:$3:3000" \
    -e ENVIRONMENT="$1" \
    -e NEXT_PUBLIC_API_URL="https://$2/api/v1" \
    -e NEXT_PUBLIC_SENTRY_DSN="https://public@$2/1" \
    -e NEXT_PUBLIC_SENTRY_ENVIRONMENT="$1" \
    -e NEXTAUTH_URL="https://$2" \
    -e NEXTAUTH_SECRET=not-a-real-secret-only-for-this-check \
    -e AUTH_TRUST_HOST=true \
    -e MONGODB_URI=mongodb://127.0.0.1:27017 -e MONGODB_DB=host-agnostic-check \
    -e GOOGLE_CLIENT_ID=check -e GOOGLE_CLIENT_SECRET=check -e GITHUB_ID=check -e GITHUB_SECRET=check \
    -e SIGNUP_MODE=open \
    "$image" >/dev/null
  local attempt
  for attempt in $(seq 1 30); do
    if curl -fsS -m 10 "http://127.0.0.1:$3/" 2>/dev/null; then return 0; fi
    sleep 2
  done
  echo "the $1 container did not serve its home page (after $attempt tries):" >&2
  docker logs --tail 30 "$name" >&2
  return 1
}

staging_page=$(home_page staging dev.host-agnostic.test 3981)
production_page=$(home_page production www.host-agnostic.test 3982)

failures=0
# <which page> <page text> <must contain> <must not contain>
expect() {
  if ! grep -qF -- "$3" <<<"$2"; then echo "FAIL: the $1 page does not carry $3"; failures=$((failures + 1)); fi
  if grep -qF -- "$4" <<<"$2"; then echo "FAIL: the $1 page carries the other host's $4"; failures=$((failures + 1)); fi
}
# The settings are JSON in an attribute of <html>, so their quotes arrive as &quot;.
setting() { printf '&quot;%s&quot;:&quot;%s&quot;' "$1" "$2"; }
expect staging "$staging_page" "$(setting NEXT_PUBLIC_API_URL https://dev.host-agnostic.test/api/v1)" 'www.host-agnostic.test'
expect staging "$staging_page" "$(setting NEXT_PUBLIC_SENTRY_DSN https://public@dev.host-agnostic.test/1)" 'public@www.host-agnostic.test'
expect staging "$staging_page" "$(setting NEXT_PUBLIC_SENTRY_ENVIRONMENT staging)" "$(setting NEXT_PUBLIC_SENTRY_ENVIRONMENT production)"
expect production "$production_page" "$(setting NEXT_PUBLIC_API_URL https://www.host-agnostic.test/api/v1)" 'dev.host-agnostic.test'
expect production "$production_page" "$(setting NEXT_PUBLIC_SENTRY_DSN https://public@www.host-agnostic.test/1)" 'public@dev.host-agnostic.test'
expect production "$production_page" "$(setting NEXT_PUBLIC_SENTRY_ENVIRONMENT production)" "$(setting NEXT_PUBLIC_SENTRY_ENVIRONMENT staging)"

# A page with nothing dynamic of its own. The settings reach it only because the root
# layout is rendered per request; were that to change, `next build` would prerender
# this page with the builder's (empty) settings while the home page could still pass.
static_looking=/legal/privacy
expect "staging $static_looking" "$(curl -fsS -m 30 "http://127.0.0.1:3981$static_looking")" \
  "$(setting NEXT_PUBLIC_API_URL https://dev.host-agnostic.test/api/v1)" 'www.host-agnostic.test'
expect "production $static_looking" "$(curl -fsS -m 30 "http://127.0.0.1:3982$static_looking")" \
  "$(setting NEXT_PUBLIC_API_URL https://www.host-agnostic.test/api/v1)" 'dev.host-agnostic.test'

# The settings must be in the page before the first script: modules read them as they
# load, and one that ran first would keep its localhost default for the whole visit.
# Next hoists async bundle tags to the top of <head>, so only <html> itself is early enough.
offset_of() { grep -bo -m 1 -- "$1" <<<"$staging_page" | head -n 1 | cut -d: -f1; }
settings_at=$(offset_of ' data-public-env=')
first_script_at=$(offset_of '<script')
if [ -z "$first_script_at" ] || [ "${settings_at:-$first_script_at}" -ge "$first_script_at" ]; then
  echo "FAIL: the settings (byte ${settings_at:-none}) do not come before the first script (byte ${first_script_at:-none})"
  failures=$((failures + 1))
fi

if [ "$failures" -gt 0 ]; then exit 1; fi
echo "OK: one image, two hosts: each page carries its own API base, Sentry DSN and environment tag, ahead of the first script"
