"""#571: a reviewer that never started must not pass for a clean review.

A `startup_failure` creates no job, so the reviewer's own workflow cannot report it.
GLM Review sat that way for 266 runs. `scripts/ci/review_bots_health.sh` looks from
outside on a schedule; these pin the wiring it depends on, and the two changes to the
reviewer's workflow that came with it (#576, #577).
"""

import subprocess
from pathlib import Path

import yaml

# apps/backend/tests/test_security/ -> repo root
REPO = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO / ".github" / "workflows"
SCRIPT = REPO / "scripts" / "ci" / "review_bots_health.sh"


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def test_the_verdict_case_table_passes():
    result = subprocess.run([str(SCRIPT), "--self-check"], capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr


def test_the_watcher_runs_on_a_schedule_with_the_permissions_it_uses():
    watcher = _workflow("review-bots-health.yml")

    assert watcher[True]["schedule"], "PyYAML reads the `on:` key as True"
    # Reading run conclusions and opening an issue; nothing else.
    assert watcher["permissions"] == {"contents": "read", "actions": "read", "issues": "write"}


def test_every_reviewer_workflow_is_watched():
    script = SCRIPT.read_text()

    for name in ("glm-review.yml", "claude-code-review.yml"):
        assert (WORKFLOWS / name).exists(), f"{name} was renamed or removed: update WORKFLOWS in the script"
        assert name in script


def test_the_alert_is_found_again_after_the_operator_retitles_it():
    """The search is the stable phrase, never the full title with its priority (#757)."""
    search = next(line for line in SCRIPT.read_text().splitlines() if line.strip().startswith("search="))

    assert "$PHRASE" in search and "[P" not in search


def test_glm_review_keeps_its_two_invariants_and_has_no_size_gate():
    caller = _workflow("glm-review.yml")
    job = caller["jobs"]["review"]

    assert "concurrency" not in caller, "a caller-level group makes the called workflow cancel its parent"
    assert job["permissions"] == {"contents": "read", "pull-requests": "write"}
    assert "changed_files" not in job["if"] and "additions" not in job["if"], "the size gate (#576)"


def test_claude_review_runs_only_where_its_token_exists():
    # A Dependabot-triggered run gets Dependabot's secrets, not the repository's, so the
    # review started with an empty token and failed on every dependency PR (#555).
    job = _workflow("claude-code-review.yml")["jobs"]["claude-review"]

    assert job["if"] == "github.event.pull_request.user.type == 'User'"
