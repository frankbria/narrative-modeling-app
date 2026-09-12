#!/bin/bash
# E2E Test Runner with Port Cleanup
# Ensures the dev server port is free before running Playwright tests

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get absolute paths for frontend and backend directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="${SCRIPT_DIR}"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/../backend" && pwd)"

# Determine the ports to use
TEST_PORT="${PORT:-3010}"
BACKEND_PORT=8000

echo -e "${YELLOW}=== E2E Test Port Cleanup ===${NC}"
echo "Frontend port: ${TEST_PORT}"
echo "Backend port: ${BACKEND_PORT}"

# Function to check if a port is in use
check_port_in_use() {
    local port=$1
    # lsof missed a listening next-server here once (WSL), so the check let a stale
    # dev server from an earlier run keep the port while the new one bound the
    # next free port — and every spec then hit the old server's environment (#613).
    if lsof -Pi :${port} -sTCP:LISTEN -t >/dev/null 2>&1 \
        || (command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE ":${port} "); then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Stop a server we started, children included. `npm run dev` and `uv run` are
# wrappers: killing only the wrapper orphaned `next-server` / `uvicorn`, which
# kept the port with a frozen environment and answered the next run's specs (#613).
stop_tree() {
    local pid=$1
    [ -n "$pid" ] || return 0
    # Recurse first: `next dev` is itself a wrapper around `next-server`, so one
    # level of children is not enough.
    local child
    for child in $(pgrep -P "$pid" 2>/dev/null); do
        stop_tree "$child"
    done
    kill "$pid" 2>/dev/null || true
    # TERM first, then a short grace, then KILL: a server that ignores TERM would
    # otherwise outlive the script and hold the port for the next run.
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "$pid" 2>/dev/null || return 0
        sleep 0.5
    done
    kill -9 "$pid" 2>/dev/null || true
}

# Function to kill processes on a port
kill_port_processes() {
    local port=$1
    echo -e "${YELLOW}Checking port ${port}...${NC}"

    if check_port_in_use ${port}; then
        echo -e "${YELLOW}Port ${port} is in use. Attempting to free it...${NC}"

        # Try lsof approach (macOS and Linux)
        if command -v lsof >/dev/null 2>&1; then
            local pids=$(lsof -ti :${port} 2>/dev/null || true)
            if [ -n "$pids" ]; then
                echo "Found processes: $pids"
                echo "$pids" | xargs kill -9 2>/dev/null || true
                sleep 1
            fi
        fi

        # Try fuser approach (Linux fallback)
        if check_port_in_use ${port} && command -v fuser >/dev/null 2>&1; then
            echo "Trying fuser method..."
            fuser -k ${port}/tcp 2>/dev/null || true
            sleep 1
        fi

        # Verify port is now free
        if check_port_in_use ${port}; then
            echo -e "${RED}ERROR: Failed to free port ${port}${NC}"
            echo "Please manually kill the process using port ${port}:"
            echo "  lsof -ti :${port} | xargs kill -9"
            exit 1
        else
            echo -e "${GREEN}✓ Port ${port} is now free${NC}"
        fi
    else
        echo -e "${GREEN}✓ Port ${port} is already free${NC}"
    fi
}

# Main execution
kill_port_processes ${TEST_PORT}
kill_port_processes ${BACKEND_PORT}

# Export environment variables BEFORE starting backend
export NODE_ENV=development
export TEST_USER_EMAIL=${TEST_USER_EMAIL:-test@narrativeml.com}
export TEST_USER_PASSWORD=${TEST_USER_PASSWORD:-test-password-123}
# /admin guard (#477, #613): the ordinary test user is NOT an admin and the second
# dev-credentials identity IS — deliberately, and unconditionally: an ambient
# ADMIN_EMAILS from the caller's shell is overwritten, or the smoke spec's two
# cases would depend on whatever happened to be exported.
export TEST_ADMIN_EMAIL=${TEST_ADMIN_EMAIL:-admin-e2e@narrativeml.com}
export TEST_ADMIN_PASSWORD=${TEST_ADMIN_PASSWORD:-admin-password-123}
export ADMIN_EMAILS="$TEST_ADMIN_EMAIL"
if [ "$TEST_ADMIN_EMAIL" = "$TEST_USER_EMAIL" ]; then
  echo "TEST_ADMIN_EMAIL must differ from TEST_USER_EMAIL: the credentials provider" >&2
  echo "checks the ordinary user first, so an equal admin identity would silently be a non-admin." >&2
  exit 1
fi
export MONGODB_URI=${MONGODB_URI:-mongodb://localhost:27017}
export MONGODB_DB=${MONGODB_DB:-narrative-modeling-test}
export NEXTAUTH_SECRET=${NEXTAUTH_SECRET:-test-secret-for-e2e-only-not-for-production}
export SKIP_AUTH=true
# Disable global rate limiting for E2E (#151): SKIP_AUTH makes every request share
# one dev-user bucket, so parallel Playwright workers + polling dashboards would
# trip the per-user limit and flake. Rate limiting has its own unit/integration
# coverage; the E2E suite must not be subject to it.
export RATE_LIMIT_ENABLED=false
# Plan limits (#368) count per user per month and every e2e test shares one
# user: FREE's 20 uploads / 10 training runs are exhausted by a single smoke
# run with retries, after which every later upload 402s and the failures
# cascade. The overrides are the module's own lever (`_env_int`); quota
# behaviour itself is covered by the backend suite, not by e2e.
export PLAN_FREE_UPLOADS=${PLAN_FREE_UPLOADS:-10000}
export PLAN_FREE_TRAINING_RUNS=${PLAN_FREE_TRAINING_RUNS:-10000}
export PLAN_FREE_PREDICTIONS=${PLAN_FREE_PREDICTIONS:-1000000}
export PLAN_FREE_AI_CALLS=${PLAN_FREE_AI_CALLS:-100000}

# AWS S3 configuration (test/mock values for E2E)
# When AWS_ENDPOINT_URL is set (e.g. http://localhost:9000 for MinIO in CI),
# the backend routes all S3 calls to that endpoint instead of real AWS.
export AWS_S3_BUCKET_NAME=${AWS_S3_BUCKET_NAME:-test-bucket}
export AWS_BUCKET_NAME=${AWS_BUCKET_NAME:-test-bucket}
export AWS_S3_BUCKET=${AWS_S3_BUCKET:-test-bucket}
export S3_BUCKET=${S3_BUCKET:-test-bucket}

# Upload workflows hard-require S3-compatible storage (issue #191): without
# AWS_ENDPOINT_URL the backend targets real AWS with dummy credentials and
# every upload-dependent spec fails (or hangs in boto3 retries) in beforeEach.
# Auto-detect a running LocalStack so a plain ./test-e2e.sh just works.
if [ -z "${AWS_ENDPOINT_URL:-}" ] && curl -sf http://localhost:4566/_localstack/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Detected LocalStack on :4566 — using it for S3${NC}"
    export AWS_ENDPOINT_URL=http://localhost:4566
fi
if [ -z "${AWS_ENDPOINT_URL:-}" ]; then
    echo -e "${YELLOW}⚠ No S3-compatible storage configured (AWS_ENDPOINT_URL unset, LocalStack not on :4566).${NC}"
    echo -e "${YELLOW}  Upload-dependent specs WILL fail. Start storage first:${NC}"
    echo -e "${YELLOW}  docker compose -f ${BACKEND_DIR}/docker-compose.test.yml up -d localstack${NC}"
fi

if [ -n "${AWS_ENDPOINT_URL:-}" ]; then
  # Real S3-compatible storage (MinIO/LocalStack): credentials must NOT start
  # with "test-" or S3Service enters no-op mock mode instead of using MinIO.
  export AWS_ENDPOINT_URL
  export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-minioadmin}
  export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-minioadmin}
