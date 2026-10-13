"""#552: something must consult per-subsystem health between deploys.

Two outages hid behind green signals for weeks: a rotated Atlas password (the
running process kept its authenticated pool) and a missing S3 bucket
(``/health/ready`` is Mongo-only, #503, and ``deploy.yml`` curled the shallower
``/health``). These tests parse the REAL workflow, compose and runbook files so
the wiring cannot quietly regress to "nothing checks".
"""

import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE = REPO_ROOT / "docker-compose.staging.yml"
RUNBOOK = REPO_ROOT / "docs" / "operations" / "CREDENTIAL_ROTATION.md"
HEALTH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "staging-health.yml"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

PROBE = "python -m app.health_probe"
SECRET_LIKE = re.compile(r"SECRET|KEY|PASSWORD|URI|TOKEN|DSN")


def _workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _run_blocks(path: Path) -> str:
    doc = _workflow(path)
    return "\n".join(
        step.get("run", "") for job in doc["jobs"].values() for step in job["steps"]
    )


def test_runbook_names_every_secret_the_compose_file_interpolates():
    """AC3: rotation and update are one procedure only if the runbook lists every
    consumer. A new secret in compose must land in the table."""
    referenced = set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", COMPOSE.read_text()))
    secrets = sorted(v for v in referenced if SECRET_LIKE.search(v))
    assert secrets, "expected the compose file to interpolate at least one secret"
    runbook = RUNBOOK.read_text()
    missing = [v for v in secrets if f"`{v}`" not in runbook]
    assert not missing, f"docs/operations/CREDENTIAL_ROTATION.md must name: {missing}"


def test_scheduled_probe_runs_independently_of_deploys():
    """AC1: a schedule, the probe, and a failure that lands somewhere visible."""
    doc = _workflow(HEALTH_WORKFLOW)
    triggers = doc.get("on") or doc[True]  # PyYAML parses a bare `on:` key as True
    assert "schedule" in triggers and "workflow_dispatch" in triggers
    runs = _run_blocks(HEALTH_WORKFLOW)
    assert PROBE in runs
    assert "gh issue" in runs, "a red run nobody watches is not a report"
    assert doc["permissions"].get("issues") == "write"
    # A tailnet/ssh failure leaves the probe step *skipped*; gating the report on
    # the probe's own outcome would file nothing for exactly those failures.
    report = next(
        s for s in doc["jobs"]["probe"]["steps"] if s["name"].startswith("Report")
    )
    assert str(report["if"]).strip() == "failure()"


def test_deploy_gate_asserts_connection_dependent_health():
    """AC2/AC4: the post-deploy gate waits on readiness (Mongo-backed) and then runs
    the probe in the freshly recreated container — never the bare liveness ping,
    which is 200 from a worker whose credentials are dead."""
    runs = _run_blocks(DEPLOY_WORKFLOW)
    assert PROBE in runs
    assert "/health/ready" in runs
    assert not re.search(r"https?://\S*/health(?![/a-z_])", runs), (
        "bare /health is liveness only"
    )


# --- #757: the alert must survive a retitle and say what state the container is in ---

STATE_SCRIPT = REPO_ROOT / "scripts" / "deploy" / "backend_state.sh"
ALERT_PHRASE = "Staging health probe is failing"
# The operator retitles every issue with a PX.Y prefix (repo convention), and #755
# became this the day it was filed — the next hourly run then opened #757 next to it.
RETITLED = "[P1.51] [ops] Staging health probe is failing — backend not serving since the 2026-09-15 deploy"


def _steps(path: Path) -> dict[str, dict]:
    doc = _workflow(path)
    return {s["name"]: s for job in doc["jobs"].values() for s in job["steps"]}


def _search_terms(run: str) -> list[str]:
    """The `search='…'` the step passes as `--search "$search"`."""
    assert '--search "$search"' in run
    return re.findall(r"search='([^']*)'", run)


def test_alert_dedupe_search_carries_no_priority_prefix():
    """Searching on the literal bot title (`[P1] [ops] …`) stops matching the moment
    a human retitles it `[P1.51] …`, and the next run files a duplicate."""
    steps = _steps(HEALTH_WORKFLOW)
    report = steps["Report the failure on an issue"]["run"]
    close = steps["Close a recovered alert"]["run"]
    terms = _search_terms(report) + _search_terms(close)
    assert len(terms) == 2, f"expected one --search per step, got {terms}"
    for term in terms:
        phrase = term.replace("\\", "").replace('"', "").replace("in:title", "").strip()
        assert "[P" not in phrase, f"search must not key on the priority prefix: {term}"
        assert phrase == ALERT_PHRASE
        assert phrase in RETITLED


def test_alert_comments_on_the_oldest_match_and_recovery_closes_every_match():
    steps = _steps(HEALTH_WORKFLOW)
    report = steps["Report the failure on an issue"]["run"]
    close = steps["Close a recovered alert"]["run"]
    assert "min_by(.number)" in report, (
        "comment on the oldest open alert, not an arbitrary one"
    )
    assert ".[0]" not in close and ".[].number" in close, (
        "a recovery must close every open alert — two were open at once (#755, #757)"
    )


