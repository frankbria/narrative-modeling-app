#!/usr/bin/env bash
# Preflight for the staging deploy: verify every variable the compose file marks
# required via a ${VAR:?...} guard has a non-empty value in the env file.
#
# Why: `docker compose up` aborts on the FIRST missing ${VAR:?} it interpolates,
# so discovering a drifted .env.staging is a slow one-variable-at-a-time loop.
# This fails fast with the COMPLETE list. The required set is derived from the
# compose file itself, so it can never drift out of sync with the guards.
#
# Usage: preflight_staging_env.sh [compose-file] [env-file]
#        preflight_staging_env.sh --self-check   # assert the parsing rules below
set -euo pipefail

if [ "${1:-}" = "--self-check" ]; then
  # The value parsing below is the only non-obvious logic here, so it gets one
  # runnable check. No test framework in this repo for scripts/ — this is it.
  tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
  printf 'services:\n  a:\n    environment:\n      - X=${SET:?req}\n      - Y=${EMPTY:?req}\n      - Z=${QUOTED_EMPTY:?req}\n      - W=${SPACES:?req}\n      - V=${ABSENT:?req}\n' > "$tmp/compose.yml"
  printf 'SET=real-value\nEMPTY=\nQUOTED_EMPTY=""\nSPACES=   \n' > "$tmp/env"
  out=$("$0" "$tmp/compose.yml" "$tmp/env" 2>&1) && { echo "self-check FAILED: expected exit 1"; exit 1; }
  for v in EMPTY QUOTED_EMPTY SPACES ABSENT; do
    grep -q -- "- $v" <<<"$out" || { echo "self-check FAILED: $v not reported missing"; echo "$out"; exit 1; }
  done
  grep -q -- "- SET" <<<"$out" && { echo "self-check FAILED: SET wrongly reported missing"; exit 1; }
  printf 'SET=real\nEMPTY=x\nQUOTED_EMPTY="x"\nSPACES=x\nABSENT=x\n' > "$tmp/env"
  "$0" "$tmp/compose.yml" "$tmp/env" >/dev/null || { echo "self-check FAILED: expected exit 0"; exit 1; }
  echo "self-check OK"; exit 0
fi

compose_file="${1:-docker-compose.staging.yml}"
env_file="${2:-.env.staging}"

[ -f "$compose_file" ] || { echo "preflight: compose file not found: $compose_file" >&2; exit 2; }
[ -f "$env_file" ] || { echo "preflight: env file not found: $env_file" >&2; exit 2; }

# Names inside ${VAR:?...} guards in the compose file. `|| true` because grep
# exits 1 on no matches, which under `set -e` + `pipefail` would abort the whole
# script with no diagnostic if the compose file ever has zero guards.
required=$(grep -oE '\$\{[A-Za-z_][A-Za-z0-9_]*:\?' "$compose_file" \
  | sed -E 's/^\$\{//; s/:\?$//' | sort -u || true)

missing=()
for v in $required; do
  # Required means present AND non-empty — ${VAR:?} rejects an empty value too.
  # Match Compose's own --env-file parsing rather than the raw text: it strips a
  # matching pair of surrounding quotes and trims whitespace, so VAR="", VAR=''
  # and VAR=<spaces> all resolve to empty and would still trip ${VAR:?} at
  # `docker compose up`. A naive `grep -qE "^VAR=.+"` would pass them.
  value=$(sed -nE "s/^${v}=//p" "$env_file" | tail -n 1)
  value="${value%\"}"; value="${value#\"}"      # strip surrounding double quotes
  value="${value%\'}"; value="${value#\'}"      # strip surrounding single quotes
  value="${value//[[:space:]]/}"                # whitespace-only counts as empty
  [ -n "$value" ] || missing+=("$v")
done

if [ "${#missing[@]}" -gt 0 ]; then
  echo "preflight: $env_file is missing ${#missing[@]} required variable(s):" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  echo "preflight: add them (see .env.staging.example) and re-run the deploy." >&2
  exit 1
fi

echo "preflight: OK — all required variables present in $env_file"
