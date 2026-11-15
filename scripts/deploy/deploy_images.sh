#!/usr/bin/env bash
# Put one commit's images on this box (#831). Runs ON THE BOX, sent by deploy.yml:
#
#   ON_BOX_FORWARD="APP_VERSION BACKEND_IMAGE FRONTEND_IMAGE REGISTRY_USER REGISTRY_TOKEN" \
#     scripts/deploy/on_box.sh scripts/deploy/deploy_images.sh
#
# Nothing is built here. CI built both images once and pushed them; BACKEND_IMAGE and
# FRONTEND_IMAGE name them by digest (registry/name@sha256:…), so this box runs
# exactly the bytes CI produced, and the production box can run the same ones.
#
# The registry token is the deploy job's own short-lived one. It is used for the pull
# from a throwaway docker config, so the box holds no standing registry credential.
set -euo pipefail
: "${DEPLOY_PATH:?DEPLOY_PATH is not set}" "${APP_VERSION:?APP_VERSION is not set}"
: "${BACKEND_IMAGE:?BACKEND_IMAGE is not set}" "${FRONTEND_IMAGE:?FRONTEND_IMAGE is not set}"

for image in "$BACKEND_IMAGE" "$FRONTEND_IMAGE"; do
  case "$image" in
    *@sha256:*) ;;
    *) echo "deploy: $image is not a digest reference; refusing to deploy a tag that can move" >&2; exit 2 ;;
  esac
done
export APP_VERSION BACKEND_IMAGE FRONTEND_IMAGE

cd "$DEPLOY_PATH"
# compose.sh refuses a box with neither env file or both; asked here, before anything runs.
env_files=()
for candidate in .env.staging .env.production; do
  if [ -f "$candidate" ]; then env_files+=("$candidate"); fi
done
if [ "${#env_files[@]}" -ne 1 ]; then
  echo "deploy: expected exactly one of .env.staging or .env.production in the deploy directory, found ${#env_files[@]}" >&2
  exit 2
fi
env_file=${env_files[0]}

# Pulled first, before anything on the box changes: a pull that fails (a token, the
# registry) leaves the checkout, the containers and the record exactly as they were.
# It uses a docker config of its own, removed again whatever happens: the token
# never joins the box's stored credentials, and a login another app on a shared box
# keeps for the same registry is left alone.
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
registry_config=$work/registry
mkdir "$registry_config"
if [ -n "${REGISTRY_TOKEN:-}" ]; then
  printf '%s' "$REGISTRY_TOKEN" \
    | docker --config "$registry_config" login "${BACKEND_IMAGE%%/*}" --username "${REGISTRY_USER:-deploy}" --password-stdin >/dev/null
fi
for image in "$BACKEND_IMAGE" "$FRONTEND_IMAGE"; do
  docker --config "$registry_config" pull --quiet "$image"
done
rm -rf "$registry_config"

# The deployed commit's preflight and compose file, read from git before the checkout
# moves: a box missing a setting that commit requires is refused with the checkout,
# the containers and the record as they were. The FULL list of missing required vars,
# instead of compose aborting on the first ${VAR:?} it interpolates.
git fetch --prune origin
git show "$APP_VERSION:docker-compose.deploy.yml" > "$work/docker-compose.deploy.yml"
git show "$APP_VERSION:scripts/deploy/preflight_staging_env.sh" > "$work/preflight_staging_env.sh"
bash "$work/preflight_staging_env.sh" "$work/docker-compose.deploy.yml" "$env_file"

# The checkout supplies the compose file and these scripts, at the commit the images
# were built from.
git checkout main
git reset --hard "$APP_VERSION"

compose() { scripts/deploy/compose.sh "$@"; }
compose up -d --remove-orphans

# What the record named before this deploy is now the rollback.
recorded() { [ ! -f .deploy-images.env ] || sed -nE "s/^$1=//p" .deploy-images.env | tail -n 1; }
rollback_backend=$(recorded BACKEND_IMAGE)
rollback_frontend=$(recorded FRONTEND_IMAGE)

# Recorded only now, so the file never names an image that failed to start. Written
# beside the target and renamed, so a reader never sees half of it.
umask 077
printf 'APP_VERSION=%s\nBACKEND_IMAGE=%s\nFRONTEND_IMAGE=%s\n' "$APP_VERSION" "$BACKEND_IMAGE" "$FRONTEND_IMAGE" > .deploy-images.env.new
mv .deploy-images.env.new .deploy-images.env
compose ps

# Each deploy pulls two new digests. This repository's images that are neither running
# nor the rollback go; the box is shared, so nothing outside these two names is
# touched (never `docker image prune`). With no rollback recorded, or the same images
# deployed again, which one is the rollback is unknown, and nothing goes.
keep=" $BACKEND_IMAGE $FRONTEND_IMAGE $rollback_backend $rollback_frontend "
if [ -n "$rollback_backend" ] && [ -n "$rollback_frontend" ] \
  && [ "$rollback_backend $rollback_frontend" != "$BACKEND_IMAGE $FRONTEND_IMAGE" ]; then
  for repository in "${BACKEND_IMAGE%@*}" "${FRONTEND_IMAGE%@*}"; do
    for image in $(docker image ls --digests --format '{{.Repository}}@{{.Digest}}' "$repository"); do
      # A locally built image has no digest: not one of the deploys'.
      case "$image" in *"@<none>") continue ;; esac
      case "$keep" in *" $image "*) continue ;; esac
      # A refusal (a container still uses it) costs disk, not the deploy.
      docker image rm "$image" >/dev/null || echo "deploy: could not remove $image; it stays" >&2
    done
  done
fi
