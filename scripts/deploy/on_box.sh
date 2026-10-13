#!/usr/bin/env bash
# Run a script on the staging box, with DEPLOY_PATH in its environment (#790).
# The one way deploy.yml and staging-health.yml reach the box:
#
#   scripts/deploy/on_box.sh scripts/deploy/backend_state.sh    # a repo script
#   scripts/deploy/on_box.sh <<'REMOTE'                         # an inline body
#   cd "$DEPLOY_PATH" && docker compose ps
#   REMOTE
#
# Needs HOST, DEPLOY_USER and DEPLOY_PATH in the environment, and the key the
# workflow's "Configure SSH" step writes.
#
# Two things it exists to get right, both of which were wrong in every step that
# wrote its own ssh line:
#
# 1. The value never sits between quotes in the command string. ssh hands the far
#    shell ONE string to parse, so `ssh host "cd '$DEPLOY_PATH'"` let a quote in the
#    value end the quoting and the rest run as shell. `printf %q` writes the value as
#    one shell word whatever it holds; the body reads "$DEPLOY_PATH" from its
#    environment. Keep an inline body's heredoc QUOTED (<<'REMOTE'), or the runner's
#    shell expands it first and the value is back in the text.
#
# 2. The body cannot be eaten by its own commands. Fed to `bash -s`, a command that
#    reads stdin (docker compose exec, ssh, cat) swallows the rest of the script and
#    the run ends there with exit 0 (#756). The far side saves the body to a file
#    first and runs it with stdin at /dev/null.
set -euo pipefail
[ $# -le 1 ] || { echo "usage: on_box.sh [script]   (or a body on stdin)" >&2; exit 2; }
: "${HOST:?HOST is not set}" "${DEPLOY_USER:?DEPLOY_USER is not set}" "${DEPLOY_PATH:?DEPLOY_PATH is not set}"

# %q writes bash quoting, and the far login shell is bash. If that ever changes, a value
# with control characters is the case to recheck (%q would write it as $'…').
#
# Single-quoted on purpose: this text is for the far shell, nothing in it is ours.
# shellcheck disable=SC2016
run_saved_body='body=$(mktemp) && cat > "$body" && bash "$body" </dev/null; status=$?; rm -f "$body"; exit $status'
remote="DEPLOY_PATH=$(printf '%q' "$DEPLOY_PATH") bash -c $(printf '%q' "$run_saved_body")"

if [ $# -gt 0 ]; then
  exec ssh -i ~/.ssh/staging_key -o BatchMode=yes "$DEPLOY_USER@$HOST" "$remote" < "$1"
fi
exec ssh -i ~/.ssh/staging_key -o BatchMode=yes "$DEPLOY_USER@$HOST" "$remote"
