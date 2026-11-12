"""#606: something other than a human must run the subscription reconciliation.

A missed renewal event costs a paying customer their tier once the grace window
passes, and only re-reading Stripe repairs it. These tests run the REAL steps of
``subscription-reconcile.yml`` against stand-ins for the box and for ``gh``, so the
schedule cannot quietly become a run that reconciles nothing or reports to nobody.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "subscription-reconcile.yml"
BACKEND = REPO_ROOT / "apps" / "backend"

COMMAND = "python -m app.billing.reconcile_subscriptions --apply"
ALERT_PHRASE = "Subscription reconciliation is failing"
RECONCILE = "Reconcile subscriptions in the backend container"
REPORT = "Report the failure on an issue"
CLOSE = "Close a recovered alert"
CLEAN_RUN = (
    "subscriptions with a stripe id: 2\n"
    "unreadable from stripe:         0\n"
    "drifted from stripe:            1\n"
    "repaired:                       1\n"
    "skipped (changed under us):     0\n"
)


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps() -> dict[str, dict]:
    return {s["name"]: s for s in _doc()["jobs"]["reconcile"]["steps"]}


def _run_step(name: str, tmp: Path, fakes: dict[str, str], **env: str):
    """Run a step's script as Actions does (`bash -e`), with /tmp moved under `tmp`
    and each fake (repo-relative path or bare command name → script) in place."""
    bin_dir = tmp / "bin"
    bin_dir.mkdir(exist_ok=True)
    for target, script in fakes.items():
        path = tmp / target if "/" in target else bin_dir / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/usr/bin/env bash\n" + script)
        path.chmod(0o755)
    return subprocess.run(
        ["bash", "-e", "-c", _steps()[name]["run"].replace("/tmp/", f"{tmp}/")],
        cwd=tmp,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GITHUB_STEP_SUMMARY": str(tmp / "summary.md"),
            "RUN_URL": "https://example.invalid/run",
            **env,
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _reconcile_step(box_script: str) -> tuple[int, str, str]:
    """Exit status, recorded status and step summary for a box that runs `box_script`."""
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        run = _run_step(RECONCILE, tmp, {"scripts/deploy/on_box.sh": box_script})
        return (
            run.returncode,
            (tmp / "reconcile.status").read_text().strip(),
            (tmp / "summary.md").read_text(),
        )


def _posted_alert(files: dict[str, str], **env: str) -> str:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for name, text in files.items():
            (tmp / name).write_text(text)
        posted = tmp / "posted.txt"
        run = _run_step(
            REPORT, tmp, {"gh": f'printf "%s\\n" "$@" >> {posted}\n'}, **env
        )
        assert run.returncode == 0, run.stderr
        return posted.read_text()


def test_it_runs_on_a_schedule_without_a_deploy():
    doc = _doc()
    triggers = doc.get("on") or doc[True]  # PyYAML parses a bare `on:` key as True
    assert triggers["schedule"], "criterion 1: something other than a human runs it"
    assert "workflow_dispatch" in triggers
    assert "push" not in triggers


def test_it_runs_the_module_the_image_ships_and_writes_the_repair():
    """The runtime image carries only `/app/app`: a path under `scripts/` does not
    exist in the container, and without `--apply` the run repairs nothing."""
    run = _steps()[RECONCILE]["run"]
    assert COMMAND in run
    assert "scripts/deploy/on_box.sh" in run
    assert "exec -T backend" in run
    assert (BACKEND / "app" / "billing" / "reconcile_subscriptions.py").exists()
    assert not (BACKEND / "scripts" / "reconcile_subscriptions.py").exists()


def test_a_clean_run_passes_and_shows_its_counts():
    status, recorded, summary = _reconcile_step(
        f"cat > /dev/null\nprintf '{CLEAN_RUN}'\n"
    )
    assert (status, recorded) == (0, "0")
    assert "repaired:                       1" in summary


def test_the_reconciliations_exit_status_fails_the_run():
    """Exit 1 is an unreadable or raced row, 2 a missing setting: both are red."""
    for code in (1, 2):
        status, recorded, _ = _reconcile_step(
            f"cat > /dev/null\necho 'unreadable from stripe:         1'\nexit {code}\n"
        )
        assert (status, recorded) == (code, str(code))


def test_an_exit_0_that_printed_no_counts_fails_the_run():
    """#756: an exec that never ran the module exited 0 having printed nothing."""
    status, recorded, _ = _reconcile_step("cat > /dev/null\n")
    assert status != 0 and recorded != "0"


def test_a_failure_lands_on_an_issue_and_survives_a_retitle():
    doc = _doc()
    assert doc["permissions"]["issues"] == "write"
    report = _steps()[REPORT]
    # A tailnet or ssh failure leaves the reconcile step skipped; keying the report
    # on that step's outcome would file nothing for exactly those failures.
    assert str(report["if"]).strip() == "failure()"
    for name in (REPORT, CLOSE):
        assert f"search='\"{ALERT_PHRASE}\" in:title'" in _steps()[name]["run"]
    assert "min_by(.number)" in report["run"]
    assert str(_steps()[CLOSE]["if"]).strip() == "steps.reconcile.outcome == 'success'"
    assert ".[].number" in _steps()[CLOSE]["run"]


def test_the_alert_carries_the_counts_and_says_what_the_exit_status_means():
    posted = _posted_alert(
        {
            "reconcile.status": "1",
            "reconcile.txt": "  could not read one subscription from Stripe: RateLimitError\n"
            "unreadable from stripe:         1\n",
        }
    )
    assert f"[P2] [billing] {ALERT_PHRASE}" in posted
    assert "RateLimitError" in posted and "unreadable from stripe:         1" in posted
    assert "could not be read from Stripe" in posted
    assert "https://example.invalid/run" in posted


def test_the_alert_is_filed_when_the_reconciliation_never_ran():
    posted = _posted_alert({})
    assert "did not run" in posted


def test_the_alert_never_publishes_the_box():
    """The issue is public; ssh names the user and host in its errors (#1150)."""
    error = (
        "deployer@box-name: Permission denied (publickey).\n"
        "cannot cd to /srv/secret-path\n"
    )
    posted = _posted_alert(
        {"reconcile.err": error},
        HOST="Box-Name",
        DEPLOY_USER="deployer",
        DEPLOY_PATH="/srv/secret-path",
    )
    assert "<deploy user>@<staging host>: Permission denied" in posted
    for secret in ("box-name", "deployer", "/srv/secret-path"):
        assert secret not in posted.lower()
    reconcile, report = _steps()[RECONCILE]["env"], _steps()[REPORT]["env"]
    for name in ("HOST", "DEPLOY_USER", "DEPLOY_PATH"):
        assert report[name] == reconcile[name], name
