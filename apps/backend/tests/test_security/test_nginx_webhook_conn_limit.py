"""The Stripe webhook has a connection cap at the edge, and still no rate limit (#595).

`POST /webhooks/stripe/webhook` is unauthenticated and, by design, has no `limit_req`:
Stripe delivers every tenant's events from a few addresses, so a request-rate budget
throttles Stripe itself (#367). `client_max_body_size` bounds one request; what was
left unbounded is how many of them one client can hold open at once.

`limit_conn` is the control that fits: it counts requests in flight per client
address, not requests per second, so a burst of short deliveries passes however fast
it arrives. These tests pin the cap, the status a refused request gets (Stripe must
see a failure it retries), and that nobody "simplifies" it into `limit_req`.

Text-based like `test_nginx_webhook_route.py` (CI has no nginx binary).
"""

import re

from tests.test_security.test_nginx_webhook_route import (
    NGINX_CONF,
    _location_blocks,
    _server_block,
    _webhook_location,
)

#: Requests one client address may have in flight on the webhook, pinned to what ships.
#: A delivery is in flight for milliseconds, so 20 at once from a single Stripe address
#: is far beyond a real burst, and 20 bodies of at most 2 MB is what one abuser can make
#: the backend hold. A different cap is a deliberate edit of the config and of this line.
WEBHOOK_CONNECTION_CAP = 20


def _zone() -> re.Match[str]:
    declared = re.search(
        r"^\s*limit_conn_zone\s+(\S+)\s+zone=(\w+):\d+[km]\s*;", NGINX_CONF.read_text(), re.M
    )
    assert declared, "expected a `limit_conn_zone <key> zone=<name>:<size>;`"
    return declared


def _webhook_cap() -> re.Match[str]:
    match, body, _ = _webhook_location()
    applied = re.search(r"^\s*limit_conn\s+(\w+)\s+(\d+)\s*;", body, re.M)
    assert applied, f"location {match} must apply `limit_conn <zone> <n>;`"
    return applied


def _note_above_the_webhook_location() -> str:
    """The comment lines directly above the webhook's `location`, joined."""
    _, _, offset = _webhook_location()
    lines = _server_block()[:offset].rstrip().splitlines()
    note: list[str] = []
    while lines and lines[-1].lstrip().startswith("#"):
        note.append(lines.pop().strip().lstrip("#").strip())
    return " ".join(reversed(note))


def test_zone_is_keyed_on_the_client_address():
    # Per client, not one total for the location: a shared total is a switch any
    # single abuser can hold down to make nginx refuse Stripe.
    assert _zone().group(1) == "$binary_remote_addr"


def test_zone_is_declared_at_http_level():
    # limit_conn_zone is only valid in the http context, which is where this file is
    # included from sites-enabled, so it must sit outside every `server {}`.
    text = NGINX_CONF.read_text()
    assert _zone().start() < text.index("server {")


def test_webhook_location_applies_the_declared_zone_at_the_pinned_cap():
    zone, cap = _webhook_cap().groups()
    assert zone == _zone().group(2), f"`limit_conn {zone}` names a zone that is not declared"
    assert int(cap) == WEBHOOK_CONNECTION_CAP, (
        f"the cap is {cap}, not the pinned {WEBHOOK_CONNECTION_CAP}. "
        "Change both together if the cap is meant to move."
    )


def test_no_other_location_counts_against_the_webhook_zone():
    # A zone applied in two locations is one shared count per client, so traffic to
    # the other location would use up the webhook's cap.
    zone = _zone().group(2)
    users = [
        match
        for match, (body, _) in _location_blocks(_server_block()).items()
        if re.search(rf"^\s*limit_conn\s+{zone}\s", body, re.M)
    ]
    assert users == [_webhook_location()[0]]


def test_a_refused_request_is_answered_503():
    # Stripe retries any non-2xx, so a refusal is never a lost event; 503 says "busy,
    # come back" rather than 4xx's "your request is wrong". It is nginx's default,
    # stated in the block so the default is not what the retry depends on.
    _, body, _ = _webhook_location()
    statuses = re.findall(r"^\s*limit_conn_status\s+(\d+)\s*;", body, re.M)
    assert statuses == ["503"]


def test_webhook_location_still_has_no_request_rate_limit():
    # #367: an address budget throttles Stripe's small delivery pool, and the retries
    # land in the same bucket.
    match, body, _ = _webhook_location()
    assert not re.search(r"^\s*limit_req\b", body, re.M), (
        f"location {match} must not carry `limit_req`: it would 429/503 Stripe itself (#367)"
    )


def test_the_block_explains_why_one_limit_and_not_the_other():
    # The note is what stops a future editor replacing the connection cap with a
    # request-rate limit, or deleting it as inconsistent with "no limit_req here".
    note = _note_above_the_webhook_location()
    for required in ("limit_conn", "limit_req", "#367", "#595"):
        assert required in note, f"the comment above the webhook location must mention {required}"
