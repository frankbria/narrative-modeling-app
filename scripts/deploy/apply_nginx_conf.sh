#!/usr/bin/env bash
# Render and install the edge config (#594). Runs ON THE BOX via
# `ssh host "DEPLOY_PATH=… bash -s" < scripts/deploy/apply_nginx_conf.sh` from
# deploy.yml, the same way backend_state.sh does.
#
# Why this exists: nginx-staging.conf was applied by hand (the deploy guide said
# `nano`), so the live file drifted from the repo for two months. Editing the repo
# file shipped nothing, and nothing at runtime said so — #456's P0 could have been
# closed green with staging still dropping every Stripe event.
#
# SAFETY, in the order it matters on a shared VPS:
#   * No NGINX_SERVER_NAME in .env.staging => no-op, exit 0. Nothing is written to
#     /etc until an operator provisions the value, so merging this cannot break the
#     box or its co-tenants.
#   * Rendered output identical to live => no write, no reload.
#   * Otherwise the live file is backed up in place, replaced, and `nginx -t` run.
#     A failed test RESTORES the backup and re-tests before exiting non-zero, so a
#     bad render never survives the step. nginx is only reloaded after a pass.
#   * Only this site's file is touched; other apps on the box are untouched.
#
# Usage (from DEPLOY_PATH, or with DEPLOY_PATH set):
#   apply_nginx_conf.sh              # render, install, test, reload
#   apply_nginx_conf.sh --check      # drift only: diff live vs rendered, exit 1 if they differ
#   apply_nginx_conf.sh --self-check # run this script's own assertions (no root needed)
set -euo pipefail

# The ONLY placeholders substituted. Everything else — $host, $remote_addr,
# $req_id — must survive into the live file verbatim, which is why this is an
# explicit list and not a blanket expansion. A new ${VAR} in the config that is
# missing here reaches nginx literally; test_nginx_template.py catches that.
SUBST_VARS=(NGINX_SERVER_NAME NGINX_CERT_DIR)

# Read one variable out of an env file without sourcing it: .env.staging is full of
# secrets with shell-significant characters, and sourcing it would execute them.
# Last assignment wins (that is what a later duplicate line means), quotes stripped.
env_get() {
  local var="$1" file="$2" value
  [ -f "$file" ] || return 0
  value=$(sed -n "s/^[[:space:]]*${var}=//p" "$file" | tail -n 1)
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  printf '%s' "$value"
}

render() {
  local text
  text=$(cat "$SRC")
  local var
  for var in "${SUBST_VARS[@]}"; do
    # Values are a hostname and a filesystem path, so `|` is a safe delimiter.
    text=$(printf '%s' "$text" | sed "s|\${${var}}|${!var}|g")
  done
  printf '%s\n' "$text"
}

main() {
  local mode="${1:-apply}"
  # Resolved per call, not at load time, so the self-check can point them at a
  # temp directory after this file has been sourced/read.
  local SRC="${NGINX_CONF_SRC:-nginx-staging.conf}"
  local TARGET="${NGINX_TARGET:-/etc/nginx/sites-available/narrative-staging.conf}"
  local env_file="${NGINX_ENV_FILE:-.env.staging}"
  local test_cmd="${NGINX_TEST_CMD:-nginx -t}"
  local reload_cmd="${NGINX_RELOAD_CMD:-systemctl reload nginx}"
  cd "${DEPLOY_PATH:-.}"
  [ -f "$SRC" ] || { echo "apply_nginx_conf: $SRC not found (cwd $PWD)" >&2; exit 2; }

  local NGINX_SERVER_NAME="${NGINX_SERVER_NAME:-$(env_get NGINX_SERVER_NAME "$env_file")}"
  if [ -z "$NGINX_SERVER_NAME" ]; then
    echo "::warning::NGINX_SERVER_NAME is not set in $env_file — edge config NOT applied."
    echo "The live nginx file stays as it is. Set NGINX_SERVER_NAME (and optionally"
    echo "NGINX_CERT_DIR) in $env_file to let deploys ship the edge config. See #594."
    return 0
  fi
  local NGINX_CERT_DIR="${NGINX_CERT_DIR:-$(env_get NGINX_CERT_DIR "$env_file")}"
  NGINX_CERT_DIR="${NGINX_CERT_DIR:-/etc/letsencrypt/live/$NGINX_SERVER_NAME}"

  local rendered; rendered=$(mktemp)
  # shellcheck disable=SC2064
  trap "rm -f '$rendered'" RETURN
  render > "$rendered"

  if [ -f "$TARGET" ] && cmp -s "$rendered" "$TARGET"; then
    echo "apply_nginx_conf: $TARGET already matches the repo config — no change."
    return 0
  fi

  if [ "$mode" = "check" ]; then
    echo "apply_nginx_conf: DRIFT — $TARGET differs from the rendered repo config:"
    diff -u "$TARGET" "$rendered" || true
    return 1
  fi

  local backup=""
  if [ -f "$TARGET" ]; then
    backup="$TARGET.bak-$(date -u +%Y%m%dT%H%M%SZ)"
    cp -p "$TARGET" "$backup"
    echo "apply_nginx_conf: live config backed up to $backup"
    diff -u "$backup" "$rendered" || true
  fi

  install -m 0644 "$rendered" "$TARGET"
  if ! $test_cmd; then
    if [ -n "$backup" ]; then
      cp -p "$backup" "$TARGET"
      echo "apply_nginx_conf: nginx -t FAILED — restored $backup" >&2
      $test_cmd || echo "apply_nginx_conf: nginx -t still fails after restore; the box was already broken" >&2
    else
      rm -f "$TARGET"
      echo "apply_nginx_conf: nginx -t FAILED — removed the newly written $TARGET" >&2
    fi
    return 1
  fi

  # Enable the site if it never was. Derived from TARGET so the self-check's temp
  # dir simply has no sites-enabled and this is skipped.
  local enabled_dir="${TARGET%/sites-available/*}/sites-enabled"
  if [ -d "$enabled_dir" ] && [ ! -e "$enabled_dir/$(basename "$TARGET")" ]; then
    ln -s "$TARGET" "$enabled_dir/$(basename "$TARGET")"
    echo "apply_nginx_conf: symlinked into $enabled_dir"
    $test_cmd
  fi

  $reload_cmd
  echo "apply_nginx_conf: applied and reloaded ($NGINX_SERVER_NAME)"
}

