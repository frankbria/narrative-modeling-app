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
# ssh lowercases it), DEPLOY_PATH (with or without a trailing slash), DEPLOY_USER
# beside an `@` and, unless it is the public default `root` (a bare `root` is
# ordinary text), as a bare word too, and any tailnet address (100.64.0.0/10,
# fd7a:115c:a1e0::/48), which ssh can print in place of the name. The longest value
# goes first: the default path ends in `/staging`, and a HOST of `staging` replaced
# first would leave the rest of the path. A user that is an ordinary word (`deploy`)
# is redacted wherever that word appears; over-redaction is the safe side.
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
  $path =~ s{/+$}{};
  my @names = (
    [length $path, qr/\Q$path\E/, "<deploy path>"],
    [length $user, qr/\Q$user\E(?=@)/, "<deploy user>"],
    [length $user, ($user eq "root" ? qr/(?!)/ : qr/(?<![\w.-])\Q$user\E(?![\w-])/), "<deploy user>"],
    [length $host, qr/\Q$host\E/i, "<staging host>"],
  );
  for my $name (sort { $b->[0] <=> $a->[0] } grep { $_->[0] } @names) {
    s/$name->[1]/$name->[2]/g;
  }
  s/(?<![\d.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}(?!\d)/<tailnet address>/g;
  s/fd7a:115c:a1e0(?::[0-9a-f]{0,4})+/<tailnet address>/gi;
')

# Prints only the successful attempt's output: a search that printed a number and
# then failed must not hand its retry two numbers.
twice() {
  local out
  out=$("$@") || { sleep "${ALERT_RETRY_DELAY_SECONDS:-10}"; out=$("$@") || return 1; }
  printf '%s\n' "$out"
}

# `// empty`: on no match jq would print the string "null".
existing=$(twice gh issue list --state open --search "$search" --json number --jq 'min_by(.number).number // empty')
if [ -n "$existing" ]; then
  twice gh issue comment "$existing" --body "$body"
else
  twice gh issue create --title "$title" --body "$body"
fi
