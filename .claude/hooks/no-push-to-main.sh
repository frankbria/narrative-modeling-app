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
# DESIGN: on the default branch, ANY git push is refused. There is deliberately no
# analysis of what it pushes.
#
# The first four versions of this hook tried to exempt "a push of some other branch"
# by parsing the refspec, and review found a bypass in every one: a flag before the
# remote shifted the positions (`git push -u origin main`), `;` glued to the command
# hid it from the detector, `${cmd#*push}` cut at the word "push" inside an earlier
# commit message, only the first of several refspecs was inspected, a trailing `)`
# made `main)` not match `main`, and a global option (`git -C x push`) stopped it
# being recognised as a push at all. Each fix was correct and the next round found
# another shape, because a command string is a shell language and this was an ad-hoc
# parser for it. The exemption bought a rare convenience — pushing someone else's
# branch while sitting on main — at the cost of the guarantee the hook exists for.
#
# So it fails closed. A push of another branch from the default branch is refused
# too; the override below clears it in one prefix. Over-refusing costs a keystroke,
# under-refusing costs the thing this was written to prevent.
#
# SCOPE: it reads the command string, so `bash -c "git push"`, xargs, aliases and a
# script that pushes are all out of scope. Backstop for direct invocation, not a
# guarantee.
#
# OVERRIDE — as a token IN THE COMMAND, which is the only thing the hook can see:
#   ALLOW_MAIN_PUSH=1 git push
# (An exported ALLOW_MAIN_PUSH=1 in the hook's own environment works too. The
# command-string form is what the refusal message teaches, and for four versions it
# could not possibly have worked: the assignment applies inside the command's shell,
# which does not exist until after this hook has already decided.)
#
# Exit 2 blocks the call and returns stderr to Claude.
# `--self-check` runs the case table at the bottom; CI runs that.
set -uo pipefail

# Is this ONE shell segment a git push? Tokenised, not pattern-matched: skip any
# leading VAR=val assignments, require `git`, skip git's global options, require
# `push`. A segment that merely mentions the words (`git commit -m "fix git push"`,
# `echo "git push done"`) does not start with them and is not a push.
segment_is_push() {
  local -a w=()
  read -r -a w <<<"$1"
  local i=0
  while [ $i -lt ${#w[@]} ] && [[ "${w[$i]}" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; do
    i=$((i + 1))
  done
  [ $i -lt ${#w[@]} ] && [ "${w[$i]}" = "git" ] || return 1
  i=$((i + 1))
  while [ $i -lt ${#w[@]} ]; do
    case "${w[$i]}" in
      # Global options that consume the next word.
      -C|-c|--git-dir|--work-tree|--namespace|--exec-path) i=$((i + 2));;
      -*) i=$((i + 1));;
      *) break;;
    esac
  done
  [ $i -lt ${#w[@]} ] && [ "${w[$i]}" = "push" ]
}

# Uses $cmd, $branch, $default. Returns 0 to allow, 2 to refuse.
check_command() {
  [ "$branch" = "$default" ] || return 0

  # The override has to be visible in the command text — see OVERRIDE above.
  printf '%s' "$cmd" | grep -qE '(^|[[:space:]])ALLOW_MAIN_PUSH=1([[:space:]]|$)' && return 0
  [ "${ALLOW_MAIN_PUSH:-}" = "1" ] && return 0

  local seg found=1
  while IFS= read -r seg; do
    # Strip the parens a subshell or $( ) capture leaves on the tokens.
    seg="${seg//[()]/ }"
    if segment_is_push "$seg"; then found=0; break; fi
    # `%s\n`, not `%s`: without a trailing newline `read` returns non-zero on the
    # final segment and the loop body never runs for it — which for a plain
    # `git push` (one segment, no operators) skips the only segment there is.
  done < <(printf '%s\n' "$cmd" | sed -E 's/(\|\||&&|[;&|])/\n/g')
  [ "$found" = 0 ] || return 0

  cat >&2 <<EOF
Refused: '$branch' is the default branch, and pushing it directly bypasses the
required "CI Success" check. That has happened three times (#604) — the push
succeeds with only an easily-missed "remote: Bypassed rule violations" line.

Branch first, then open a PR:
    git switch -c <branch> && git push -u origin <branch>

This refuses ANY push from '$branch', including a push of another branch — the
guard deliberately does not try to work out what a command pushes. If you do mean
to push from here, put the override in the command itself:
    ALLOW_MAIN_PUSH=1 git push ...
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
  # Refused: any push at all from the default branch. Each of these was a live
  # bypass in some earlier version of this hook.
  t 2 main "git push"
  t 2 main "git push -q"
  t 2 main "git push origin"
  t 2 main "git push origin main"
  t 2 main "git push -u origin main"                  # flag shifted the positions
  t 2 main "git push --force origin main"
  t 2 main "git push -o ci.skip origin main"
  t 2 main "git push origin HEAD"
  t 2 main "git push origin HEAD:main"
  t 2 main "git push origin refs/heads/main"
  t 2 main "git push origin feat/x main"              # main in a later refspec
  t 2 main "git push origin feat/x"                   # deliberate: no exemption
  t 2 main "git -C /repo push origin main"            # global option before push
  t 2 main "git --no-pager push"
  t 2 main "git -c user.name=x push origin main"
  t 2 main "git add x && git push"
  t 2 main "git push;echo done"                       # separator glued on
  t 2 main "git push&&echo done"
  t 2 main '(cd /repo && git push origin main)'       # parens on the tokens
  t 2 main 'git commit -m "push notification fix" && git push origin main'
  t 2 main "FOO=1 git push"
  t 2 main "cd /repo && git push -u origin main"
  t 2 main 'git push origin feat/x && echo "git push done"' # the first segment is a push
  # Allowed: not the default branch, or not a push.
  t 0 feat/x "git push"
  t 0 feat/x "git push -u origin feat/x"
  t 0 feat/x "git push origin main"                   # scope: only guards the branch you are ON
  t 0 main "git status"
  t 0 main "cat docs/git-push-notes.md"
  t 0 main "echo 'git push' >> notes.md"
  t 0 main 'git commit -m "fix the git push hook"'    # mentions it, does not run it
  t 0 main 'git log --grep="git push"'
  # The override, in the command text — the form the refusal message teaches.
  t 0 main "ALLOW_MAIN_PUSH=1 git push"
  t 0 main "ALLOW_MAIN_PUSH=1 git push origin main"
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
