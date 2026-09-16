"""Demo helper for #552 (run from the repo root).

Default: per-secret consumers derived from the real compose file, checked against
the rotation runbook. ``--workflow``: the parsed triggers, permissions and steps of
the scheduled health workflow.
"""

import re
import sys
from pathlib import Path

import yaml


def consumers() -> None:
    compose = Path("docker-compose.staging.yml").read_text()
    runbook = Path("docs/operations/CREDENTIAL_ROTATION.md").read_text()
    backend, _, frontend = compose.partition("\n  frontend:")
    secrets = sorted(
        {
            v
            for v in re.findall(r"\$\{([A-Z][A-Z0-9_]+)", compose)
            if re.search(r"SECRET|KEY|PASSWORD|URI|TOKEN|DSN", v)
        }
    )
    print(f"{'secret':24s} backend frontend in-runbook")
    for v in secrets:
        in_backend = "yes" if v in backend else "no "
        in_frontend = "yes" if v in frontend else "no "
        in_runbook = "yes" if f"`{v}`" in runbook else "NO"
        print(f"{v:24s} {in_backend:7s} {in_frontend:8s} {in_runbook}")


def workflow() -> None:
    wf = yaml.safe_load(Path(".github/workflows/staging-health.yml").read_text())
    triggers = wf.get("on") or wf[True]  # PyYAML reads a bare `on:` key as True
    print("triggers:", triggers)
    print("permissions:", wf["permissions"])
    for step in wf["jobs"]["probe"]["steps"]:
        print("step:", step["name"], "| if:", step.get("if", "-"))


if __name__ == "__main__":
    workflow() if "--workflow" in sys.argv else consumers()
