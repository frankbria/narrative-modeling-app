#!/usr/bin/env bash
# wait_for_server NAME URL PID SECONDS
#
# Polls URL once a second until it answers (returns 0). Stops early, returning 1, when
# PID has exited, so a server that crashed on start is reported at once instead of
# after the whole wait; returns 2 when SECONDS pass with the process still running
# (#1005: a loaded machine took longer than the old 30 seconds to start the backend).
# Prints which of the three happened. Sourced by test-e2e.sh.
#
# --self-check runs the three cases against throwaway processes.

wait_for_server() {
    local name=$1 url=$2 pid=$3 seconds=$4 i
    for ((i = 0; i < seconds; i++)); do
        # -f: an error status is not ready; --max-time: a server that accepts the
        # connection and then hangs must not stall the poll past its budget.
        if curl -sf --max-time 2 "$url" > /dev/null 2>&1; then
            echo "✓ ${name} is ready"
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "ERROR: the ${name} process exited before it answered at ${url}"
            return 1
        fi
        sleep 1
    done
    echo "ERROR: the ${name} is still running but did not answer at ${url} within ${seconds} seconds"
    return 2
}

_self_check() {
    local port pid status=0
    port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')

    python3 -m http.server "$port" --bind 127.0.0.1 > /dev/null 2>&1 &
    pid=$!
    wait_for_server "answering server" "http://127.0.0.1:${port}" "$pid" 10 > /dev/null
    [ $? -eq 0 ] || { echo "FAIL: a server that answers was not ready"; status=1; }
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null

    sleep 0 &
    pid=$!
    wait "$pid"
    wait_for_server "dead server" "http://127.0.0.1:${port}" "$pid" 10 > /dev/null
    [ $? -eq 1 ] || { echo "FAIL: a process that exited was not reported as exited"; status=1; }

    sleep 30 &
    pid=$!
    wait_for_server "silent server" "http://127.0.0.1:${port}" "$pid" 2 > /dev/null
    [ $? -eq 2 ] || { echo "FAIL: a process that never answered was not reported as timed out"; status=1; }
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null

    [ $status -eq 0 ] && echo "wait-for-server self-check: 3 cases passed"
    return $status
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--self-check" ]; then
    _self_check
    exit $?
fi
