#!/usr/bin/env bash
# CRAP gate: every function a change adds or modifies (vs main) must score below 6,
# i.e. stay small or be tested. Untouched legacy functions are out of scope.
# Exit 0 pass, 1 offenders listed, 2 a measurement is missing (follow the hint, rerun).
# Config: .claude/quartermaster/crap.json. Needs lizard (`uv tool install lizard`) and
# the quartermaster plugin, whose newest installed version that still scores CRAP this
# resolves (0.12.2 retired it in favour of the quality-gate plugin).
# shortcut: needs a pre-0.12.2 quartermaster in the plugin cache; move to quality-gate when the cache is pruned.
set -euo pipefail
q=""
for d in $(ls -d "$HOME"/.claude/plugins/cache/eigenwise-toolshed/quartermaster/*/ 2>/dev/null | sort -rV); do
  grep -qs "crap is retired" "${d}lib/quality-gate.js" || { q="$d"; break; }
done
[ -n "$q" ] || { echo "no installed quartermaster version still scores CRAP" >&2; exit 2; }
exec node "${q}bin/quartermaster.js" crap "$@"
