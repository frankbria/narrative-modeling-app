#!/usr/bin/env bash
# dump_hung_backend WRAPPER_PID LOG
#
# For a backend that is running but no longer answers (#1245): writes a heading to LOG,
# then sends SIGABRT to every process under WRAPPER_PID (the `uv run` wrapper; the wrapper
# itself is left alone) and waits for them to exit. The backend is started with
# PYTHONFAULTHANDLER=1, so Python's fault handler writes every thread's stack to its
# stderr, which is LOG, before the process aborts. The handler runs in C and needs no
# lock, so it reports a thread that holds the GIL or a blocked event loop as well.
# Returns 1, saying so, when there is no process under the wrapper. Sourced by test-e2e.sh;
# tests: apps/backend/tests/test_security/test_hung_backend_stack_dump.py.

_descendants_of() {
    local child
    for child in $(pgrep -P "$1" 2>/dev/null); do
        echo "$child"
        _descendants_of "$child"
    done
}

dump_hung_backend() {
    local wrapper=$1 log=$2 pids pid
    pids=$(_descendants_of "$wrapper")
    if [ -z "$pids" ]; then
        echo "Backend stack dump: no backend process under pid ${wrapper}" | tee -a "$log"
        return 1
    fi
    echo "Backend stack dump (SIGABRT to pid ${pids//$'\n'/ }); every thread's stack follows in this log:" | tee -a "$log"
    for pid in $pids; do
        kill -ABRT "$pid" 2>/dev/null || true
    done
    # The handler writes and the process aborts within a moment; 20 seconds is for a
    # loaded runner. The cleanup that follows stops anything still left.
    for _ in $(seq 40); do
        for pid in $pids; do
            kill -0 "$pid" 2>/dev/null && break
            pid=
        done
        [ -z "$pid" ] && return 0
        sleep 0.5
    done
    echo "Backend stack dump: pid ${pid} was still running 20 seconds after SIGABRT" | tee -a "$log"
    return 0
}