else
  export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-test-access-key-id}
  export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-test-secret-access-key}
fi
export AWS_REGION=${AWS_REGION:-us-east-1}

# OpenAI API configuration (test/mock value for E2E)
export OPENAI_API_KEY=${OPENAI_API_KEY:-sk-test-dummy-key-for-e2e-testing}

echo ""
echo -e "${YELLOW}=== Starting Backend Server ===${NC}"
# Start backend in background using absolute path
uv run --directory "${BACKEND_DIR}" uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT} > /tmp/backend-e2e.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to be ready
echo "Waiting for backend to start..."
for i in {1..30}; do
  if curl -s http://localhost:${BACKEND_PORT}/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is ready${NC}"
    break
  fi
  if [ $i -eq 30 ]; then
    echo -e "${RED}ERROR: Backend failed to start within 30 seconds${NC}"
    echo -e "${YELLOW}Backend logs:${NC}"
    cat /tmp/backend-e2e.log 2>/dev/null || echo "No backend logs found"
    stop_tree $BACKEND_PID
    exit 1
  fi
  sleep 1
done

echo ""
echo -e "${YELLOW}=== Seeding E2E Test Data ===${NC}"
# Seed MongoDB with test user and sample data using absolute path
uv run --directory "${BACKEND_DIR}" python scripts/seed_e2e_data.py
SEED_EXIT_CODE=$?

