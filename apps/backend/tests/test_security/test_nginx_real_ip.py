"""Regression guard: nginx and the rate limiter must agree on the client-IP header.

Issue #483 (P1.8): the limiter read ``X-Forwarded-For[0]``. nginx *appends* to that
header (``$proxy_add_x_forwarded_for``), so element ``[0]`` is whatever the client
sent — a caller varying a spoofed XFF minted a fresh bucket per request, and the
global ``/api/v1`` limiter enforced nothing. The fix reads ``X-Real-IP`` instead,
which nginx sets from ``$remote_addr`` and *overwrites*, so behind the proxy it is
authoritative. That only holds while two files stay in step:

* every ``location`` that proxies to the backend upstream sets
  ``proxy_set_header X-Real-IP $remote_addr`` — drop it from one block and the
  limiter there sees the raw client header again; and
* the staging compose passes ``RATE_LIMIT_TRUST_PROXY: "true"`` to the backend.
  Compose is the contract (#457): without the line, staging runs with the flag off
  and every anonymous request behind nginx shares nginx's container IP as its bucket.

The parser is the text-based one from ``test_nginx_webhook_route`` — same file, same
limits (flat config, one directive per line, no ``include``).
"""

import re

import yaml

from tests.test_security.test_nginx_webhook_route import (
    NGINX_CONF,
    REPO_ROOT,
    _location_blocks,
    _server_block,
)

COMPOSE_FILE = REPO_ROOT / "docker-compose.staging.yml"


def _backend_upstream() -> str:
    m = re.search(r"^\s*upstream\s+(\S*backend\S*)\s*\{", NGINX_CONF.read_text(), re.M)
    assert m, "expected an `upstream ...backend...` block"
    return m.group(1)


def _backend_locations() -> dict[str, str]:
    upstream = _backend_upstream()
    return {
        match: body
        for match, (body, _) in _location_blocks(_server_block()).items()
        if re.search(rf"^\s*proxy_pass\s+http://{re.escape(upstream)}\b", body, re.M)
    }


class TestNginxSetsRealIp:
    def test_backend_locations_exist(self):
        assert _backend_locations(), "no location proxies to the backend upstream"

    def test_every_backend_location_overwrites_x_real_ip(self):
        missing = [
            match
            for match, body in _backend_locations().items()
            if not re.search(
                r"^\s*proxy_set_header\s+X-Real-IP\s+\$remote_addr\s*;", body, re.M
            )
        ]
        assert not missing, (
            "these backend locations do not set `X-Real-IP $remote_addr`, so the "
            f"rate limiter behind them keys on a client-supplied header (#483): {missing}"
        )


class TestComposeTrustsProxy:
    def test_backend_receives_trust_proxy_flag(self):
        compose = yaml.safe_load(COMPOSE_FILE.read_text())
        env = compose["services"]["backend"]["environment"]
        assert str(env.get("RATE_LIMIT_TRUST_PROXY", "")).strip().lower() == "true", (
            "docker-compose.staging.yml must pass RATE_LIMIT_TRUST_PROXY=true to the "
            "backend, or every anonymous request behind nginx shares one bucket (#483)"
        )
