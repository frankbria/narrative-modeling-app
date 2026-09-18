"""The NextAuth surface is rate-limited at the edge (#768 AC3).

`/api/auth/*` is served by Next.js, so the backend's `RateLimitMiddleware` (which
covers `/api/v1` only) never sees it, and the frontend has no limiter. nginx is the
one layer in front of every sign-in, callback and session poll, so the cap lives
there: a per-client-IP zone, with a burst that a human sign-in never reaches.

The repo file is not what runs (#456/#594) — this pins the repo copy; the box copy
ships with #594's deploy.
"""

import re

from tests.test_security.test_nginx_webhook_route import (
    NGINX_CONF,
    _location_blocks,
    _server_block,
)


def _zone() -> re.Match:
    m = re.search(
        r"^\s*limit_req_zone\s+\$binary_remote_addr\s+zone=(\w+):\d+m\s+rate=(\d+)r/([sm])\s*;",
        NGINX_CONF.read_text(),
        re.M,
    )
    assert m, "expected a per-client-IP `limit_req_zone $binary_remote_addr ...`"
    return m


def _auth_block() -> str:
    blocks = _location_blocks(_server_block())
    assert "/api/auth/" in blocks, "expected a `location /api/auth/` block"
    return blocks["/api/auth/"][0]


def test_zone_is_declared_at_http_level():
    # Outside every `server {}`: limit_req_zone is only valid in the http context,
    # and this file is included there from sites-enabled.
    text = NGINX_CONF.read_text()
    assert _zone().start() < text.index("server {")


def test_auth_location_applies_the_zone_with_a_burst():
    zone = _zone().group(1)
    m = re.search(rf"^\s*limit_req\s+zone={zone}\s+burst=(\d+)(\s+nodelay)?\s*;", _auth_block(), re.M)
    assert m, f"`location /api/auth/` must apply `limit_req zone={zone} burst=N`"
    # A sign-in is a handful of requests (providers, csrf, signin, callback,
    # session); NextAuth also polls the session on focus. The burst absorbs that.
    assert int(m.group(1)) >= 20


def test_rate_is_generous_for_humans_and_finite_for_scripts():
    _, rate, unit = _zone().groups()
    per_minute = int(rate) * (60 if unit == "s" else 1)
    assert 10 <= per_minute <= 120


def test_refusals_are_429_not_503():
    # nginx's default refusal status is 503, which reads as an outage to monitors
    # and to NextAuth's client; 429 is what it is.
    assert re.search(r"^\s*limit_req_status\s+429\s*;", _auth_block(), re.M)
