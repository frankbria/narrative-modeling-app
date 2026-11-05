#!/usr/bin/env bash
# CRAP gate: every function a change adds or modifies (vs main) must score below 6,
# i.e. stay small or be tested. Untouched legacy functions are out of scope.
# Exit 0 pass, 1 offenders listed, 2 a measurement is missing (follow the hint, rerun).
# Config: .claude/quality-gate/crap.json. Runs the newest quality-gate plugin in the
# plugin cache (Node >= 22.5).
set -euo pipefail
gate="$(ls -d "$HOME"/.claude/plugins/cache/eigenwise-toolshed/quality-gate/*/bin/quality-gate.js 2>/dev/null | sort -V | tail -n 1 || true)"
[ -n "$gate" ] || { echo "quality-gate plugin not installed: /plugin install quality-gate@eigenwise-toolshed" >&2; exit 2; }
exec node "$gate" crap "$@"
