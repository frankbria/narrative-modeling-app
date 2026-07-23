#!/bin/bash
set -euo pipefail

# Bring up local infrastructure (MongoDB + LocalStack S3) for development.
#
# ponytail: plain `docker run`, not compose — the repo has no root
# docker-compose.yml (staging uses Atlas; the test compose has no mongo).
# Two containers + a bucket is all local dev needs.

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

# Create .env from example if missing (non-fatal if no example exists)
if [ ! -f .env ] && [ -f .env.example ]; then
    echo "Creating .env from .env.example — edit it with your API keys."
    cp .env.example .env
    echo ""
fi

# Start MongoDB (idempotent: reuse an existing container, else create one)
if [ -n "$(docker ps -aq -f name=^narrative-mongodb$)" ]; then
    docker start narrative-mongodb >/dev/null
    echo "MongoDB: reusing existing container 'narrative-mongodb'"
else
    docker run -d --name narrative-mongodb \
        -p 27017:27017 \
        -e MONGO_INITDB_ROOT_USERNAME="$MONGO_USER" \
        -e MONGO_INITDB_ROOT_PASSWORD="$MONGO_PASS" \
        "$MONGO_IMAGE" >/dev/null
    echo "MongoDB: started (admin/$MONGO_PASS on :27017)"
fi

# Start LocalStack S3 (idempotent)
if [ -n "$(docker ps -aq -f name=^narrative-localstack$)" ]; then
    docker start narrative-localstack >/dev/null
    echo "LocalStack: reusing existing container 'narrative-localstack'"
else
    docker run -d --name narrative-localstack \
        -p 4566:4566 \
        -e SERVICES=s3 \
        "$LOCALSTACK_IMAGE" >/dev/null
    echo "LocalStack: started (S3 on :4566)"
fi

echo "Waiting for services to be ready..."
sleep 5

# Create the local S3 bucket (ignore "already exists")
docker exec narrative-localstack awslocal s3 mb "s3://$BUCKET" 2>/dev/null \
    && echo "Created bucket s3://$BUCKET" \
    || echo "Bucket s3://$BUCKET already exists"

echo ""
echo "Local infrastructure ready:"
echo "  - MongoDB:      localhost:27017 (user: $MONGO_USER)"
echo "  - LocalStack S3: localhost:4566 (bucket: $BUCKET)"
echo ""
echo "Next: run the apps locally (see docs/development/LOCAL_DEVELOPMENT.md):"
echo "  cd apps/backend  && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "  cd apps/frontend && npm run dev"
