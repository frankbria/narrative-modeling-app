"""#1233: a failed E2E run keeps what the servers printed.

The backend in CI run 43670042389 stopped answering mid-run, and nothing showed why:
`test-e2e.sh` writes both servers' output to files that died with the runner. Both E2E
jobs now upload those files when the suite fails. The artifact is as public as the run,
so these also pin that no secret reaches the servers.
"""

import re
from pathlib import Path

import pytest
import yaml

# apps/backend/tests/test_security/ -> repo root
REPO = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO / ".github" / "workflows"
RUNNER_SCRIPT = REPO / "apps" / "frontend" / "test-e2e.sh"

# A hang can also run the job into its timeout-minutes, which cancels it.
ON_FAILURE = "failure() || cancelled()"

# Any reference to the context, not only `secrets.NAME`: `secrets['NAME']` and
# `toJSON(secrets)` read it too, and expression names ignore case.
SECRETS_CONTEXT = re.compile(r"\bsecrets\b", re.IGNORECASE)
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)
# The only expressions an E2E job may evaluate before its logs are uploaded. Any
# other can carry a token to the servers: env at any level, `container`, a step
# input, or a value an earlier step writes to $GITHUB_ENV.
HARMLESS_EXPRESSIONS = {"runner.os", "hashFiles('apps/frontend/package-lock.json')"}

E2E_JOBS = [
    pytest.param("ci.yml", "e2e-smoke", "Run Smoke Tests", id="smoke"),
    pytest.param("e2e-tests.yml", "e2e-full-suite", "Run E2E Full Suite", id="nightly"),
]


def _steps(workflow: str, job: str) -> list[dict]:
    return yaml.safe_load((WORKFLOWS / workflow).read_text())["jobs"][job]["steps"]


def _index_of_step(steps: list[dict], name: str) -> int:
    return next(index for index, step in enumerate(steps) if step.get("name") == name)


def _server_log_paths() -> set[str]:
    """The files `test-e2e.sh` sends each server's output to."""
    return set(
        re.findall(r">>?\s*(/tmp/\S+\.log)\s+2>&1\s*&", RUNNER_SCRIPT.read_text())
    )


def _uploaded_paths(step: dict) -> set[str]:
    return set(step["with"]["path"].split())


def _log_upload(steps: list[dict]) -> tuple[int, dict]:
    server_logs = _server_log_paths()
    return next(
        (index, step)
        for index, step in enumerate(steps)
        if "upload-artifact" in step.get("uses", "")
        and server_logs <= _uploaded_paths(step)
    )


def test_the_runner_script_still_writes_both_server_logs():
    assert _server_log_paths() == {"/tmp/backend-e2e.log", "/tmp/frontend-e2e.log"}


GUIDE = Path("docs") / "dev" / "E2E_TESTING_GUIDE.md"


@pytest.mark.parametrize(
    ("workflow", "job", "artifact", "cited_in"),
    [
        ("ci.yml", "e2e-smoke", "smoke-server-logs", [Path("CLAUDE.md"), GUIDE]),
        ("e2e-tests.yml", "e2e-full-suite", "e2e-full-server-logs", [GUIDE]),
    ],
)
def test_the_artifact_keeps_the_name_the_docs_give_it(
    workflow: str, job: str, artifact: str, cited_in: list[Path]
):
    _, upload = _log_upload(_steps(workflow, job))

    assert upload["with"]["name"] == artifact
    for document in cited_in:
        assert artifact in (REPO / document).read_text(), (
            f"{document} no longer names {artifact}"
        )


def test_the_backend_log_is_appended_to_so_the_probe_line_is_not_overwritten():
    """`>` would keep uvicorn's own write offset, and its shutdown lines would land on the probe line."""
    assert re.search(
        r">>\s*/tmp/backend-e2e\.log\s+2>&1\s*&", RUNNER_SCRIPT.read_text()
    )


@pytest.mark.parametrize(("workflow", "job", "suite"), E2E_JOBS)
def test_the_server_logs_are_uploaded_when_the_suite_fails(
    workflow: str, job: str, suite: str
):
    steps = _steps(workflow, job)

    index, upload = _log_upload(steps)

    assert index > _index_of_step(steps, suite)
    assert upload["if"] == ON_FAILURE


@pytest.mark.parametrize(("workflow", "job", "suite"), E2E_JOBS)
def test_the_localstack_output_is_saved_before_the_upload(
    workflow: str, job: str, suite: str
):
    steps = _steps(workflow, job)
    upload_index, upload = _log_upload(steps)
    capture_index = next(
        index
        for index, step in enumerate(steps)
        if "docker logs narrative-localstack-test" in step.get("run", "")
        and "> /tmp/localstack-e2e.log" in step["run"]
    )

    assert _index_of_step(steps, suite) < capture_index < upload_index
    assert steps[capture_index]["if"] == ON_FAILURE
    assert "/tmp/localstack-e2e.log" in _uploaded_paths(upload)


@pytest.mark.parametrize(("workflow", "job", "suite"), E2E_JOBS)
def test_the_logs_use_the_same_pinned_upload_action_as_the_report(
    workflow: str, job: str, suite: str
):
    steps = _steps(workflow, job)
    _, upload = _log_upload(steps)
    report = next(
        step
        for step in steps
        if "playwright-report" in step.get("with", {}).get("path", "")
    )

    assert upload["uses"] == report["uses"]
    assert upload["with"]["retention-days"] == report["with"]["retention-days"]


def _strings(node: object) -> list[str]:
    if isinstance(node, dict):
        return [
            text
            for key, value in node.items()
            for text in _strings(key) + _strings(value)
        ]
    if isinstance(node, list):
        return [text for item in node for text in _strings(item)]
    return [node] if isinstance(node, str) else []


@pytest.mark.parametrize(("workflow", "job", "suite"), E2E_JOBS)
def test_no_secret_reaches_the_servers_whose_logs_are_published(
    workflow: str, job: str, suite: str
):
    definition = yaml.safe_load((WORKFLOWS / workflow).read_text())
    job_definition = definition["jobs"][job]
    upload_index, _ = _log_upload(job_definition["steps"])
    up_to_the_upload = [
        definition.get("env", {}),
        {key: value for key, value in job_definition.items() if key != "steps"},
        job_definition["steps"][: upload_index + 1],
    ]
    expressions = {
        " ".join(found.split())
        for text in _strings(up_to_the_upload)
        for found in EXPRESSION.findall(text)
    }

    assert not SECRETS_CONTEXT.search(yaml.safe_dump(job_definition))
    assert expressions <= HARMLESS_EXPRESSIONS, (
        f"not allowed before the upload: {expressions - HARMLESS_EXPRESSIONS}"
    )
