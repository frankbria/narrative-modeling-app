#!/usr/bin/env bash
# Is a review bot failing to start? (#571)
#
# A `startup_failure` is GitHub refusing to start a workflow run at all: no job is
# created, so nothing inside the reviewer's own workflow can report it, and on a pull
# request it is indistinguishable from "the bot found nothing". GLM Review sat in that
# state for 266 runs. This looks from outside: for each reviewer workflow, if the latest
# run that actually ran ended in `startup_failure`, it opens an issue (or comments on the
# open one); once the reviewer starts again it closes it.
#
# Usage: review_bots_health.sh [--dry-run]     needs GH_TOKEN (actions: read, issues: write)
#        review_bots_health.sh --self-check    the verdict's case table; needs only jq
set -euo pipefail

WORKFLOWS=(glm-review.yml claude-code-review.yml)
# Searched for in titles. Never the full title: the operator retitles every issue with
# a PX.Y prefix, and an exact-title search then files a duplicate beside it (#757).
PHRASE='Review bot is failing at startup'

# stdin: runs as JSON, newest first. stdout: how many of the latest runs that ran, in a
# row, ended in startup_failure. Skipped, cancelled and unfinished runs say nothing
# about whether the workflow can start, so they are not counted either way.
failing_streak() {
  jq -r '
    def lead: if length > 0 and .[0] == "startup_failure" then 1 + (.[1:] | lead) else 0 end;
    [.[].conclusion | select(. != null and . != "" and . != "skipped" and . != "cancelled")] | lead'
}

self_check() {
  local failed=0 expected runs got
  while IFS='|' read -r expected runs; do
    got=$(printf '%s' "$runs" | failing_streak)
    if [ "$got" != "$expected" ]; then
      echo "FAIL: expected $expected, got $got, for $runs"
      failed=1
    fi
  done <<'CASES'
0|[]
0|[{"conclusion":"success"}]
0|[{"conclusion":"failure"},{"conclusion":"startup_failure"}]
1|[{"conclusion":"startup_failure"},{"conclusion":"success"}]
3|[{"conclusion":"startup_failure"},{"conclusion":"startup_failure"},{"conclusion":"startup_failure"}]
2|[{"conclusion":"skipped"},{"conclusion":"startup_failure"},{"conclusion":"cancelled"},{"conclusion":"startup_failure"},{"conclusion":"success"}]
0|[{"conclusion":null},{"conclusion":"success"},{"conclusion":"startup_failure"}]
1|[{"conclusion":""},{"conclusion":"startup_failure"}]
0|[{"conclusion":"skipped"},{"conclusion":"cancelled"}]
CASES
  [ "$failed" -eq 0 ] && echo "review_bots_health self-check: ok"
  return "$failed"
}

run() { # the one place a write happens, so --dry-run is one switch
  if [ "$DRY_RUN" = 1 ]; then echo "  would run: $*"; else "$@"; fi
}

check() {
  local workflow=$1 runs streak search existing body
  search="\"$PHRASE: $workflow\" in:title"
  runs=$(gh run list --workflow "$workflow" --limit 20 --json conclusion,url)
  streak=$(printf '%s' "$runs" | failing_streak)
  if [ "$streak" -eq 0 ]; then
    echo "$workflow: starts"
    for existing in $(gh issue list --state open --search "$search" --json number --jq '.[].number'); do
      run gh issue close "$existing" --comment "Recovered: the latest run of $workflow started."
    done
    return
  fi
  echo "$workflow: the latest $streak run(s) ended in startup_failure"
  body=$(printf '%s\n\n%s\n\n%s\n\n%s\n' \
    "The latest $streak run(s) of \`$workflow\` ended in \`startup_failure\`: GitHub refused to start them, so no job ran and nothing was posted on the pull requests. Latest: $(printf '%s' "$runs" | jq -r '.[0].url')" \
    "**A review from this window is absent, not clean.** Do not read a pull request without a reviewer comment as reviewed." \
    "The reason is shown only in the Actions UI, on the run's page. The two causes seen so far (#571, #575): the caller's \`permissions:\` block grants less than the pinned called workflow declares, or the caller declares a \`concurrency:\` group the called workflow also uses." \
    "Opened by \`scripts/ci/review_bots_health.sh\`; it closes this issue when the workflow starts again.")
  # `// empty`: on no match jq would print the string "null". The OLDEST open alert is
  # the thread of record, so a duplicate never becomes it.
  existing=$(gh issue list --state open --search "$search" --json number --jq 'min_by(.number).number // empty')
  if [ -n "$existing" ]; then
    run gh issue comment "$existing" --body "$body"
  else
    run gh issue create --title "[P2] [infra] $PHRASE: $workflow" --body "$body"
  fi
}

DRY_RUN=0
case "${1:-}" in
  --self-check) self_check; exit ;;
  --dry-run) DRY_RUN=1 ;;
  "") ;;
  *) echo "usage: $0 [--dry-run | --self-check]" >&2; exit 2 ;;
esac
for workflow in "${WORKFLOWS[@]}"; do
  check "$workflow"
done
