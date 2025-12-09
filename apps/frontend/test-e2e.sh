#!/bin/bash
# E2E Test Runner with Port Cleanup
# Ensures the dev server port is free before running Playwright tests

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine the ports to use
TEST_PORT="${PORT:-3010}"
BACKEND_PORT=8000

echo -e "${YELLOW}=== E2E Test Port Cleanup ===${NC}"
echo "Frontend port: ${TEST_PORT}"
echo "Backend port: ${BACKEND_PORT}"

# Function to check if a port is in use
check_port_in_use() {
    local port=$1
    if lsof -Pi :${port} -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
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

echo ""
echo -e "${YELLOW}=== Starting Backend Server ===${NC}"
# Start backend in background
cd ../backend
uv run uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT} > /tmp/backend-e2e.log 2>&1 &
BACKEND_PID=$!
cd -

# Wait for backend to be ready
echo "Waiting for backend to start..."
for i in {1..30}; do
  if curl -s http://localhost:${BACKEND_PORT}/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is ready${NC}"
    break
  fi
  if [ $i -eq 30 ]; then
    echo -e "${RED}ERROR: Backend failed to start within 30 seconds${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
  fi
  sleep 1
done

echo ""
echo -e "${YELLOW}=== Starting Playwright Tests ===${NC}"
echo "Command: npx playwright test $@"
echo ""

# Export environment variables for E2E testing
export NODE_ENV=development
export NEXT_PUBLIC_API_URL=http://localhost:${BACKEND_PORT}/api/v1
export TEST_USER_EMAIL=${TEST_USER_EMAIL:-test@narrativeml.com}
export TEST_USER_PASSWORD=${TEST_USER_PASSWORD:-test-password-123}

# Run Playwright with all arguments passed to this script
npx playwright test "$@"

# Capture exit code
EXIT_CODE=$?

# Cleanup: Kill backend server
echo ""
echo -e "${YELLOW}=== Cleaning up ===${NC}"
if [ ! -z "$BACKEND_PID" ]; then
  kill $BACKEND_PID 2>/dev/null
  echo "Stopped backend server (PID: $BACKEND_PID)"
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=== Tests completed successfully ===${NC}"
else
    echo ""
    echo -e "${RED}=== Tests failed with exit code ${EXIT_CODE} ===${NC}"
    echo -e "${YELLOW}Backend logs: /tmp/backend-e2e.log${NC}"
fi

exit $EXIT_CODE
