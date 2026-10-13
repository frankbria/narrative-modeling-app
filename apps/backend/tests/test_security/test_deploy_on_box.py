"""#790: how the deploy workflows run something on the staging box.

Every step used to build its remote command as ``ssh host "… cd '$DEPLOY_PATH' …"``:
the value sat between quotes in a string the far shell then parsed, so a quote in it
ended the quoting and the rest ran as shell. The pattern had been copied to eight call
sites. ``scripts/deploy/on_box.sh`` is the one shape now, and these tests run it
against a fake ``ssh`` that parses the command string the way the far shell does.
"""

import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
ON_BOX = REPO_ROOT / "scripts" / "deploy" / "on_box.sh"
WORKFLOWS = [
    REPO_ROOT / ".github" / "workflows" / "deploy.yml",
    REPO_ROOT / ".github" / "workflows" / "staging-health.yml",
]

# The far side: skip ssh's own options and the destination, then hand the one command
# string to a shell, with stdin passed through. That re-parse is where a value written
# into the string could break out.
FAKE_SSH = """#!/usr/bin/env bash
while [ $# -gt 1 ]; do shift; done
exec bash -c "$1"
"""


def _on_box(body: str, deploy_path: str, *args: str) -> subprocess.CompletedProcess:
    assert ON_BOX.stat().st_mode & stat.S_IXUSR
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "bin" / "ssh"
        fake.parent.mkdir()
        fake.write_text(FAKE_SSH)
        fake.chmod(0o755)
        return subprocess.run(
            ["bash", str(ON_BOX), *args],
            input=body,
            env={
                **os.environ,
                "PATH": f"{fake.parent}:{os.environ['PATH']}",
                "HOST": "box.example",
                "DEPLOY_USER": "deployer",
                "DEPLOY_PATH": deploy_path,
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )


def test_a_path_with_shell_in_it_arrives_as_one_value_and_runs_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        marker = Path(tmp) / "ran"
        hostile = f"/srv/app's dir'; touch {marker}; echo '$(touch {marker}) `touch {marker}`"

        run = _on_box('printf "%s" "$DEPLOY_PATH"', hostile)

        assert run.returncode == 0, run.stderr
        assert run.stdout == hostile
        assert not marker.exists(), "something in DEPLOY_PATH was executed on the far side"


def test_the_ordinary_path_is_passed_through_unchanged():
    run = _on_box('printf "%s" "$DEPLOY_PATH"', "/opt/narrative-modeling-app/staging")
    assert (run.returncode, run.stdout) == (0, "/opt/narrative-modeling-app/staging")


def test_a_command_that_reads_stdin_cannot_eat_the_rest_of_the_body():
    """#756: fed to ``bash -s``, a ``docker compose exec`` in the body read the rest of
    the script from stdin and the run ended there with exit 0. The body is saved first
    and run with stdin at /dev/null, so this holds whatever the body calls."""
    run = _on_box("cat > /dev/null\necho after-the-reader\n", "/srv/app")
    assert (run.returncode, run.stdout.strip()) == (0, "after-the-reader")


def test_the_bodys_exit_code_comes_back():
    assert _on_box("echo before; exit 7; echo never", "/srv/app").returncode == 7
    assert _on_box("set -e; false; echo never", "/srv/app").returncode == 1


def test_a_repo_script_can_be_named_instead_of_piped():
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "body.sh"
        script.write_text('echo "in $DEPLOY_PATH"\n')
        run = _on_box("", "/srv/app", str(script))
        assert (run.returncode, run.stdout.strip()) == (0, "in /srv/app")


def test_it_refuses_to_run_without_knowing_where():
    with tempfile.TemporaryDirectory() as tmp:
        run = subprocess.run(
            ["bash", str(ON_BOX)],
            input="echo ran",
            env={"PATH": os.environ["PATH"], "HOME": tmp},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    assert run.returncode != 0
    assert "ran" not in run.stdout


def _run_blocks(path: Path) -> str:
    doc = yaml.safe_load(path.read_text())
    return "\n".join(
        step.get("run", "") for job in doc["jobs"].values() for step in job["steps"]
    )


def test_every_workflow_step_reaches_the_box_through_the_wrapper():
    """The reason this was worth fixing is that the unsafe shape was copied, not
    written. One shape, so the next step copies a safe one."""
    for workflow in WORKFLOWS:
        run = _run_blocks(workflow)
        assert "scripts/deploy/on_box.sh" in run, workflow.name
        raw = [line.strip() for line in run.splitlines() if re.match(r"\s*ssh\s", line)]
        assert not raw, f"{workflow.name} calls ssh itself: {raw}"
        assert "'$DEPLOY_PATH'" not in run, (
            f"{workflow.name} writes DEPLOY_PATH between quotes in a command string"
        )


def test_inline_bodies_are_quoted_heredocs():
    """An unquoted heredoc is expanded by the runner's shell before it is sent, which
    puts the value back into the text. Quoted, the body reaches the box as written and
    reads the variable there."""
    openers = {}
    for workflow in WORKFLOWS:
        # Anywhere on the line: one call has its redirects between the name and the `<<`.
        openers[workflow.name] = re.findall(r"on_box\.sh[^\n]*?<<\s*(\S+)", _run_blocks(workflow))
        for opener in openers[workflow.name]:
            assert opener.startswith("'"), f"{workflow.name}: heredoc {opener} is not quoted"
    # The three inline bodies this guards: deploy, its health gate, and the hourly probe.
    assert {name: len(found) for name, found in openers.items()} == {
        "deploy.yml": 2,
        "staging-health.yml": 1,
    }


def test_it_takes_one_script_or_none():
    run = _on_box("echo ran", "/srv/app", "one.sh", "two.sh")
    assert run.returncode == 2
    assert "ran" not in run.stdout
