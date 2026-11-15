"""#1245: when the E2E backend stops answering, its log shows where every thread is.

Twice the smoke job's backend stayed alive while `/health` went unanswered for the rest
of the run, and the uploaded log (#1233) ended mid-request with no clue which line held
the event loop. `test-e2e.sh` now starts the backend with `PYTHONFAULTHANDLER=1` and,
when the probe finds it running but not answering, `dump_hung_backend` sends it SIGABRT:
Python's fault handler writes every thread's stack to stderr, which is that log.
"""

import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

# apps/backend/tests/test_security/ -> repo root
REPO = Path(__file__).resolve().parents[4]
RUNNER_SCRIPT = REPO / "apps" / "frontend" / "test-e2e.sh"
HELPER = REPO / "apps" / "frontend" / "e2e" / "dump-hung-backend.sh"

# Stands in for the hung backend, as `uv run` → uvicorn → a child uvicorn would: under
# the wrapper, an intermediate shell with two hung Pythons under it. In the first, the
# main thread blocks on a lock nobody releases and a second thread sleeps; the second
# blocks on a lock. Each waits in a function the dump has to name. Signalling only some
# of the three leaves a stack missing.
FIRST_HUNG_PROCESS = """
import threading, time

def worker_sleeps_forever():
    time.sleep(600)

def main_thread_waits_on_a_lock():
    lock = threading.Lock()
    lock.acquire()
    print("first hung", flush=True)
    lock.acquire()

threading.Thread(target=worker_sleeps_forever, daemon=True).start()
main_thread_waits_on_a_lock()
"""

SECOND_HUNG_PROCESS = """
import threading

def second_process_waits_on_a_lock():
    lock = threading.Lock()
    lock.acquire()
    print("second hung", flush=True)
    lock.acquire()

second_process_waits_on_a_lock()
"""

# The intermediate shell logs the SIGABRT it gets and keeps waiting, so both Pythons are
# reaped by their own parent whatever the host's PID 1 does with orphans; a trap set to
# a command is reset in the children, so their SIGABRT keeps its default action.
INTERMEDIATE_SHELL = (
    "trap 'echo \"intermediate shell got SIGABRT\"' ABRT; "
    'PYTHONFAULTHANDLER=1 "$0" -c "$1" & '
    'PYTHONFAULTHANDLER=1 "$0" -c "$2" & '
    "until wait; do :; done"
)


