#!/usr/bin/env bash
# Coverage for the CRAP gate (.claude/quartermaster/crap.json): one LCOV file at
# $QUARTERMASTER_COVERAGE_DIR/lcov.info with repo-root paths, because the gate
# resolves every SF: line from the repo root while pytest-cov and jest write them
# relative to their own app. Only the apps the change touches (vs main) are run:
# the backend gate suite takes minutes and a frontend-only change has no use for it.
# Backend needs MongoDB on :27017, same as the PR gate.
set -euo pipefail

out="${QUARTERMASTER_COVERAGE_DIR:?run this through: quartermaster crap}/lcov.info"
root="$(git rev-parse --show-toplevel)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
# The merge-base, so apps that changed only upstream on main are not run.
changed="$(git -C "$root" diff --name-only "$(git -C "$root" merge-base main HEAD)")"
: > "$out"

if grep -q '^apps/backend/' <<<"$changed"; then
  (cd "$root/apps/backend" && PYTHONPATH=. uv run pytest tests/ \
    -m "not integration and not performance" -q -p no:cacheprovider \
    --cov=app --cov-report="lcov:$tmp/backend.info" >"$tmp/backend.log" 2>&1) \
    || { cat "$tmp/backend.log" >&2; exit 1; }
  sed 's|^SF:|SF:apps/backend/|' "$tmp/backend.info" >> "$out"
fi

if grep -q '^apps/frontend/' <<<"$changed"; then
  (cd "$root/apps/frontend" && npx jest --coverage --coverageReporters=lcov \
    --coverageDirectory="$tmp/frontend" >"$tmp/frontend.log" 2>&1) \
    || { cat "$tmp/frontend.log" >&2; exit 1; }
  sed 's|^SF:|SF:apps/frontend/|' "$tmp/frontend/lcov.info" >> "$out"
fi
