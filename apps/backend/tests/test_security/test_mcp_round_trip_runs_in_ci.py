"""#998: the backend-to-MCP SSE round trip runs in the required integration job.

`test_mcp_integration_sse_localstack.py` is the only suite that connects the backend's
MCP client to the real server. It needs `apps/mcp`'s environment, which the job did not
sync, so it skipped on every run and an `mcp` bump in either app could break the
connection with CI green. These pin the three things that keep it running.
"""

from pathlib import Path

import yaml

# apps/backend/tests/test_security/ -> repo root
REPO = Path(__file__).resolve().parents[4]
SUITE = REPO / "apps" / "backend" / "tests" / "test_integration" / "test_mcp_integration_sse_localstack.py"


def _job(name: str) -> dict:
    return yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())["jobs"][name]


def test_the_integration_job_syncs_the_mcp_app_before_its_tests():
    steps = _job("backend-integration")["steps"]
    names = [step.get("name", "") for step in steps]
    sync = next(
        i for i, step in enumerate(steps)
        if step.get("working-directory") == "apps/mcp" and "uv sync" in step.get("run", "")
    )
    tests = next(i for i, name in enumerate(names) if name.startswith("Run integration tests"))

    assert sync < tests
    assert steps[tests]["env"]["CI_REQUIRE_SERVICES"] == "true"


def test_the_round_trip_cannot_skip_quietly():
    source = SUITE.read_text()

    assert "pytest.skip(" not in source, "a plain skip passes CI_REQUIRE_SERVICES by; use require_service"
    assert "require_service(" in source


def test_ci_success_waits_for_the_integration_job():
    assert "backend-integration" in _job("ci-success")["needs"]