def _start_hung_backend(log: Path) -> subprocess.Popen[bytes]:
    """A wrapper shell with the hung processes under it, as `uv run` is for uvicorn.

    In a session of its own, so `_stop_all` can end them all whatever the test reached.
    """
    with log.open("ab") as output:
        return subprocess.Popen(
            [
                "bash",
                "-c",
                'ulimit -c 0; bash -c "$0" "$@"; exit $?',
                INTERMEDIATE_SHELL,
                sys.executable,
                FIRST_HUNG_PROCESS,
                SECOND_HUNG_PROCESS,
            ],
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def _wait_until_hung(log: Path) -> None:
    deadline = time.monotonic() + 30
    while not _all_hung(log) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert _all_hung(log), "the stand-in never started: " + log.read_text()


def _all_hung(log: Path) -> bool:
    return {"first hung", "second hung"} <= set(log.read_text().splitlines())


def _processes_under(pid: int) -> list[int]:
    children = subprocess.run(
        ["pgrep", "-P", str(pid)], capture_output=True, text=True
    ).stdout.split()
    return [
        descendant
        for child in map(int, children)
        for descendant in [child, *_processes_under(child)]
    ]


def _still_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _stop_all(wrapper: subprocess.Popen[bytes] | subprocess.Popen[str]) -> None:
    try:
        os.killpg(wrapper.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    wrapper.wait(timeout=30)


def _dump(wrapper_pid: int, log: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            "-c",
            f'source "{HELPER}" && dump_hung_backend "$0" "$1"',
            str(wrapper_pid),
            str(log),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_log_gets_every_threads_stack_and_the_hung_process_is_stopped(
    tmp_path: Path,
):
    log = tmp_path / "backend-e2e.log"
    wrapper = _start_hung_backend(log)
    try:
        _wait_until_hung(log)
        backend = _processes_under(wrapper.pid)
        assert len(backend) == 3, f"expected the shell and two Pythons: {backend}"
        dumped = _dump(wrapper.pid, log)
        # Every one gone (reaped, not a zombie, which signal 0 still reaches) when the
        # helper returns: the dump is complete in the log before the job's cleanup and
        # upload run.
        still_running = [pid for pid in backend if _still_running(pid)]
    finally:
        _stop_all(wrapper)

    text = log.read_text()
    assert dumped.returncode == 0, dumped.stdout + dumped.stderr
    assert still_running == [], f"still running after the dump: {still_running}"
    dump = text[text.index("Backend stack dump") :]
    assert dump.count("Fatal Python error: Aborted") == 2, text
    assert "main_thread_waits_on_a_lock" in dump, text
    assert "worker_sleeps_forever" in dump, text
    assert "second_process_waits_on_a_lock" in dump, text
    assert "intermediate shell got SIGABRT" in dump, text
    assert len(re.findall(r"^(?:Current thread|Thread) 0x", dump, re.MULTILINE)) == 3, (
        text
    )
    assert "Backend stack dump" in dumped.stdout, (
        "the job log should say the dump is in the artifact"
    )


def test_a_wrapper_with_no_backend_under_it_is_reported_not_signalled(tmp_path: Path):
    log = tmp_path / "backend-e2e.log"
    lone = subprocess.Popen(["sleep", "30"])
    try:
        dumped = _dump(lone.pid, log)
        assert lone.poll() is None, "the wrapper itself must not be signalled"
    finally:
        lone.kill()
        lone.wait()

    assert dumped.returncode == 1
    assert "no backend process" in dumped.stdout
    assert "no backend process" in log.read_text()


def test_the_backend_is_started_with_the_fault_handler_on():
    start = next(
        line
        for line in RUNNER_SCRIPT.read_text().splitlines()
        if "uvicorn app.main:app" in line and not line.lstrip().startswith("#")
    )
    assert start.lstrip().startswith("PYTHONFAULTHANDLER=1 "), start


def test_the_runner_dumps_a_running_backend_that_does_not_answer_after_the_probe_line():
    script = RUNNER_SCRIPT.read_text()
    assert 'source "${SCRIPT_DIR}/e2e/dump-hung-backend.sh"' in script
    probe = script.index('echo "Backend after the tests:')
    dump = script.index('dump_hung_backend "$BACKEND_PID" /tmp/backend-e2e.log')
    stop = script.index("stop_tree $BACKEND_PID", probe)
    assert probe < dump < stop
    condition = [
        line
        for line in script[probe:dump].splitlines()
        if line.lstrip().startswith("if ")
    ][-1]
    assert '"$backend_process" = running' in condition, condition
    assert '"$health_status" != 200' in condition, condition


def test_the_docs_say_where_the_dump_is():
    for document in (
        REPO / "CLAUDE.md",
        REPO / "docs" / "dev" / "E2E_TESTING_GUIDE.md",
    ):
        assert "Backend stack dump" in document.read_text(), (
            f"{document.name} does not mention the dump"
        )


def test_nothing_the_runner_starts_writes_a_core_file():
    """The dump aborts the backend, and SIGABRT's default action dumps core: the
    backend's size, on a host that allows cores. Set before the start, so it holds
    whatever the host allows and needs nothing to succeed later."""
    script = RUNNER_SCRIPT.read_text()
    limit = re.search(r"^ulimit -c 0$", script, re.MULTILINE)
    assert limit, "test-e2e.sh no longer sets a core limit of 0"
    assert limit.start() < script.index("PYTHONFAULTHANDLER=1 uv run")


def test_uv_run_keeps_a_wrapper_with_the_backend_as_its_child():
    """The helper signals what is under `uv run`, which works only if uv forks, not execs.

    Pinned to this interpreter and offline, so a cold uv cache never resolves or
    downloads one: the PR gate needs no network for this test."""
    uv = shutil.which("uv")
    assert uv, "uv is how test-e2e.sh starts the backend"
    wrapper = subprocess.Popen(
        [
            uv,
            "run",
            "--no-project",
            "--offline",
            "--python",
            sys.executable,
            "python",
            "-c",
            "import os; print(os.getpid(), os.getppid())",
        ],
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        out, _ = wrapper.communicate(timeout=120)
    finally:
        _stop_all(wrapper)
    python_pid, parent = (int(field) for field in out.split())
    assert python_pid != wrapper.pid and parent == wrapper.pid, out
