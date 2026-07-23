#!/bin/bash
set -euo pipefail

# Bring up local infrastructure (MongoDB + LocalStack S3) for development.
#
# Uses plain `docker run` rather than compose: the repo has no root
# docker-compose.yml (staging uses Atlas; the test compose has no mongo),
# and two containers plus a bucket is all local dev needs.

MONGO_IMAGE="mongo:7"
LOCALSTACK_IMAGE="localstack/localstack:3"
MONGO_USER="admin"
MONGO_PASS="localpassword"   # local-only dev credentials (see docs/development/LOCAL_DEVELOPMENT.md)
BUCKET="narrative-modeling-local"

echo "Setting up local development infrastructure"
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed"
    exit 1
fi

# Start MongoDB (idempotent: reuse an existing container, else create one)
if [ -n "$(docker ps -aq -f name=^narrative-mongodb$)" ]; then
    docker start narrative-mongodb >/dev/null
    echo "MongoDB: reusing existing container 'narrative-mongodb'"
    echo "  (keeps its ORIGINAL credentials/image — 'docker rm -f narrative-mongodb' to recreate)"
else
    # Bind to loopback only — these are unauthenticated/well-known-credential
    # dev services and must not be reachable on a routable host interface.
    docker run -d --name narrative-mongodb \
        -p 127.0.0.1:27017:27017 \
        -e MONGO_INITDB_ROOT_USERNAME="$MONGO_USER" \
        -e MONGO_INITDB_ROOT_PASSWORD="$MONGO_PASS" \
        "$MONGO_IMAGE" >/dev/null
    echo "MongoDB: started (admin/$MONGO_PASS on 127.0.0.1:27017)"
fi

# Start LocalStack S3 (idempotent)
if [ -n "$(docker ps -aq -f name=^narrative-localstack$)" ]; then
    docker start narrative-localstack >/dev/null
    echo "LocalStack: reusing existing container 'narrative-localstack'"
else
    docker run -d --name narrative-localstack \
        -p 127.0.0.1:4566:4566 \
        -e SERVICES=s3 \
        "$LOCALSTACK_IMAGE" >/dev/null
    echo "LocalStack: started (S3 on 127.0.0.1:4566)"
fi

# Wait for LocalStack's S3 to accept requests before creating the bucket.
# A fixed sleep is unreliable on a cold run (image pulls, slow start), so poll
# until `s3 ls` succeeds — that way a real failure surfaces instead of being
# masked by a swallowed `mb` error.
echo "Waiting for LocalStack S3 to be ready..."
ready=false
for _ in $(seq 1 30); do
    if docker exec narrative-localstack awslocal s3 ls >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 2
done

if [ "$ready" != true ]; then
    echo "ERROR: LocalStack S3 did not become ready in time; check 'docker logs narrative-localstack'." >&2
    exit 1
fi

# Wait for MongoDB to accept connections too (mirrors the LocalStack poll), so
# the printed "run the apps" instructions don't hit connection-refused on a
# cold start where mongod is still initializing.
echo "Waiting for MongoDB to be ready..."
mongo_ready=false
for _ in $(seq 1 30); do
    if docker exec narrative-mongodb mongosh --quiet --eval 'db.runCommand({ ping: 1 }).ok' >/dev/null 2>&1; then
        mongo_ready=true
        break
    fi
    sleep 2
done

if [ "$mongo_ready" != true ]; then
    echo "ERROR: MongoDB did not become ready in time; check 'docker logs narrative-mongodb'." >&2
    exit 1
fi

# Create the local S3 bucket. S3 is confirmed up, so only "already owned" is a
# benign non-zero exit — surface anything else instead of masking it.
if mb_err=$(docker exec narrative-localstack awslocal s3 mb "s3://$BUCKET" 2>&1); then
    echo "Created bucket s3://$BUCKET"
elif echo "$mb_err" | grep -qE "BucketAlreadyOwnedByYou|BucketAlreadyExists"; then
    echo "Bucket s3://$BUCKET already exists"
else
    echo "ERROR: failed to create bucket s3://$BUCKET:" >&2
    echo "$mb_err" >&2
    exit 1
fi

echo ""
echo "Local infrastructure ready:"
echo "  - MongoDB:      localhost:27017 (user: $MONGO_USER)"
echo "  - LocalStack S3: localhost:4566 (bucket: $BUCKET)"
echo ""
echo "Next: run the apps locally (see docs/development/LOCAL_DEVELOPMENT.md):"
echo "  cd apps/backend  && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "  cd apps/frontend && npm run dev"
echo ""
echo "To recreate from scratch (e.g. after changing credentials or image tags):"
echo "  docker rm -f narrative-mongodb narrative-localstack && ./scripts/local-setup.sh"
