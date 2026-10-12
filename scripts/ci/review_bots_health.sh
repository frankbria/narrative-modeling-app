#!/usr/bin/env bash
# Is a review bot failing to start? (#571)
#
# A reviewer can fail before any job exists, and then nothing inside its own workflow
# can report it; on a pull request that is indistinguishable from "the bot found
# nothing". Two ways are known (#571, #575): GitHub refuses to start the run
# (`startup_failure`: the caller grants fewer permissions than the called workflow
# declares), or the called workflow cancels its own caller as it queues (`cancelled`
# after two seconds: both declare the same concurrency group). GLM Review sat in the
# first state for 266 runs. This looks from outside: it opens an issue (or comments on
# the open one) when a reviewer workflow is in either state, and closes it once the
# workflow runs again.
#
# Usage: review_bots_health.sh [--dry-run]     needs GH_TOKEN (actions: read, issues: write)
#        review_bots_health.sh --self-check    the verdict's case table; needs only jq
set -euo pipefail

WORKFLOWS=(glm-review.yml claude-code-review.yml)
# Searched for in titles. Never the full title: the operator retitles every issue with
# a PX.Y prefix, and an exact-title search then files a duplicate beside it (#757).
PHRASE='Review bot is failing at startup'

# stdin: runs as JSON, newest first. stdout: how many of the latest runs, in a row, never
# ran (0 = the workflow starts).
#
# A run that never ran ended in `startup_failure` or `cancelled`. One startup failure at
# the head is enough: it is a configuration error, never a blip. A cancelled run is also
# what a superseded push looks like, so cancellations count only as three or more in a
# row with nothing after them: a series of pushes ends in a run that was not cancelled.
# A head run that has not finished is a run with jobs, so the workflow starts. Skipped
# runs (bot authors, docs-only) say nothing either way.
failing_streak() {
  jq -r '
    def lead: if length > 0 and (.[0] == "startup_failure" or .[0] == "cancelled") then 1 + (.[1:] | lead) else 0 end;
    [.[].conclusion | select(. != "skipped")] as $c
    | if ($c | length) == 0 or $c[0] == null or $c[0] == "" then 0
      else ($c | lead) as $n | if $c[0] == "startup_failure" or $n >= 3 then $n else 0 end
      end'
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
3|[{"conclusion":"skipped"},{"conclusion":"startup_failure"},{"conclusion":"cancelled"},{"conclusion":"startup_failure"},{"conclusion":"success"}]
0|[{"conclusion":null},{"conclusion":"success"},{"conclusion":"startup_failure"}]
0|[{"conclusion":""},{"conclusion":"startup_failure"},{"conclusion":"startup_failure"}]
0|[{"conclusion":"skipped"},{"conclusion":"cancelled"}]
3|[{"conclusion":"cancelled"},{"conclusion":"cancelled"},{"conclusion":"cancelled"},{"conclusion":"success"}]
0|[{"conclusion":"cancelled"},{"conclusion":"cancelled"},{"conclusion":"success"}]
0|[{"conclusion":null},{"conclusion":"cancelled"},{"conclusion":"cancelled"},{"conclusion":"cancelled"}]
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
  echo "$workflow: the latest $streak run(s) never ran"
  body=$(printf '%s\n\n%s\n\n%s\n\n%s\n' \
    "The latest $streak run(s) of \`$workflow\` never ran: each ended in \`startup_failure\` or was cancelled, so no review was posted on the pull requests. Latest: $(printf '%s' "$runs" | jq -r '.[0].url') ($(printf '%s' "$runs" | jq -r '.[0].conclusion'))" \
    "**A review from this window is absent, not clean.** Do not read a pull request without a reviewer comment as reviewed." \
    "The reason is shown only in the Actions UI, on the run's page. The two causes seen so far (#571, #575): the caller's \`permissions:\` block grants less than the pinned called workflow declares (\`startup_failure\`), or the caller declares a \`concurrency:\` group the called workflow also uses, so the callee cancels its own caller (\`cancelled\` after about two seconds)." \
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