if [ $SEED_EXIT_CODE -ne 0 ]; then
  echo -e "${RED}ERROR: Failed to seed test data${NC}"
  stop_tree $BACKEND_PID
  exit 1
fi

echo ""
echo -e "${YELLOW}=== Starting Frontend Dev Server ===${NC}"
# Start frontend in background (without SKIP_AUTH - tests need real auth flow)
PORT=${TEST_PORT} npm run dev > /tmp/frontend-e2e.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to be ready
echo "Waiting for frontend to start..."
for i in {1..60}; do
  if curl -s http://localhost:${TEST_PORT} > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend is ready${NC}"
    break
  fi
  if [ $i -eq 60 ]; then
    echo -e "${RED}ERROR: Frontend failed to start within 60 seconds${NC}"
    stop_tree $FRONTEND_PID
    stop_tree $BACKEND_PID
    exit 1
  fi
  sleep 1
done

echo ""
echo -e "${YELLOW}=== Starting Playwright Tests ===${NC}"
echo "Command: npx playwright test $@"
echo ""

# Export additional environment variables for Playwright tests
export NEXT_PUBLIC_API_URL=http://localhost:${BACKEND_PORT}/api/v1
export BASE_URL=http://localhost:${TEST_PORT}
export PORT=${TEST_PORT}
export NEXTAUTH_URL=http://localhost:${TEST_PORT}

# Run Playwright with all arguments passed to this script.
# Capture the exit code without letting `set -e` abort the script —
# cleanup below must always run, and the exit code must propagate.
EXIT_CODE=0
npx playwright test "$@" || EXIT_CODE=$?

# Cleanup: Kill both servers
echo ""
echo -e "${YELLOW}=== Cleaning up ===${NC}"
# `|| true` keeps `set -e` from turning an already-exited process
# (kill returns non-zero) into a spurious script failure on green runs
if [ ! -z "$FRONTEND_PID" ]; then
  stop_tree $FRONTEND_PID
  echo "Stopped frontend server (PID: $FRONTEND_PID)"
fi
if [ ! -z "$BACKEND_PID" ]; then
  stop_tree $BACKEND_PID
  echo "Stopped backend server (PID: $BACKEND_PID)"
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=== Tests completed successfully ===${NC}"
else
    echo ""
    echo -e "${RED}=== Tests failed with exit code ${EXIT_CODE} ===${NC}"
    echo -e "${YELLOW}Backend logs: /tmp/backend-e2e.log${NC}"
    echo -e "${YELLOW}Frontend logs: /tmp/frontend-e2e.log${NC}"
fi

exit $EXIT_CODE