self_check() {
  tmp=$(mktemp -d)
  # Expanded NOW on purpose (shellcheck disable=SC2064): the EXIT trap fires after
  # this function's scope is gone, so a deferred $tmp would be unbound under `set -u`.
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" EXIT
  local fails=0
  check() { if [ "$2" = "$3" ]; then echo "  ok: $1"; else echo "  FAIL: $1"; echo "    want: $3"; echo "    got:  $2"; fails=$((fails + 1)); fi; }

  # shellcheck disable=SC2016  # the placeholders must stay literal — that is the point
  printf 'server_name ${NGINX_SERVER_NAME};\nssl_certificate ${NGINX_CERT_DIR}/fullchain.pem;\nproxy_set_header X-Real-IP $remote_addr;\n' > "$tmp/src.conf"
  printf 'NGINX_SERVER_NAME=ignored\nNGINX_SERVER_NAME="example.test"\nOTHER=x\n' > "$tmp/env"

  export NGINX_CONF_SRC="$tmp/src.conf" NGINX_ENV_FILE="$tmp/env" \
         NGINX_TARGET="$tmp/live.conf" NGINX_TEST_CMD=true NGINX_RELOAD_CMD=true
  unset NGINX_SERVER_NAME NGINX_CERT_DIR DEPLOY_PATH || true

  # Last assignment wins and quotes are stripped.
  check "env_get reads the last unquoted value" "$(env_get NGINX_SERVER_NAME "$tmp/env")" "example.test"

  # A full apply: placeholders substituted, nginx's own $variables untouched, and
  # NGINX_CERT_DIR defaulted from the hostname.
  main >/dev/null
  check "server_name rendered" "$(sed -n 1p "$tmp/live.conf")" "server_name example.test;"
  check "cert dir defaulted" "$(sed -n 2p "$tmp/live.conf")" "ssl_certificate /etc/letsencrypt/live/example.test/fullchain.pem;"
  check "nginx variables survive" "$(sed -n 3p "$tmp/live.conf")" "proxy_set_header X-Real-IP \$remote_addr;"

  # Re-running is a no-op, and --check agrees there is no drift.
  check "second run is a no-op" "$(main | tail -n 1)" "apply_nginx_conf: $tmp/live.conf already matches the repo config — no change."
  if main check >/dev/null; then check "--check passes when in sync" "in sync" "in sync"; else check "--check passes when in sync" "drift" "in sync"; fi

  # Drift is detected and reported non-zero.
  printf 'hand edited\n' > "$tmp/live.conf"
  if main check >/dev/null 2>&1; then check "--check fails on drift" "exit 0" "exit 1"; else check "--check fails on drift" "exit 1" "exit 1"; fi

  # The rollback path: a failing `nginx -t` must restore the live file, not leave
  # the new one in place. This is the only branch that can take the box down.
  NGINX_TEST_CMD=false main >/dev/null 2>&1 || true
  check "failed nginx -t restores the backup" "$(cat "$tmp/live.conf")" "hand edited"
  if ls "$tmp"/live.conf.bak-* >/dev/null 2>&1; then check "a backup was kept" "kept" "kept"; else check "a backup was kept" "missing" "kept"; fi

  # No hostname configured => the live file is left exactly as it is, exit 0. The
  # stubbed `nginx -t` passes here on purpose: an apply that wrongly proceeded
  # would succeed and overwrite, so this fails if the guard is removed.
  printf 'pre-existing\n' > "$tmp/live.conf"
  printf 'OTHER=x\n' > "$tmp/env"
  main >/dev/null
  check "unset hostname leaves the live file alone" "$(cat "$tmp/live.conf")" "pre-existing"

  [ "$fails" -eq 0 ] || { echo "self-check FAILED ($fails)"; exit 1; }
  echo "self-check OK"
}

case "${1:-}" in
  --self-check) self_check ;;
  --check)      main check ;;
  "")           main apply ;;
  *)            echo "usage: $0 [--check|--self-check]" >&2; exit 2 ;;
esac
