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
            "  *\" ps \"*) echo 'narrative-staging-backend  Restarting (3) 2 seconds ago';;\n"
            "  *\" inspect \"*) echo 'RestartCount=41 OOMKilled=false ExitCode=3';;\n"
            '  *" logs "*)\n'
            "    echo 'pymongo.errors.OperationFailure: bad auth : authentication failed, full error: {host: cluster0.abc123.mongodb.net}';\n"
            "    echo 'connecting to mongodb+srv://svc_user:hunter2@cluster0.abc123.mongodb.net/db';\n"
            "    echo 'botocore.exceptions.ClientError: An error occurred (404) when calling the HeadBucket operation: Not Found bucket=narrative-secret-bucket';\n"
            "    echo '[ERROR] Worker (pid:12) exited with code 3';\n"
            "    echo '[ERROR] Worker failed to boot.';;\n"
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
    for secret in (
        "mongodb.net",
        "hunter2",
        "svc_user",
        "narrative-secret-bucket",
        "full error",
    ):
        assert secret not in out, f"{secret!r} left the box"
