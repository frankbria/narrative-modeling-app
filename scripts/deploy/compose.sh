#!/usr/bin/env bash
# The one way to run docker compose for a deployed environment (#831):
#
#   scripts/deploy/compose.sh ps
#   scripts/deploy/compose.sh exec -T backend python -m app.health_probe
#   scripts/deploy/compose.sh up -d --force-recreate      # after a credential rotation
#
# docker-compose.deploy.yml serves staging and production, so it names neither and
# builds nothing. This supplies the four values it requires that no env file holds:
#
#   ENVIRONMENT                     the suffix of the one env file on the box
#                                   (.env.staging -> staging). The file's NAME decides,
#                                   so a box cannot come up as the other environment
#                                   because a line was left out or copied across.
#   BACKEND_IMAGE, FRONTEND_IMAGE   the digests of the deployed commit's images
#   APP_VERSION                     that commit
#
# The last three are read from .deploy-images.env, which deploy_images.sh writes after
# a successful `up`. That file is the answer to "what is running here".
#
# Runs in DEPLOY_PATH (default: the checkout this script is in).
set -euo pipefail
cd "${DEPLOY_PATH:-$(dirname "$0")/../..}"

env_files=()
for candidate in .env.staging .env.production; do
  if [ -f "$candidate" ]; then env_files+=("$candidate"); fi
done
if [ "${#env_files[@]}" -ne 1 ]; then
  echo "compose.sh: expected exactly one of .env.staging or .env.production in $PWD, found ${#env_files[@]}" >&2
  exit 2
fi
env_file=${env_files[0]}
export ENVIRONMENT=${env_file#.env.}

# Values already in the environment win: deploy_images.sh passes the images it is
# about to start, before it records them.
recorded() { sed -nE "s/^$1=//p" .deploy-images.env 2>/dev/null | tail -n 1; }
export BACKEND_IMAGE=${BACKEND_IMAGE:-$(recorded BACKEND_IMAGE)}
export FRONTEND_IMAGE=${FRONTEND_IMAGE:-$(recorded FRONTEND_IMAGE)}
export APP_VERSION=${APP_VERSION:-$(recorded APP_VERSION)}

if [ -z "$BACKEND_IMAGE" ] || [ -z "$FRONTEND_IMAGE" ] || [ -z "$APP_VERSION" ]; then
  # No deploy has recorded its images yet (the first deploy after #831 failed part
  # way, or the file was removed). The containers that are running can still be
  # inspected and probed, which is what keeps the health alert truthful; anything
  # that would start a container needs a real image and is refused.
  case " $* " in
    *" up "*|*" run "*|*" pull "*|*" create "*|*" restart "*|*" start "*)
      echo "compose.sh: no image is recorded in $PWD/.deploy-images.env; run a deploy (deploy.yml) first" >&2
      exit 2 ;;
  esac
  export BACKEND_IMAGE=${BACKEND_IMAGE:-not-recorded} FRONTEND_IMAGE=${FRONTEND_IMAGE:-not-recorded} APP_VERSION=${APP_VERSION:-not-recorded}
fi

exec docker compose -f docker-compose.deploy.yml --env-file "$env_file" "$@"
