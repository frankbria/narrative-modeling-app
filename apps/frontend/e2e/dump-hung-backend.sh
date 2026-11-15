#!/usr/bin/env bash
# dump_hung_backend WRAPPER_PID LOG
#
# For a backend that is running but no longer answers (#1245): writes a heading to LOG,
# then sends SIGABRT to every process under WRAPPER_PID (the `uv run` wrapper; the wrapper
# itself is left alone) and waits for them to exit. The backend is started with
# PYTHONFAULTHANDLER=1, so Python's fault handler writes every thread's stack to its
# stderr, which is LOG, before the process aborts. The handler runs in C and needs no
# lock, so it reports a thread that holds the GIL or a blocked event loop as well.
# test-e2e.sh starts the backend with a core-file limit of 0: SIGABRT's default action
# would otherwise write a core the size of the backend on a host that allows cores.
# Returns 1, saying so, when there is no process under the wrapper; otherwise 0, also
# when a process outlives the 20-second wait (said in LOG; the cleanup then stops it).
# Sourced by test-e2e.sh;
# tests: apps/backend/tests/test_security/test_hung_backend_stack_dump.py.

_descendants_of() {
    local child
    for child in $(pgrep -P "$1" 2>/dev/null); do
        echo "$child"
        _descendants_of "$child"
    done
}

# Prints the first of the given pids that is still running (a zombie counts until reaped),
# or nothing.
_first_alive() {
    local pid
    for pid in "$@"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return
        fi
    done
}

dump_hung_backend() {
    local wrapper=$1 log=$2 pids pid alive
    pids=()
    # A read loop, not mapfile: macOS still ships bash 3.2.
    while read -r pid; do
        pids+=("$pid")
    done < <(_descendants_of "$wrapper")
    if [ "${#pids[@]}" -eq 0 ]; then
        echo "Backend stack dump: no backend process under pid ${wrapper}" | tee -a "$log"
        return 1
    fi
    echo "Backend stack dump (SIGABRT to pid ${pids[*]}); every thread's stack follows in this log:" | tee -a "$log"
    for pid in "${pids[@]}"; do
        kill -ABRT "$pid" 2>/dev/null || true
    done
    # The handler writes and the process aborts within a moment; 20 seconds is for a
    # loaded runner. The cleanup that follows stops anything still left.
    for _ in $(seq 40); do
        alive=$(_first_alive "${pids[@]}")
        [ -z "$alive" ] && return 0
        sleep 0.5
    done
    echo "Backend stack dump: pid ${alive} was still running 20 seconds after SIGABRT" | tee -a "$log"
    return 0
}
