#!/usr/bin/env bash
# Install this repo's tracked git hooks. Idempotent — safe to re-run.
#
# Only `.githooks/pre-push` is tracked (it refuses a push that updates the default
# branch; see its header). It is SYMLINKED into .git/hooks rather than installed by
# pointing `core.hooksPath` at .githooks, because this repo's core.hooksPath is
# already .git/hooks and that directory holds an untracked secret-scanning
# pre-commit hook. Repointing it would silently disable that.
#
# Run once per clone:
#   ./scripts/install-git-hooks.sh
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

hooks_dir=$(git rev-parse --git-path hooks)
mkdir -p "$hooks_dir"

installed=0
for src in .githooks/*; do
  [ -f "$src" ] || continue
  name=$(basename "$src")
  target="$hooks_dir/$name"

  # An existing REAL file is someone's own hook — never clobber it.
  if [ -f "$target" ] && [ ! -L "$target" ]; then
    echo "skip   $name: $target already exists and is not a symlink; move it aside first" >&2
    continue
  fi

  ln -sfn "$repo_root/$src" "$target"
  chmod +x "$src"
  echo "ok     $name -> $src"
  installed=$((installed + 1))
done

echo
echo "$installed hook(s) installed into $hooks_dir"
echo "Verify: .githooks/pre-push --self-check"
