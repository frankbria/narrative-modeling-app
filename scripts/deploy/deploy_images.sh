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

# Pulled first, before anything on the box changes: a pull that fails (a token, the
# registry) leaves the checkout, the containers and the record exactly as they were.
# It uses a docker config of its own, removed again whatever happens: the token
# never joins the box's stored credentials, and a login another app on a shared box
# keeps for the same registry is left alone.
registry_config=$(mktemp -d)
trap 'rm -rf "$registry_config"' EXIT
if [ -n "${REGISTRY_TOKEN:-}" ]; then
  printf '%s' "$REGISTRY_TOKEN" \
    | docker --config "$registry_config" login "${BACKEND_IMAGE%%/*}" --username "${REGISTRY_USER:-deploy}" --password-stdin >/dev/null
fi
for image in "$BACKEND_IMAGE" "$FRONTEND_IMAGE"; do
  docker --config "$registry_config" pull --quiet "$image"
done
rm -rf "$registry_config"

cd "$DEPLOY_PATH"
# The checkout supplies the compose file and these scripts, at the commit the images
# were built from.
git fetch --prune origin
git checkout main
git reset --hard "$APP_VERSION"

compose() { scripts/deploy/compose.sh "$@"; }
# compose.sh refuses a box that has both; here the one that exists is enough.
env_file=.env.staging
[ -f "$env_file" ] || env_file=.env.production
# Fail fast with the FULL list of any missing required vars, instead of letting
# compose abort on the first ${VAR:?} it interpolates.
bash scripts/deploy/preflight_staging_env.sh docker-compose.deploy.yml "$env_file"

# shortcut: images of earlier deploys stay on the box (the previous one is the
# rollback); remove older ones of this repository once disk use on a box shows it.
compose up -d --remove-orphans

# Recorded only now, so the file never names an image that failed to start. Written
# beside the target and renamed, so a reader never sees half of it.
umask 077
printf 'APP_VERSION=%s\nBACKEND_IMAGE=%s\nFRONTEND_IMAGE=%s\n' "$APP_VERSION" "$BACKEND_IMAGE" "$FRONTEND_IMAGE" > .deploy-images.env.new
mv .deploy-images.env.new .deploy-images.env
compose ps
