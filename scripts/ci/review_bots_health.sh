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
# Usage: review_bots_health.sh [--dry-run]     needs GH_TOKEN (actions: read, issues: write,
#                                              pull-requests: read)
#        review_bots_health.sh --self-check    the verdict's case table; needs only jq
set -euo pipefail

WORKFLOWS=(glm-review.yml claude-code-review.yml)
# A green GLM Review run can still have reviewed nothing: since the callee's Codex → Kimi
# → Z.ai failover, a run where no reviewer posted ends green and says so on the PR in a
# "Reviewer failover" comment carrying NO_REVIEW (glm-review#17). Such a run counts as
# `no_review` (#1149). Its duration says nothing: a Codex review takes about 80 seconds.
NO_REVIEW='No reviewer produced a review for this commit'
# Searched for in titles. Never the full title: the operator retitles every issue with
# a PX.Y prefix, and an exact-title search then files a duplicate beside it (#757).
PHRASE='Review bot is failing at startup'

# stdin: runs as JSON, newest first. stdout: how many of the latest runs, in a row, never
# ran (0 = the workflow starts).
#
# A run that never ran ended in `startup_failure` or `cancelled`, or ran and reviewed
# nothing (`no_review`, from mark_unreviewed). One startup failure at the head is enough:
# it is a configuration error, never a blip. A cancelled run is also what a superseded
# push looks like, and one no-review run can be a provider blip, so those count only as
# three or more in a row with nothing after them.
# A head run that has not finished is a run with jobs, so the workflow starts. Skipped
# runs (bot authors, docs-only) say nothing either way.
failing_streak() {
  jq -r '
    def lead: if length > 0 and (.[0] | IN("startup_failure", "cancelled", "no_review")) then 1 + (.[1:] | lead) else 0 end;
    [.[] | .conclusion | select(. != "skipped")] as $c
    | if ($c | length) == 0 or $c[0] == null or $c[0] == "" then 0
      else ($c | lead) as $n | if $c[0] == "startup_failure" or $n >= 3 then $n else 0 end
      end'
}

