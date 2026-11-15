"""#1243: the E2E backend holds no OpenAI client.

With a dummy `OPENAI_API_KEY` the E2E backend built a real client, sent every summary
the specs triggered to api.openai.com, waited for the 401 and only then fell back (22
`Error calling OpenAI API` lines in CI run 43693904859). A blank key gives every service
no client, so the specs exercise the rule-based fallback, as the pytest suite does
(#1089). The backend loads `apps/backend/.env` without override, so an exported blank
value also beats a key in a developer's `.env`.
"""

import re
from pathlib import Path

import pytest
import yaml

# apps/backend/tests/test_security/ -> repo root
REPO = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO / ".github" / "workflows"
RUNNER_SCRIPT = REPO / "apps" / "frontend" / "test-e2e.sh"

KEY = "OPENAI_API_KEY"
BACKEND_START = "uvicorn app.main:app"

E2E_JOBS = [
    pytest.param("ci.yml", "e2e-smoke", id="smoke"),
    pytest.param("e2e-tests.yml", "e2e-full-suite", id="nightly"),
]


def _env_blocks(workflow: str, job: str) -> list[tuple[str, dict]]:
    """Every `env:` that reaches the job's steps: the workflow's, the job's, each step's."""
    document = yaml.safe_load((WORKFLOWS / workflow).read_text())
    job_definition = document["jobs"][job]
    blocks = [
        ("workflow", document.get("env") or {}),
        ("job", job_definition.get("env") or {}),
    ]
    blocks += [
        (f"step {step.get('name', index)!r}", step.get("env") or {})
        for index, step in enumerate(job_definition["steps"])
    ]
    return blocks


@pytest.mark.parametrize(("workflow", "job"), E2E_JOBS)
def test_no_e2e_job_gives_the_backend_an_openai_key(workflow, job):
    given = {
        where: env[KEY]
        for where, env in _env_blocks(workflow, job)
        if KEY in env and str(env[KEY]).strip()
    }
    assert given == {}, f"{workflow} {job} sets a non-blank {KEY}: {given}"


@pytest.mark.parametrize(("workflow", "job"), E2E_JOBS)
def test_no_e2e_step_writes_the_key_from_a_script(workflow, job):
    """A `run:` line could export it or append it to $GITHUB_ENV, past the env check."""
    steps = yaml.safe_load((WORKFLOWS / workflow).read_text())["jobs"][job]["steps"]
    naming = [step.get("name") for step in steps if KEY in step.get("run", "")]
    assert naming == []


def _assignments() -> list[tuple[int, str]]:
    """Each line of the runner script that sets the key, with its line number."""
    return [
        (number, line.strip())
        for number, line in enumerate(RUNNER_SCRIPT.read_text().splitlines())
        if re.search(rf"\b{KEY}=", line)
    ]


def test_the_runner_script_exports_a_blank_key_and_nothing_else():
    """Unconditionally: `${OPENAI_API_KEY:-dummy}` turned a blank value back into a key,
    and `unset` would let the backend read a developer's `.env` key."""
    assert [line for _, line in _assignments()] == [f"export {KEY}="]
    assert not re.search(rf"\bunset\b.*\b{KEY}\b", RUNNER_SCRIPT.read_text())


def test_the_blank_key_is_exported_before_the_backend_starts():
    lines = RUNNER_SCRIPT.read_text().splitlines()
    backend_start = next(
        number for number, line in enumerate(lines) if BACKEND_START in line
    )
    assert all(number < backend_start for number, _ in _assignments())
