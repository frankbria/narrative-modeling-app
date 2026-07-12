"""Regression guard: staging compose must publish host ports on loopback only.

Issue #258 (P0.8): `ports: "8010:8000"` / `"3011:3000"` / `"6381:6379"` bound
every published port to 0.0.0.0, so on the shared VPS the API/app/redis were
reachable over plaintext HTTP at the host IP — bypassing nginx TLS/HSTS/security
headers (nginx upstreams to 127.0.0.1). Docker's iptables DNAT rules are also
evaluated before UFW, so a 0.0.0.0 publish leaks even when the firewall doesn't
`allow` the port. Binding the host side to 127.0.0.1 is the control that holds.

These tests parse the real compose file (not a fixture) so re-exposing any port
fails the build.
"""

from pathlib import Path

import yaml

# apps/backend/tests/test_security/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "docker-compose.staging.yml"


def _published_ports() -> list[tuple[str, str]]:
    """Yield (service_name, port_mapping) for every published port."""
    compose = yaml.safe_load(COMPOSE_FILE.read_text())
    published = []
    for name, service in compose.get("services", {}).items():
        for mapping in service.get("ports", []) or []:
            published.append((name, str(mapping)))
    return published


def test_compose_file_exists():
    assert COMPOSE_FILE.is_file(), f"missing {COMPOSE_FILE}"


def test_all_published_ports_bind_loopback():
    ports = _published_ports()
    assert ports, "expected staging services to publish ports"
    offenders = [
        (svc, m) for svc, m in ports if not m.startswith("127.0.0.1:")
    ]
    assert not offenders, (
        "staging published ports must bind to 127.0.0.1 (loopback) so the shared "
        f"VPS doesn't expose them past nginx: {offenders}"
    )


def test_expected_services_published():
    """The three host ports nginx/redis rely on are still published."""
    mappings = {m for _, m in _published_ports()}
    for expected in ("127.0.0.1:8010:8000", "127.0.0.1:3011:3000", "127.0.0.1:6381:6379"):
        assert expected in mappings, f"expected published port {expected}, got {mappings}"


def test_backend_healthcheck_uses_readiness_not_liveness():
    """Issue #273: the backend healthcheck must hit /health/ready (503 when Mongo
    is down) so a broken container isn't reported healthy while serving 500s."""
    compose = yaml.safe_load(COMPOSE_FILE.read_text())
    backend = compose["services"]["backend"]
    test_cmd = " ".join(backend["healthcheck"]["test"])
    assert "/health/ready" in test_cmd, (
        f"backend healthcheck should target /health/ready, got: {test_cmd}"
    )


def test_dockerfile_healthcheck_uses_readiness():
    """Issue #273: the image-level HEALTHCHECK must also target /health/ready."""
    dockerfile = (REPO_ROOT / "apps" / "backend" / "Dockerfile").read_text()
    healthcheck_lines = [
        ln for ln in dockerfile.splitlines() if "localhost:8000/health" in ln
    ]
    assert healthcheck_lines, "expected a HEALTHCHECK curl to localhost:8000"
    assert all("/health/ready" in ln for ln in healthcheck_lines), (
        f"Dockerfile HEALTHCHECK should target /health/ready, got: {healthcheck_lines}"
    )


def test_redis_healthcheck_authenticated():
    """Issue #277 (P1.14): redis runs with --requirepass, so an unauthenticated
    healthcheck (`redis-cli --raw incr ping`) either blocks depends_on forever or
    false-passes. The probe must authenticate with the same password."""
    compose = yaml.safe_load(COMPOSE_FILE.read_text())
    redis = compose["services"]["redis"]
    assert "--requirepass" in " ".join(
        redis["command"] if isinstance(redis["command"], list) else [redis["command"]]
    ), "expected redis to require a password"
    test_cmd = " ".join(redis["healthcheck"]["test"])
    assert "-a" in redis["healthcheck"]["test"] and "REDIS_PASSWORD" in test_cmd, (
        f"redis healthcheck must authenticate with -a $REDIS_PASSWORD, got: {test_cmd}"
    )


def test_frontend_dockerfile_node_major_matches_ci():
    """Issue #277 (P1.14): the frontend production image must run the same Node
    major CI builds/tests on (Node 20), not an untested major. Guards the FROM
    tag *and* the pin comment against drifting back to node:26."""
    dockerfile = (REPO_ROOT / "apps" / "frontend" / "Dockerfile").read_text()
    from_lines = [ln for ln in dockerfile.splitlines() if ln.startswith("FROM node:")]
    assert from_lines, "expected FROM node: lines in the frontend Dockerfile"
    assert all("node:20-alpine" in ln for ln in from_lines), (
        f"frontend image must use node:20-alpine (CI runs Node 20), got: {from_lines}"
    )
    assert "node:26" not in dockerfile, "stale node:26 reference in frontend Dockerfile"
