#!/usr/bin/env bash
# File a scheduled workflow's failure on a public issue (#1215). The one way
# staging-health.yml and subscription-reconcile.yml report:
#
#   printf '%s' "$body" | scripts/ci/file_alert.sh "$title" '<stable phrase>'
#
# Comments on the oldest open issue whose title contains the phrase, or opens one
# with the title. Search on the phrase, never the full title: issues get retitled
# with a PX.Y prefix, and a search on the bot's own prefix then files a duplicate.
#
# Actions masks secrets only in the run log, never in an issue body a run posts to
# a public repo (#1150), so the body loses the box's names first: HOST (in any case:
# ssh lowercases it), DEPLOY_PATH, DEPLOY_USER beside an `@` and, unless it is the
# public default `root` (a bare `root` is ordinary text), as a bare word too, and
# any tailnet address (100.64.0.0/10, fd7a:115c:a1e0::/48), which ssh can print in
# place of the name.
#
# Each gh call is tried twice, ALERT_RETRY_DELAY_SECONDS (default 10) apart, so one
# API error does not leave a red run as the day's only signal. A create whose first
# attempt landed before failing can file a duplicate; the next run comments on the
# oldest, so that is accepted.
set -euo pipefail
[ $# -eq 2 ] || { echo "usage: file_alert.sh <title> <stable phrase>   (body on stdin)" >&2; exit 2; }
title=$1
search="\"$2\" in:title"

body=$(perl -0777 -pe '
  my ($host, $path, $user) = map { $ENV{$_} // "" } qw(HOST DEPLOY_PATH DEPLOY_USER);
  s/\Q$host\E/<staging host>/gi if length $host;
  s/\Q$path\E/<deploy path>/g if length $path;
  s/\Q$user\E@/<deploy user>@/g if length $user;
  s/(?<![\w.-])\Q$user\E(?![\w-])/<deploy user>/g if length $user && $user ne "root";
  s/(?<![\d.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}(?!\d)/<tailnet address>/g;
  s/fd7a:115c:a1e0(?::[0-9a-f]{0,4})+/<tailnet address>/gi;
')

twice() {
  "$@" || { sleep "${ALERT_RETRY_DELAY_SECONDS:-10}"; "$@"; }
}

# `// empty`: on no match jq would print the string "null".
existing=$(twice gh issue list --state open --search "$search" --json number --jq 'min_by(.number).number // empty')
if [ -n "$existing" ]; then
  twice gh issue comment "$existing" --body "$body"
else
  twice gh issue create --title "$title" --body "$body"
fi
