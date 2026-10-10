"""Staging must be told its signup mode, and only invite mode needs an allowlist (#780).

`SIGNUP_MODE` was an optional passthrough: blank resolved to `invite`, so the only
sign the mode was deliberate was a startup log line. Compose now refuses to start
without it. `INVITE_ALLOWLIST` goes the other way: guarded with `${VAR:?}` it would
force a dummy value on the day signup opens, so the "invite needs a list" rule lives
in `scripts/deploy/preflight_staging_env.sh`, which can read the mode (its
`--self-check` covers that rule; CI runs it).

These parse the REAL compose file and env example, like `test_staging_billing_env.py`.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "docker-compose.staging.yml"
STAGING_ENV_EXAMPLE = REPO_ROOT / ".env.staging.example"

# Both halves read the mode (`resolve_signup_mode` / `resolveSignupMode`).
SERVICES = ("backend", "frontend")


def _environment(service: str) -> dict[str, str]:
    env = yaml.safe_load(COMPOSE_FILE.read_text())["services"][service]["environment"]
    return {k: "" if v is None else str(v) for k, v in env.items()}


@pytest.mark.parametrize("service", SERVICES)
def test_signup_mode_is_required(service):
    assert _environment(service)["SIGNUP_MODE"].startswith("${SIGNUP_MODE:?"), (
        f"{service} must refuse to start without an explicit SIGNUP_MODE"
    )


@pytest.mark.parametrize("service", SERVICES)
def test_open_mode_needs_no_dummy_allowlist(service):
    value = _environment(service)["INVITE_ALLOWLIST"]
    assert value.startswith("${INVITE_ALLOWLIST") and ":?" not in value, (
        f"{service} guards INVITE_ALLOWLIST unconditionally ({value!r}); the preflight "
        "requires it in invite mode only, so SIGNUP_MODE=open needs no placeholder list"
    )


def test_the_example_env_carries_a_valid_mode():
    modes = [
        line.split("=", 1)[1].strip()
        for line in STAGING_ENV_EXAMPLE.read_text().splitlines()
        if line.startswith("SIGNUP_MODE=")
    ]
    assert modes == ["invite"], (
        "a box provisioned from .env.staging.example must pass the preflight and "
        f"start invite-only, got {modes}"
    )
