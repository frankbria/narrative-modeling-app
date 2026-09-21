#!/usr/bin/env bash
# PreToolUse(Bash): refuse `git push` from the default branch.
#
# Why this is a hook and not a rule: the global instructions already say "if on the
# default branch, branch first", and main has "CI Success" as a required check —
# and it has still been bypassed three times (#604), because `enforce_admins` is
# false, the only signal is a `remote: Bypassed rule violations` line that scrolls
# past in the push output, and nothing afterwards distinguishes a bypassed commit
# from one that passed. For docs commits under tasks/ it had become the habit.
#
# A prose rule can be forgotten mid-session. This cannot.
#
# Deliberate override, for the case where pushing main really is the intent:
#   ALLOW_MAIN_PUSH=1 git push
#
# Exit 2 blocks the call and returns stderr to Claude.
set -uo pipefail

input=$(cat)
cmd=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null) || exit 0

# Not a push at all (and not a push hidden behind && or ;) — nothing to say.
printf '%s' "$cmd" | grep -qE '(^|[;&|]|[[:space:]])git[[:space:]]+push([[:space:]]|$)' || exit 0

[ "${ALLOW_MAIN_PUSH:-}" = "1" ] && exit 0

branch=$(git branch --show-current 2>/dev/null) || exit 0
default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
default="${default:-main}"
[ "$branch" = "$default" ] || exit 0

# On the default branch, but the command names some other ref explicitly
# (`git push origin feat/x`) — that is a legitimate push of a branch you are not on.
if printf '%s' "$cmd" | grep -qE "git[[:space:]]+push[[:space:]]+\S+[[:space:]]+\S+" &&
   ! printf '%s' "$cmd" | grep -qE "git[[:space:]]+push[[:space:]]+\S+[[:space:]]+(HEAD|$default)([[:space:]]|:|$)"; then
  exit 0
fi

cat >&2 <<EOF
Refused: this would push '$branch', the default branch, bypassing the required
"CI Success" check. That has happened three times already (#604) — the push
succeeds with only an easily-missed "remote: Bypassed rule violations" line.

Branch first, then open a PR:
    git switch -c <branch> && git push -u origin <branch>

If pushing '$branch' directly is genuinely what you want, say so explicitly and
re-run it as:  ALLOW_MAIN_PUSH=1 git push ...
EOF
exit 2
