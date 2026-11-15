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
# fd7a:115c:a1e0::/48, a `*.ts.net` MagicDNS name), which ssh can print in place
# of the name. Every name is matched against the original text and overlapping
# matches are replaced as one span: the default path ends in `/staging`, and a
# HOST of `staging` replaced first would leave the rest of the path. A user that is
# an ordinary word (`deploy`) is redacted wherever that word appears;
# over-redaction is the safe side.
#
# shortcut: only the names above are redacted. A custom MagicDNS domain (not
# `*.ts.net`) and any other host name or address the stderr prints go public as
# printed. ssh names the host it was given (HOST, redacted), so this holds while
# HOST is the bare machine name; redact more (every host name in the stderr block)
# if a step ever connects through a name the box's secrets do not hold (#1231).
#
# The body goes to gh as a file, not an argument (Linux refuses one over 128 KiB),
# cut to fit GitHub's 65,536-character limit with a line saying how much was cut;
# a cut body is printed whole, redacted, to the run log first (#1241).
#
# Each gh call is tried twice, ALERT_RETRY_DELAY_SECONDS (default 60) apart, so one
# API error does not leave a red run as the day's only signal; a minute because
# GitHub asks for at least that after a secondary rate limit. A create whose first
# attempt landed before failing can file a duplicate; the next run comments on the
# oldest, so that is accepted. The callers' report budget counts on this: two gh
# calls, each able to wait once (REPORT_MINUTES = 3 in test_staging_health_wiring.py).
# A third call needs a bigger number there and longer job limits in both workflows.
set -euo pipefail
[ $# -eq 2 ] || { echo "usage: file_alert.sh <title> <stable phrase>   (body on stdin)" >&2; exit 2; }
title=$1
search="\"$2\" in:title"
body_file=$(mktemp)
trap 'rm -f "$body_file"' EXIT

# Decoded so the limit and the cut count characters, as GitHub does; leniently
# (a bad byte becomes U+FFFD), because ssh stderr can hold anything and -CS would
# die on it in the first match, losing the alert.
perl -MEncode -0777 -pe '
  $_ = Encode::decode("UTF-8", $_);
  # Decoded like the body, or a name with a non-ASCII character would never match.
  my ($host, $path, $user) = map { Encode::decode("UTF-8", $ENV{$_} // "") } qw(HOST DEPLOY_PATH DEPLOY_USER);
  $path =~ s{/+$}{};
  my @names;
  push @names, [qr/\Q$path\E/, "<deploy path>"] if length $path;
  push @names, [qr/\Q$user\E(?=@)/, "<deploy user>"] if length $user;
  push @names, [qr/(?<![\w.-])\Q$user\E(?![\w-])/, "<deploy user>"] if length $user && $user ne "root";
  push @names, [qr/\Q$host\E/i, "<staging host>"] if length $host;
  # After the values of the box: on a tie the first placeholder stays.
  push @names,
    [qr/(?<![\d.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])(?:\.\d{1,3}){2}(?!\d)/, "<tailnet address>"],
    # A colon is taken only before a hex group, so the colon ssh prints after an
    # address stays; only a final `::` is. Every hex letter after a colon is taken,
    # even one starting a word (`::3:Cannot` loses `Ca`): the groups at the end are
    # the ones that name the node. An embedded IPv4 tail (`…:7:10.0.0.1`) goes too.
    [qr/fd7a:115c:a1e0(?::{1,2}[0-9a-f]+)*(?:\.\d{1,3})*(?:::(?![\w:]))?/i, "<tailnet address>"],
    # A MagicDNS name (`box.tailXXXX.ts.net`) names the tailnet too; merged with
    # the HOST match it overlaps, it is replaced whole.
    [qr/[\w-]+(?:\.[\w-]+)*\.ts\.net\b/i, "<tailnet address>"],
  ;
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
  # What closes every block a cut leaves open. A cut inside a code fence would
  # render the notice as code, and one inside the collapsed <details> both callers
  # end with would hide it. Fences per CommonMark: backticks or tildes; a closing
  # one is the same character, at least as long, with no info string, and a
  # backtick opener has no backtick in its info string. A tag inside a fence is text.
  sub closing_markup {
    my ($open, $details) = ("", 0);
    for my $line (split /\n/, $_[0]) {
      if (length $open) {
        $open = "" if $line =~ /^ {0,3}(`{3,}|~{3,})[ \t\r]*$/
          && substr($1, 0, 1) eq substr($open, 0, 1) && length $1 >= length $open;
      }
      elsif ($line =~ /^ {0,3}(`{3,}(?=[^`]*$)|~{3,})/) { $open = $1 }
      else { $details += (() = $line =~ /<details\b/gi) - (() = $line =~ m{</details>}gi) }
    }
    return (length $open ? "\n$open" : "") . "\n</details>" x $details;
  }
  # Cut after redacting, so a name is never split into a part the pattern misses.
  # 65,000 leaves room for the line below inside the 65,536 limit.
  if (length > 65536) {
    # The notice sends the reader here, and the callers print their stderr tail
    # nowhere else; redacted, because the log is public and masks only secrets.
    # Between stop-commands markers, so a box line reading `::error::` stays text.
    my $token = join "", map { sprintf "%04x", int rand 65536 } 1 .. 8;
    print STDERR "file_alert.sh: the body was cut for the issue; the whole body, redacted:\n",
      "::stop-commands::$token\n", Encode::encode("UTF-8", $_), "\n::${token}::\n";
    my $kept = substr($_, 0, 65000);
    my $notice = sub {
      my $cut = length($_) - length $_[0];
      "\n\n($cut characters were cut: an issue body holds at most 65,536. The run log has the whole body.)\n";
    };
    my $closing = closing_markup($kept);
    if (length($kept . $closing . $notice->($kept)) > 65536) {
      my $room = 65536 - length($closing) - length($notice->($kept)) - 1;
      $kept = substr($kept, 0, $room < 0 ? 0 : $room);
      $closing = closing_markup($kept);
      # The alert has to arrive: a body over the limit is refused whole, so one the
      # shorter cut still cannot close goes unclosed.
      $closing = "" if length($kept . $closing . $notice->($kept)) > 65536;
    }
    $_ = $kept . $closing . $notice->($kept);
  }
  $_ = Encode::encode("UTF-8", $_);
' > "$body_file"

# Prints only the successful attempt's output: a search that printed a number and
# then failed must not hand its retry two numbers.
twice() {
  local out
  out=$("$@") || { sleep "${ALERT_RETRY_DELAY_SECONDS:-60}"; out=$("$@") || return 1; }
  printf '%s\n' "$out"
}

# `// empty`: on no match jq would print the string "null".
existing=$(twice gh issue list --state open --search "$search" --json number --jq 'min_by(.number).number // empty')
if [ -n "$existing" ]; then
  twice gh issue comment "$existing" --body-file "$body_file"
else
  twice gh issue create --title "$title" --body-file "$body_file"
fi
