"""#552: something must consult per-subsystem health between deploys.

Two outages hid behind green signals for weeks: a rotated Atlas password (the
running process kept its authenticated pool) and a missing S3 bucket
(``/health/ready`` is Mongo-only, #503, and ``deploy.yml`` curled the shallower
``/health``). These tests parse the REAL workflow, compose and runbook files so
the wiring cannot quietly regress to "nothing checks".
"""

import re
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
