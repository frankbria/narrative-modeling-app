#!/usr/bin/env bash
# CRAP gate: every function a change adds or modifies (vs main) must score below 6,
# i.e. stay small or be tested. Untouched legacy functions are out of scope.
# Exit 0 pass, 1 offenders listed, 2 a measurement is missing (follow the hint, rerun).
# Config: .claude/quartermaster/crap.json. Needs lizard (`uv tool install lizard`) and
# the quartermaster plugin, whose newest installed version this resolves.
set -euo pipefail
q="$(ls -d "$HOME"/.claude/plugins/cache/eigenwise-toolshed/quartermaster/*/ 2>/dev/null | sort -V | tail -1)"
[ -n "$q" ] || { echo "quartermaster plugin not installed" >&2; exit 2; }
exec node "${q}bin/quartermaster.js" crap "$@"
