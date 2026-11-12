#!/usr/bin/env bash
# Build the backend and frontend images for one commit (#831).
#
#   scripts/ci/build_images.sh <revision>                         # build only (the PR gate)
#   scripts/ci/build_images.sh <revision> --push <registry/path>  # build, push, print digests
#
# The one place the images are built: the PR gate and the deploy both call it, and no
# box builds anything. Neither image is given a host name, an API address or an
# environment at build time (the frontend reads those when a request arrives,
# lib/runtimeEnv.ts), so the same digest runs on staging and on production.
#
# Without --push the images are tagged narrative-backend:<revision> and
# narrative-frontend:<revision> in the local daemon. With --push they are tagged
# <registry/path>/backend:<revision> and …/frontend:<revision>, pushed, and the two
# digest references are printed as `backend=…@sha256:…` and `frontend=…@sha256:…`
# on stdout (everything else goes to stderr), ready for $GITHUB_OUTPUT.
#
# Source maps (#1158): with SENTRY_AUTH_TOKEN, SENTRY_ORG and SENTRY_PROJECT in the
# environment the frontend build uploads its maps under release <revision>. The token
# goes in as a build secret, never a build arg.
set -euo pipefail

revision=${1:?usage: build_images.sh <revision> [--push <registry/path>]}
prefix=narrative-
if [ "${2:-}" = "--push" ] && [ $# -eq 3 ]; then
  prefix=$3/
elif [ $# -gt 1 ]; then
  echo "usage: build_images.sh <revision> [--push <registry/path>]" >&2
  exit 2
fi
repo_root=$(cd "$(dirname "$0")/../.." && pwd)

labels=(
  --label "org.opencontainers.image.revision=$revision"
  --label "org.opencontainers.image.source=https://github.com/frankbria/narrative-modeling-app"
)
frontend_args=(
  --build-arg "SENTRY_RELEASE=$revision"
  --build-arg "SENTRY_ORG=${SENTRY_ORG:-}"
  --build-arg "SENTRY_PROJECT=${SENTRY_PROJECT:-}"
)
if [ -n "${SENTRY_AUTH_TOKEN:-}" ]; then
  frontend_args+=(--secret "id=sentry_auth_token,env=SENTRY_AUTH_TOKEN")
fi

backend=${prefix}backend:${revision}
frontend=${prefix}frontend:${revision}
docker build "${labels[@]}" --tag "$backend" "$repo_root/apps/backend" >&2
docker build "${labels[@]}" "${frontend_args[@]}" --tag "$frontend" "$repo_root/apps/frontend" >&2

if [ "${2:-}" = "--push" ]; then
  for image in "$backend" "$frontend"; do
    docker push "$image" >&2
  done
  # The registry's digest for what was just pushed: the reference the boxes pull. An
  # image can carry digests under other names too, so the one for this name is picked.
  pushed_digest() {
    docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$1" | grep -F -m 1 "${1%:*}@sha256:"
  }
  echo "backend=$(pushed_digest "$backend")"
  echo "frontend=$(pushed_digest "$frontend")"
fi
