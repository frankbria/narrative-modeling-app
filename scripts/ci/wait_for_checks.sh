#!/usr/bin/env bash
# Wait for the PR gate on a commit, without re-inventing the poll loop every session.
#
#   scripts/ci/wait_for_checks.sh <pr-number|sha> [--timeout SECONDS] [--interval SECONDS]
#
# Polls repos/{owner}/{repo}/commits/{sha}/check-runs (`gh pr checks` has no --json)
# and prints one status line per poll. Exit codes:
#   0  the aggregate "CI Success" check completed with success
#   1  "CI Success" completed with any other conclusion, or a gate job failed
#   2  timed out while runs were still in progress (re-issue the command)
# Run it in the FOREGROUND with a bounded --timeout (<= the tool's own cap); background
# waits get culled on low memory and look identical to "CI still running".
set -euo pipefail

usage() { sed -n '2,13p' "$0"; exit 2; }

ref="${1:-}"; [[ -n "$ref" ]] || usage; shift
timeout_s=570; interval=30; aggregate="CI Success"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout)  timeout_s="$2"; shift 2;;
    --interval) interval="$2"; shift 2;;
    --check)    aggregate="$2"; shift 2;;
    -h|--help)  usage;;
    *) echo "unknown arg: $1" >&2; usage;;
  esac
done

repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
if [[ "$ref" =~ ^[0-9]+$ ]]; then
  sha="$(gh pr view "$ref" --json headRefOid --jq .headRefOid)"
else
  sha="$(git rev-parse "$ref")"
fi

deadline=$(( $(date +%s) + timeout_s ))
while :; do
  runs="$(gh api "repos/$repo/commits/$sha/check-runs?per_page=100" --jq '[.check_runs[]|{name,status,conclusion}]')"
  total="$(jq length <<<"$runs")"
  done_n="$(jq '[.[]|select(.status=="completed")]|length' <<<"$runs")"
  agg="$(jq -r --arg n "$aggregate" '.[]|select(.name==$n)|"\(.status)/\(.conclusion)"' <<<"$runs")"
  failed="$(jq -r '.[]|select(.conclusion=="failure")|.name' <<<"$runs" | paste -sd, -)"
  printf '%s %s completed=%s/%s %s=%s failures=%s\n' "$(date +%T)" "${sha:0:7}" "$done_n" "$total" "$aggregate" "${agg:-pending}" "${failed:-none}"

  if [[ "$agg" == "completed/success" ]]; then exit 0; fi
  if [[ "$agg" == completed/* ]]; then
    echo "--- non-green runs:"; jq -r '.[]|select(.conclusion!="success")|"\(.name): \(.status)/\(.conclusion)"' <<<"$runs"
    exit 1
  fi
  if (( $(date +%s) >= deadline )); then
    echo "--- timed out with runs still in progress:"; jq -r '.[]|select(.status!="completed")|.name' <<<"$runs"
    exit 2
  fi
  sleep "$interval"
done
