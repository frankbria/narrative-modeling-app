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
# fd7a:115c:a1e0::/48), which ssh can print in place of the name. Every name is
# matched against the original text and overlapping matches are replaced as one
# span: the default path ends in `/staging`, and a HOST of `staging` replaced first
# would leave the rest of the path. A user that is an ordinary word (`deploy`)
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
    [qr/(?<![\d.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}(?!\d)/, "<tailnet address>"],
    [qr/fd7a:115c:a1e0(?::[0-9a-f]{0,4})+/i, "<tailnet address>"],
  );
  push @names, [qr/\Q$path\E/, "<deploy path>"] if length $path;
  push @names, [qr/\Q$user\E(?=@)/, "<deploy user>"] if length $user;
  push @names, [qr/(?<![\w.-])\Q$user\E(?![\w-])/, "<deploy user>"] if length $user && $user ne "root";
  push @names, [qr/\Q$host\E/i, "<staging host>"] if length $host;
  # Every match is found in the ORIGINAL text, and overlapping matches become one
  # span: replacing one name first can break the match of another that overlaps it.
  my @spans;
  for my $name (@names) {
    # Resumed one character after each match starts, so a value that overlaps
    # itself (`node-node` in `node-node-node`) is found at every position.
    while (/$name->[0]/g) { push @spans, [$-[0], $+[0], $name->[1]]; pos($_) = $-[0] + 1 }
  }
  my @merged;
  for my $span (sort { $a->[0] <=> $b->[0] || $b->[1] <=> $a->[1] } @spans) {
    if (@merged && $span->[0] < $merged[-1][1]) {
      $merged[-1][1] = $span->[1] if $span->[1] > $merged[-1][1];
    } else {
      push @merged, [@$span];
    }
  }
  for my $span (reverse @merged) { substr($_, $span->[0], $span->[1] - $span->[0]) = $span->[2] }
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
