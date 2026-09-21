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
# SCOPE: this is a backstop for direct invocations, not a hard guarantee. It reads
# the command string, so it cannot see through `bash -c "git push"`, xargs, a shell
# alias, or a script that pushes. Those are not the failure mode it exists for —
# the observed one is an agent typing an ordinary `git push` while on main.
#
# Deliberate override, for the case where pushing main really is the intent:
#   ALLOW_MAIN_PUSH=1 git push
#
# Exit 2 blocks the call and returns stderr to Claude.
# `--self-check` runs the case table at the bottom; wire it into CI, not into faith.
set -uo pipefail

# Does this command push the DEFAULT branch? Uses $cmd and $default.
#
# A token parse, not a positional regex. "the ref is the second word after push" is
# only true for `git push origin main`; one flag shifts every position, so the first
# version of this hook read `origin` as the ref in `git push -u origin main` — the
# most ordinary way to push a first commit, and exactly what it exists to catch —
# and allowed it through. Flags are dropped first, then positionals are counted.
pushes_default() {
  # This push's arguments end at the first shell operator, and the operator does not
  # need a space in front of it: in `git push;echo done` the first token is `;echo`,
  # which is neither a flag nor a separator by itself, so it was counted as the
  # remote and `done` became the refspec. Cut the string first, then tokenize.
  local args="${cmd#*push}"
  args="${args%%;*}"
  args="${args%%&*}"
  args="${args%%|*}"

  local -a words positional=()
  read -r -a words <<<"$args"
  local i=0 w
  while [ $i -lt ${#words[@]} ]; do
    w="${words[$i]}"
    case "$w" in
      # Flags that consume the NEXT word as their value.
      -o|--push-option|--repo|--exec|--receive-pack) i=$((i + 2)); continue;;
      # Anything else dash-prefixed is a standalone flag.
      -*) i=$((i + 1)); continue;;
    esac
    positional+=("$w")
    i=$((i + 1))
  done
  # Fewer than 2 positionals means no refspec: `git push` and `git push origin` push
  # the CURRENT branch, which on this path is the default branch.
  [ "${#positional[@]}" -lt 2 ] && return 0
  # With a refspec, the DESTINATION is what lands — `src:dst` pushes to dst.
  local ref="${positional[1]}"
  ref="${ref##*:}"
  ref="${ref#refs/heads/}"
  [ "$ref" = "$default" ] || [ "$ref" = "HEAD" ]
}

# Uses $cmd, $branch, $default. Returns 0 to allow, 2 to refuse.
check_command() {
  # Not a push at all (and not a push hidden behind && or ;) — nothing to say.
  # Both boundaries accept a separator OR whitespace OR the string edge: `git push;x`
  # and `git push&&x` are pushes too, and requiring whitespace *after* `push` let
  # both through the first gate entirely.
  printf '%s' "$cmd" | grep -qE '(^|[;&|(]|[[:space:]])git[[:space:]]+push([;&|)[:space:]]|$)' || return 0

  [ "${ALLOW_MAIN_PUSH:-}" = "1" ] && return 0
  [ "$branch" = "$default" ] || return 0
  pushes_default || return 0

  cat >&2 <<EOF
Refused: this would push '$branch', the default branch, bypassing the required
"CI Success" check. That has happened three times already (#604) — the push
succeeds with only an easily-missed "remote: Bypassed rule violations" line.

Branch first, then open a PR:
    git switch -c <branch> && git push -u origin <branch>

If pushing '$branch' directly is genuinely what you want, say so explicitly and
re-run it as:  ALLOW_MAIN_PUSH=1 git push ...
EOF
  return 2
}

if [ "${1:-}" = "--self-check" ]; then
  fails=0
  t() { # <expected 0|2> <branch> <command>
    local want="$1" br="$2" c="$3" got
    ( cmd="$c"; branch="$br"; default=main; unset ALLOW_MAIN_PUSH; check_command ) >/dev/null 2>&1
    got=$?
    if [ "$got" = "$want" ]; then
      printf '  ok   [%s] %s\n' "$br" "$c"
    else
      printf '  FAIL [%s] %s -- want %s got %s\n' "$br" "$c" "$want" "$got"; fails=$((fails + 1))
    fi
  }
  # Refused: every shape that updates the default branch from the default branch.
  t 2 main "git push"
  t 2 main "git push -q"
  t 2 main "git push origin"
  t 2 main "git push origin main"
  t 2 main "git push -u origin main"          # the bypass a PR review caught
  t 2 main "git push --force origin main"
  t 2 main "git push -o ci.skip origin main"  # flag that eats the next word
  t 2 main "git push origin HEAD"
  t 2 main "git push origin HEAD:main"        # src:dst — dst is what lands
  t 2 main "git push origin refs/heads/main"
  t 2 main "git add x && git push"
  t 2 main "git push;echo done"               # no space before the separator
  t 2 main "git push&&echo done"
  # Allowed: a different branch, or not a push at all.
  t 0 main "git push origin feat/x"
  t 0 main "git push -u origin feat/x"
  t 0 main "git push origin HEAD:feat/x"
  t 0 feat/x "git push"
  t 0 feat/x "git push -u origin feat/x"
  t 0 main "git status"
  t 0 main "cat docs/git-push-notes.md"
  t 0 main "echo 'git push' >> notes.md"      # a quote before git guards it
  # The override, checked separately since t() clears it.
  ( cmd="git push"; branch=main; default=main; ALLOW_MAIN_PUSH=1; check_command ) >/dev/null 2>&1
  if [ $? = 0 ]; then printf '  ok   [main] ALLOW_MAIN_PUSH=1 git push\n'
  else printf '  FAIL [main] ALLOW_MAIN_PUSH=1 git push -- want 0\n'; fails=$((fails + 1)); fi
  [ "$fails" -eq 0 ] || { echo "self-check FAILED ($fails)"; exit 1; }
  echo "self-check OK"; exit 0
fi

# Real invocation: read the tool call, resolve the branch, decide.
input=$(cat)
cmd=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null) || exit 0
branch=$(git branch --show-current 2>/dev/null) || exit 0
default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
default="${default:-main}"
check_command
exit $?
