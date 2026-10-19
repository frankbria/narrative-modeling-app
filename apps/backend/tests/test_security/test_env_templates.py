"""The env templates mirror each other, so a variable cannot be added to one alone (#1074).

That is how they drifted before #1075: `SIGNUP_MODE`, which compose requires, was
added to `.env.staging.example` only, so `.env.production.example` silently lacked
it. And a `NEXTAUTH_SECRET` placeholder that differs between the two local templates
makes a freshly copied local stack answer 401 on every API call.

These read the REAL files, like `test_staging_signup_env.py`.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "docker-compose.staging.yml"
STAGING = REPO_ROOT / ".env.staging.example"
PRODUCTION = REPO_ROOT / ".env.production.example"
BACKEND_LOCAL = REPO_ROOT / "apps/backend/.env.example"
FRONTEND_LOCAL = REPO_ROOT / "apps/frontend/.env.local.example"

ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _values(path: Path) -> dict[str, str]:
    lines = path.read_text().splitlines()
    return dict(m.groups() for m in map(ASSIGNMENT.match, lines) if m)


def test_the_deployed_templates_declare_the_same_names_in_the_same_order():
    assert list(_values(STAGING)) == list(_values(PRODUCTION))


def test_the_deployed_templates_hold_exactly_what_compose_interpolates():
    code = [line for line in COMPOSE_FILE.read_text().splitlines() if not line.lstrip().startswith("#")]
    interpolated = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", "\n".join(code)))
    # Read by scripts/deploy/apply_nginx_conf.sh, not by compose; NGINX_CERT_DIR is optional there.
    assert set(_values(STAGING)) - {"NGINX_CERT_DIR"} == interpolated | {"NGINX_SERVER_NAME"}


def test_a_variable_both_local_templates_declare_has_one_value():
    backend, frontend = _values(BACKEND_LOCAL), _values(FRONTEND_LOCAL)
    shared = backend.keys() & frontend.keys()
    assert {"MONGODB_URI", "MONGODB_DB", "NEXTAUTH_SECRET", "SIGNUP_MODE"} <= shared
    assert {k: backend[k] for k in shared} == {k: frontend[k] for k in shared}