# stdin: {runs, comments}; runs carry `prs` (their pull request numbers) where looked up,
# comments are the NO_REVIEW comments as {pr, at}. stdout: the runs' conclusions, a green
# run that posted one (on its pull request, inside its own window) turned into `no_review`.
mark_unreviewed() {
  jq -c '.comments as $c | [.runs[]
    | . as $run
    | if .conclusion == "success" and any($c[]; (.pr | IN(($run.prs // [])[])) and .at >= $run.createdAt and .at <= $run.updatedAt)
      then "no_review" else .conclusion end]'
}

# The NO_REVIEW comments since $1, as [{pr, at}].
no_review_comments() {
  gh api --paginate "repos/{owner}/{repo}/issues/comments?since=$1&per_page=100" \
    --jq ".[] | select(.body | contains(\"$NO_REVIEW\")) | {pr: (.issue_url | split(\"/\") | last | tonumber), at: .created_at}" \
    | jq -s -c .
}

# stdin: runs. stdout: the runs, `conclusion` turned into `no_review` where it applies.
# Only green runs with a NO_REVIEW comment inside their window need their pull requests
# looked up, so a healthy window costs one comments call. Looked up from the run's commit:
# a run's own `pull_requests` is empty once its pull request is merged.
with_no_review() {
  local runs since comments ids id prs
  runs=$(cat)
  since=$(printf '%s' "$runs" | jq -r 'map(.createdAt) | min // empty')
  [ -n "$since" ] || { printf '%s' "$runs"; return; }
  comments=$(no_review_comments "$since")
  ids=$(jq -rn --argjson runs "$runs" --argjson c "$comments" \
    '$runs[] | select(.conclusion == "success") | . as $r | select(any($c[]; .at >= $r.createdAt and .at <= $r.updatedAt)) | .databaseId')
  for id in $ids; do
    prs=$(gh api "repos/{owner}/{repo}/commits/$(jq -rn --argjson runs "$runs" --argjson id "$id" '$runs[] | select(.databaseId == $id) | .headSha')/pulls" --jq '[.[].number]')
    runs=$(printf '%s' "$runs" | jq -c --argjson id "$id" --argjson prs "$prs" 'map(if .databaseId == $id then .prs = $prs else . end)')
  done
  jq -n --argjson runs "$runs" --argjson c "$comments" '{runs: $runs, comments: $c}' | mark_unreviewed \
    | jq -c --argjson runs "$runs" '[range(length) as $i | $runs[$i] + {conclusion: .[$i]}]'
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
3|[{"conclusion":"no_review"},{"conclusion":"no_review"},{"conclusion":"no_review"},{"conclusion":"success"}]
0|[{"conclusion":"no_review"},{"conclusion":"no_review"},{"conclusion":"success"}]
0|[{"conclusion":"success"},{"conclusion":"no_review"},{"conclusion":"no_review"},{"conclusion":"no_review"}]
3|[{"conclusion":"no_review"},{"conclusion":"cancelled"},{"conclusion":"no_review"}]
CASES
  # Which green runs posted the callee's "no reviewer" comment: on one of the run's pull
  # requests, while the run was going.
  while IFS='|' read -r expected input; do
    got=$(printf '%s' "$input" | mark_unreviewed)
    if [ "$got" != "$expected" ]; then
      echo "FAIL: expected $expected, got $got, for $input"
      failed=1
    fi
  done <<'CASES'
["no_review"]|{"comments":[{"pr":7,"at":"2026-11-01T10:05:00Z"}],"runs":[{"conclusion":"success","prs":[7],"createdAt":"2026-11-01T10:00:00Z","updatedAt":"2026-11-01T10:06:00Z"}]}
["success"]|{"comments":[{"pr":8,"at":"2026-11-01T10:05:00Z"}],"runs":[{"conclusion":"success","prs":[7],"createdAt":"2026-11-01T10:00:00Z","updatedAt":"2026-11-01T10:06:00Z"}]}
["success"]|{"comments":[{"pr":7,"at":"2026-11-01T11:00:00Z"}],"runs":[{"conclusion":"success","prs":[7],"createdAt":"2026-11-01T10:00:00Z","updatedAt":"2026-11-01T10:06:00Z"}]}
["failure"]|{"comments":[{"pr":7,"at":"2026-11-01T10:05:00Z"}],"runs":[{"conclusion":"failure","prs":[7],"createdAt":"2026-11-01T10:00:00Z","updatedAt":"2026-11-01T10:06:00Z"}]}
["success","no_review"]|{"comments":[{"pr":7,"at":"2026-11-01T10:05:00Z"}],"runs":[{"conclusion":"success","createdAt":"2026-11-01T12:00:00Z","updatedAt":"2026-11-01T12:06:00Z"},{"conclusion":"success","prs":[7],"createdAt":"2026-11-01T10:00:00Z","updatedAt":"2026-11-01T10:06:00Z"}]}
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
  runs=$(gh run list --workflow "$workflow" --limit 20 --json conclusion,url,createdAt,updatedAt,databaseId,headSha | with_no_review)
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
    "The latest $streak run(s) of \`$workflow\` never reviewed: each ended in \`startup_failure\`, was cancelled, or ran green while every reviewer failed over (\`no_review\`: the run posted \"$NO_REVIEW\" on its pull request), so no review was posted. Latest: $(printf '%s' "$runs" | jq -r '[.[] | select(.conclusion != "skipped")][0] | "\(.url) (\(.conclusion))"')" \
    "**A review from this window is absent, not clean.** Do not read a pull request without a reviewer comment as reviewed." \
    "For \`no_review\`, the run's \"Reviewer failover\" comment names each reviewer's outcome; all three keys expiring or running out together is the usual cause. For the others, the reason is shown only in the Actions UI, on the run's page. The two causes seen so far (#571, #575): the caller's \`permissions:\` block grants less than the pinned called workflow declares (\`startup_failure\`), or the caller declares a \`concurrency:\` group the called workflow also uses, so the callee cancels its own caller (\`cancelled\` after about two seconds)." \
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
