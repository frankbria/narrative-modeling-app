#!/bin/bash
# E2E Test Runner with Port Cleanup
# Ensures the dev server port is free before running Playwright tests

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine the port to use (default to 3010 if PORT not set)
TEST_PORT="${PORT:-3010}"

echo -e "${YELLOW}=== E2E Test Port Cleanup ===${NC}"
echo "Target port: ${TEST_PORT}"

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

echo ""
echo -e "${YELLOW}=== Starting Playwright Tests ===${NC}"
echo "Command: npx playwright test $@"
echo ""

# Run Playwright with all arguments passed to this script
npx playwright test "$@"

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=== Tests completed successfully ===${NC}"
else
    echo ""
    echo -e "${RED}=== Tests failed with exit code ${EXIT_CODE} ===${NC}"
fi

exit $EXIT_CODE
