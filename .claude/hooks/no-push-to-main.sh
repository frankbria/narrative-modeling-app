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
# THIS IS THE EARLY-FEEDBACK LAYER, NOT THE GUARANTEE. `.githooks/pre-push` is the
# guarantee: git hands that hook the refs it is actually about to update, on stdin,
# so there is no command string to parse and nothing to slip past. This one exists
# because it refuses *before* the command runs and can explain why — but it reads
# text, and text is where the bypasses live. Six review rounds on PR #791 found six:
# a flag before the remote, `;` glued to the command, the word "push" inside an
# earlier commit message, a second refspec, a `)` left on a token, and a global
# option between `git` and `push`. A seventh is known and deliberately NOT patched
# here — the segment split is a plain `sed`, so a quoted separator inside an
# argument (`git -c http.extraHeader="X-Custom: a;b" push`) cuts the command in the
# wrong place and hides the push. Chasing it would be round seven of writing a shell
# parser in bash; the pre-push hook catches that case exactly, from any caller.
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
# SCOPE: it reads the command string and requires the literal first word of a
# segment to be `git`, so all of these are out of scope — `bash -c "git push"`,
# xargs, a shell alias or function, a script that pushes, `env git push`,
# `command git push`, `\git push`, and a push inside a command substitution whose
# outer command is something else. Backstop for direct invocation, not a guarantee;
# the recurring failure it exists for is an agent typing an ordinary `git push`.
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
# Returns 0 = a push, 3 = a push carrying its own ALLOW_MAIN_PUSH=1, 1 = not a push.
#
# The override is read from THIS segment's leading assignments, never from a grep
# over the whole command: a blind grep matched the token inside an unrelated quoted
# argument, so `git commit -m "document ALLOW_MAIN_PUSH=1" && git push origin main`
# allowed the push — a fail-open in the one check that exists to be the escape
# hatch, and this repo writes exactly those meta-commit messages.
segment_is_push() {
  local -a w=()
  read -r -a w <<<"$1"
  local i=0 override=1
  while [ $i -lt ${#w[@]} ] && [[ "${w[$i]}" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; do
    [ "${w[$i]}" = "ALLOW_MAIN_PUSH=1" ] && override=0
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
  [ $i -lt ${#w[@]} ] && [ "${w[$i]}" = "push" ] || return 1
  [ "$override" = 0 ] && return 3
  return 0
}

# Uses $cmd, $branch, $default. Returns 0 to allow, 2 to refuse.
check_command() {
  [ "$branch" = "$default" ] || return 0
  [ "${ALLOW_MAIN_PUSH:-}" = "1" ] && return 0

  local seg found=1 rc
  while IFS= read -r seg; do
    # Strip the parens a subshell or $( ) capture leaves on the tokens.
    seg="${seg//[()]/ }"
    segment_is_push "$seg"
    rc=$?
    # 0 = a push with no override of its own: refuse the command.
    # 3 = a push carrying its own override: THIS segment is cleared, keep looking.
    #     Returning 0 here instead would let one overridden push waive every push
    #     after it — `ALLOW_MAIN_PUSH=1 git push origin feat-x && git push origin
    #     main` was allowed, which is the opposite of "read from the segment's own
    #     leading assignments".
    # 1 = not a push.
    [ "$rc" = 0 ] && { found=0; break; }
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
  hook_path=$(cd "$(dirname "$0")" && pwd)/$(basename "$0")
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
  # The override, in the command text — the form the refusal message teaches. It is
  # read from the push segment's OWN leading assignments, so merely naming the token
  # elsewhere (a commit message about this hook — this repo writes those) does not
  # clear a push.
  t 0 main "ALLOW_MAIN_PUSH=1 git push"
  t 0 main "ALLOW_MAIN_PUSH=1 git push origin main"
  t 0 main "git status && ALLOW_MAIN_PUSH=1 git push"
  t 2 main 'git commit -m "document ALLOW_MAIN_PUSH=1 usage" && git push origin main'
  t 2 main 'echo "ALLOW_MAIN_PUSH=1" && git push'
  # An override clears ONLY the segment it is attached to. Both orders, because the
  # first version short-circuited on the overridden segment and never read the rest.
  t 2 main 'ALLOW_MAIN_PUSH=1 git push origin feat/x && git push origin main'
  t 2 main 'git push origin main && ALLOW_MAIN_PUSH=1 git push origin feat/x'
  t 0 main 'ALLOW_MAIN_PUSH=1 git push && ALLOW_MAIN_PUSH=1 git push origin main'

  # The real invocation path: stdin JSON, python3 parse, live branch resolution.
  # The case table above calls check_command directly, so none of that was covered —
  # and its parse failure used to `|| exit 0`, a fail-open in the one spot the script
  # cannot see what it was asked about.
  probe_repo=$(mktemp -d)
  (
    cd "$probe_repo" || exit 1
    git init -q -b main . && git commit -q --allow-empty -m init
  ) >/dev/null 2>&1
  e2e() { # <expected> <label> <stdin>
    local want="$1" label="$2" payload="$3" got
    got=$( cd "$probe_repo" && printf '%s' "$payload" | bash "$hook_path" >/dev/null 2>&1; echo $? )
    if [ "$got" = "$want" ]; then printf '  ok   [e2e] %s\n' "$label"
    else printf '  FAIL [e2e] %s -- want %s got %s\n' "$label" "$want" "$got"; fails=$((fails + 1)); fi
  }
  e2e 2 "git push on main"            '{"tool_input":{"command":"git push"}}'
  e2e 2 "git push -u origin main"     '{"tool_input":{"command":"git push -u origin main"}}'
  e2e 0 "git status"                  '{"tool_input":{"command":"git status"}}'
  e2e 0 "override in the command"     '{"tool_input":{"command":"ALLOW_MAIN_PUSH=1 git push"}}'
  e2e 0 "no push, no git spawn"       '{"tool_input":{"command":"ls -la"}}'
  e2e 2 "unparseable payload w/ push" 'this is not json but it says git push'
  rm -rf "$probe_repo"

  [ "$fails" -eq 0 ] || { echo "self-check FAILED ($fails)"; exit 1; }
  echo "self-check OK"; exit 0
fi

# Real invocation: read the tool call, resolve the branch, decide.
input=$(cat)

# Cheap early-out. This hook is wired on EVERY Bash call, and without this each one
# would pay a python3 spawn plus two git spawns to learn it was not a push. A
# command with no "push" anywhere in it cannot be one.
case "$input" in *push*) ;; *) exit 0;; esac

cmd=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null) || cmd=""
branch=$(git branch --show-current 2>/dev/null) || exit 0
default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
default="${default:-main}"

# Could not read the command (no python3, malformed payload), yet the raw text
# mentions a push and we are on the default branch. There is nothing to analyse, so
# refuse rather than guess: `|| exit 0` here was a fail-open in the one place the
# script cannot see what it is being asked about. Escape with an EXPORTED
# ALLOW_MAIN_PUSH=1, since the in-command form needs the parse that just failed.
if [ -z "$cmd" ]; then
  [ "$branch" = "$default" ] || exit 0
  [ "${ALLOW_MAIN_PUSH:-}" = "1" ] && exit 0
  echo "Refused: cannot read the command to check it, and '$branch' is the default branch." >&2
  echo "Branch first, or export ALLOW_MAIN_PUSH=1 if you know this is safe." >&2
  exit 2
fi

check_command
exit $?