def test_both_workflows_dump_backend_state_when_the_gate_fails():
    """The alert body used to be pydantic stderr noise and an exit code; the operator's
    first step was to ssh in and look at the container. The workflow can do that."""
    for wf in (HEALTH_WORKFLOW, DEPLOY_WORKFLOW):
        steps = _steps(wf)
        state = next(
            s for s in steps.values() if "backend_state.sh" in s.get("run", "")
        )
        assert "failure()" in str(state["if"])
        assert any("actions/checkout" in s.get("uses", "") for s in steps.values()), (
            f"{wf.name} must check out the repo to ship the state script over ssh"
        )
    health = _steps(HEALTH_WORKFLOW)["Report the failure on an issue"]["run"]
    assert "state.txt" in health
    assert "137" in health, (
        "a SIGKILLed probe means the container died under it — say so"
    )


def test_backend_state_script_emits_exception_classes_not_log_lines():
    """The repo is public: a pymongo auth error names the Atlas cluster, a boto error
    the bucket. Only status fields and exception CLASS names may leave the box."""
    assert STATE_SCRIPT.stat().st_mode & stat.S_IXUSR
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "bin" / "docker"
        fake.parent.mkdir()
        fake.write_text(
            "#!/usr/bin/env bash\n"
            'case " $* " in\n'
            "  *\" ps -q \"*) echo 'c0ffee';;\n"
            "  *\" ps \"*) echo 'narrative-staging-backend  Restarting (3) 2 seconds ago';;\n"
            "  *\" inspect c0ffee \"*) echo 'RestartCount=41 OOMKilled=false ExitCode=3';;\n"
            "  *\" inspect \"*) echo 'inspect got the wrong container id' >&2; exit 1;;\n"
            '  *" logs "*)\n'
            "    echo 'pymongo.errors.OperationFailure: bad auth : authentication failed, full error: {host: cluster0.abc123.mongodb.net}';\n"
            "    echo 'connecting to mongodb+srv://svc_user:hunter2@cluster0.abc123.mongodb.net/db';\n"
            "    echo 'botocore.exceptions.ClientError: An error occurred (404) when calling the HeadBucket operation: Not Found bucket=narrative-secret-bucket';\n"
            "    echo '[ERROR] Worker (pid:12) exited with code 3';\n"
            "    echo '[ERROR] Worker failed to boot.';\n"
            "    echo \"RuntimeError: Configured S3 bucket 'narrative-secret-bucket' is not writable (ClientError); refusing to start (#495).\";;\n"
            "esac\n"
        )
        fake.chmod(0o755)
        out = subprocess.run(
            ["bash", str(STATE_SCRIPT)],
            env={
                **os.environ,
                "PATH": f"{fake.parent}:{os.environ['PATH']}",
                "DEPLOY_PATH": tmp,
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    assert "Restarting (3)" in out and "RestartCount=41" in out
    assert "OperationFailure" in out and "ClientError" in out
    assert "(404) when calling the HeadBucket operation" in out
    assert "Worker failed to boot" in out
    assert "is not writable (ClientError)" in out, (
        "the #495 boot-refusal mode, minus the bucket name"
    )
    for secret in (
        "mongodb.net",
        "hunter2",
        "svc_user",
        "narrative-secret-bucket",
        "full error",
    ):
        assert secret not in out, f"{secret!r} left the box"
    assert "LogsFetchError" not in out
    # A failed log fetch is a visible sentinel, never an empty section that reads as "clean".
    with tempfile.TemporaryDirectory() as tmp2:
        fake2 = Path(tmp2) / "bin" / "docker"
        fake2.parent.mkdir()
        fake2.write_text(
            '#!/usr/bin/env bash\ncase " $* " in *" logs "*) exit 1;; *) echo x;; esac\n'
        )
        fake2.chmod(0o755)
        failed = subprocess.run(
            ["bash", str(STATE_SCRIPT)],
            env={
                **os.environ,
                "PATH": f"{fake2.parent}:{os.environ['PATH']}",
                "DEPLOY_PATH": tmp2,
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    assert "LogsFetchError" in failed


# --- #756: the frontend container shares MONGODB_URI and NEXTAUTH_SECRET -------------

FRONTEND_PROBE = REPO_ROOT / "scripts" / "deploy" / "frontend_probe.sh"
FRONTEND_ROUTE = (
    REPO_ROOT / "apps" / "frontend" / "app" / "api" / "health" / "ready" / "route.ts"
)


def test_both_workflows_probe_the_frontend_container_in_the_same_run():
    """A stale credential in the frontend breaks sign-in while pages still render. The
    probe ran in the backend container only; the frontend's half must fail the same
    run, so it lands on the same alert issue."""
    assert FRONTEND_ROUTE.exists(), "the script asks a route that must exist"
    for wf in (HEALTH_WORKFLOW, DEPLOY_WORKFLOW):
        step = next(s for s in _steps(wf).values() if PROBE in s.get("run", ""))
        assert "frontend_probe.sh" in step["run"], (
            f"{wf.name}: the frontend probe must run in the step that runs the backend's"
        )
    health = next(
        s for s in _steps(HEALTH_WORKFLOW).values() if PROBE in s.get("run", "")
    )["run"]
    # Its output joins the backend's in the file the alert quotes, and its exit code
    # reaches the status the alert is keyed on.
    assert "cat /tmp/frontend-probe.txt >> /tmp/probe.txt" in health
    assert "status=$frontend" in health


def _frontend_probe(docker_script: str) -> subprocess.CompletedProcess:
    """Run the script the way both workflows do: fed to ``bash -s`` on stdin.

    The fake ``docker`` drains its stdin first, as ``docker compose exec`` does. Run as
    a file, with a ``docker`` that ignored stdin, these tests passed while the real
    thing printed nothing and exited 0: the exec ate the rest of the script (#756)."""
    assert FRONTEND_PROBE.stat().st_mode & stat.S_IXUSR
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "bin" / "docker"
        fake.parent.mkdir()
        fake.write_text("#!/usr/bin/env bash\ncat > /dev/null\n" + docker_script)
        fake.chmod(0o755)
        return subprocess.run(
            ["bash", "-s"],
            stdin=FRONTEND_PROBE.open(),
            env={
                **os.environ,
                "PATH": f"{fake.parent}:{os.environ['PATH']}",
                "DEPLOY_PATH": tmp,
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )


def test_frontend_probe_is_fed_to_bash_on_stdin_by_both_workflows():
    """Pins what `_frontend_probe` imitates. If a workflow starts running the script
    another way, the harness above stops being the real thing."""
    for wf in (HEALTH_WORKFLOW, DEPLOY_WORKFLOW):
        run = _run_blocks(wf)
        assert re.search(r"bash -s\"\s*<\s*scripts/deploy/frontend_probe\.sh", run), wf.name
        # And neither takes silence for a pass: no verdict line fails the step. It is
        # looked for in the probe's own file, where no backend line can stand in for it.
        assert "grep -q '^frontend: ' /tmp/frontend-probe.txt" in run, wf.name
        # Nor loses the exit code in a pipe (the run shell has no pipefail).
        assert not re.search(r"frontend_probe\.sh[^\n]*\|", run), wf.name


def _answering(body: str, code: int) -> str:
    """A `docker compose … exec -T frontend curl -w '\\n%{http_code}' …` that answers."""
    return f"printf '%s\\n%s' '{body}' '{code}'\n"


HEALTHY = '{"status":"healthy","checks":{"mongo":"healthy","api_token":"healthy"}}'
STALE = (
    '{"status":"unhealthy","checks":{"mongo":"unhealthy (MongoServerError'
    ' AuthenticationFailed)","api_token":"healthy"}}'
)


def test_frontend_probe_passes_the_routes_verdict_through():
    healthy = _frontend_probe(_answering(HEALTHY, 200))
    assert (healthy.returncode, healthy.stdout.strip()) == (0, f"frontend: {HEALTHY}")

    stale = _frontend_probe(_answering(STALE, 503))
    assert stale.returncode == 1
    assert "MongoServerError AuthenticationFailed" in stale.stdout


def test_frontend_probe_does_not_fail_an_image_that_predates_the_route():
    """The scheduled probe can run between the merge and the deploy that ships the route."""
    older = _frontend_probe(_answering("<html>404: This page could not be found</html>", 404))
    assert older.returncode == 0
    assert older.stdout.strip() == "frontend: skipped (this image has no readiness route)"


def test_frontend_probe_prints_a_report_or_a_fixed_phrase_and_nothing_else():
    """The repo is public. Whatever the container answers, only the route's own report
    is repeated; an error page or a dead container is named, not printed."""
    # Assembled, so no connection string with a password in it sits in the repo.
    leaked = "mongodb+srv://" + ":".join(("svc_user", "hunter2")) + "@cluster0.example.net"
    crashed = _frontend_probe(_answering(f"Error: connect to {leaked}", 500))
    assert crashed.returncode == 1
    assert crashed.stdout.strip() == (
        "frontend: unhealthy (the readiness route answered 500 with no report)"
    )

    # A 200 that carries no report is still a failure: something sat between curl and the route.
    proxied = _frontend_probe(_answering("<html>welcome</html>", 200))
    assert proxied.returncode == 1
    assert proxied.stdout.strip() == (
        "frontend: unhealthy (the readiness route answered 200 with no report)"
    )

    dead = _frontend_probe(
        "echo 'service \"frontend\" is not running: secret=hunter2' >&2; exit 1\n"
    )
    assert dead.returncode == 1
    assert dead.stdout.strip() == "frontend: unhealthy (the frontend container did not answer)"
    for run in (crashed, dead):
        assert "hunter2" not in run.stdout + run.stderr
