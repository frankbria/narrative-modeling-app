"""Regression guard: the Stripe webhook path must be proxied to the backend.

Issue #456 (P0.13): the backend deliberately mounts the webhook OUTSIDE
``/api/v1`` (``app/main.py``) so ``RateLimitMiddleware`` cannot 429 Stripe's small
IP pool (#367). ``nginx-staging.conf`` only had ``location /api/`` and
``location /``, so every ``checkout.session.completed`` and
``customer.subscription.*`` event fell through to Next.js — in practice a 307 to
the sign-in page — and never reached the handler. A customer could pay and never
become entitled, and a cancellation never revoked.

Three properties have to hold, not one:

* the path is routed to the **backend**, and to the backend nginx would actually
  pick (longest prefix, and no regex location that outranks it);
* nothing on the path **rewrites the request**. ``verify_signature`` HMACs the exact
  bytes, so a ``proxy_set_body``/``rewrite``, or a ``proxy_pass`` carrying a URI,
  breaks it even once routing works; and
* the endpoint is **unauthenticated**, so the edge caps the body. The backend's
  ``BodySizeLimitMiddleware`` only inspects a *declared* ``Content-Length``, so a
  chunked body skips it and ``await request.body()`` buffers whatever arrives —
  before any signature check. ``client_max_body_size`` is the control that binds.

Note what is deliberately NOT asserted: ``proxy_request_buffering off`` is not
required for byte-exactness. Buffering changes framing, never bytes.

These tests parse the real config file and the real router mount, so the two cannot
drift apart silently.

The parser is text-based rather than `nginx -T`, since CI has no nginx binary. That
is fine for this file — flat, self-contained, one directive per line — but it would
not follow an `include`d location fragment or a directive split across lines. If the
config is ever restructured that way, this needs a real parser, not more regexes.
"""

import re
from pathlib import Path

# apps/backend/tests/test_security/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]
NGINX_CONF = REPO_ROOT / "nginx-staging.conf"
MAIN_PY = REPO_ROOT / "apps" / "backend" / "app" / "main.py"

#: Directives that would change the REQUEST nginx forwards. Response-side rewriters
#: (`sub_filter`, `charset`) are irrelevant here — the HMAC covers the request.
REQUEST_ALTERING_DIRECTIVES = ("proxy_set_body", "rewrite")

#: The cap on the webhook's request body, pinned to what ships (#596). Stripe events are
#: a few KB, so 2 MB is already three orders of magnitude of room, and anything near the
#: server-wide 100M on an unauthenticated endpoint is a free memory-pressure lever. This
#: used to be a band (anything up to 8M passed) with no reason given for the 8. A
#: different cap is a deliberate edit of the config and of this line together.
WEBHOOK_BODY_CAP = "2m"


def _block_end(text: str, start: int) -> int:
    """The offset just past the brace that closes the block opened before ``start``."""
    depth, i = 1, start
    while depth and i < len(text):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return i


def _server_block() -> str:
    """The body of the HTTPS server block — the one that terminates real traffic.

    Exactly that block, not "from `listen 443` to the end of the file" (#596). nginx
    only ever compares the locations of one server, so a server appended later (a
    metrics listener, a second domain) must not have its locations weighed against
    this one's: that reads as a false green when the other block happens to route the
    path correctly, and as a false red when it holds a longer unrelated location.
    """
    text = NGINX_CONF.read_text()
    servers = [
        text[m.end() : _block_end(text, m.end()) - 1]
        for m in re.finditer(r"^server\s*\{", text, re.M)
    ]
    tls = [body for body in servers if re.search(r"^\s*listen\s+(\[::\]:)?443\b", body, re.M)]
    assert len(tls) == 1, (
        f"expected exactly one server block listening on 443, found {len(tls)} "
        f"(of {len(servers)} server blocks). With more than one, decide which serves the "
        "webhook's host and scope this guard to it by server_name."
    )
    return tls[0]


def _location_blocks(text: str) -> dict[str, tuple[str, int]]:
    """Map each ``location <match>`` to its (brace-balanced body, start offset)."""
    blocks: dict[str, tuple[str, int]] = {}
    for m in re.finditer(r"^[^\S\n]*location\s+([^\s{]+(?:\s+[^\s{]+)?)\s*\{", text, re.M):
        blocks[m.group(1).strip()] = (text[m.end() : _block_end(text, m.end()) - 1], m.start())
    return blocks


def _webhook_mount_prefix() -> str:
    """The prefix ``main.py`` actually mounts the webhook router under.

    Insists there is exactly one. Taking the first of several would silently guard
    one webhook path while a second went unrouted — the #456 failure, green.
    """
    found = re.findall(r'prefix="(/webhooks/[^"]*)"', MAIN_PY.read_text())
    assert found, "expected main.py to mount a /webhooks/... router prefix"
    assert len(found) == 1, (
        f"main.py mounts {len(found)} /webhooks/ prefixes {found}; this guard only "
        "covers one. Parameterise it over all of them before adding another."
    )
    return found[0]


def _webhook_path() -> str:
    """A concrete path the webhook serves, for testing nginx's matching."""
    return f"{_webhook_mount_prefix()}/webhook"


def _webhook_location() -> tuple[str, str, int]:
    """The location covering the webhook mount, as (match, body, offset).

    Picks the LONGEST matching prefix, because that is what nginx does. Taking the
    first in file order would let a broad ``location /webhooks/`` pointing at the
    frontend pass this suite while nginx routes past it — the #456 failure mode,
    green.
    """
    prefix = _webhook_mount_prefix()
    path = _webhook_path()

    # An `=` location wins outright over every prefix, so if one claims this exact
    # path it IS the routing, whatever the prefix blocks say.
    for match, (body, offset) in _location_blocks(_server_block()).items():
        parts = match.split()
        if len(parts) == 2 and parts[0] == "=" and parts[1] == path:
            return match, body, offset

    # Prefix locations. `^~` is one too — it just also suppresses regex evaluation
    # when it wins — so strip the modifier rather than dropping the block, which
    # would hide a longer `^~` pointing somewhere else. `location /` is excluded:
    # falling through to it is what caused #456.
    candidates = []
    for match, (body, offset) in _location_blocks(_server_block()).items():
        parts = match.split()
        if len(parts) == 2 and parts[0] == "^~":
            literal = parts[1]
        elif len(parts) == 1 and match.startswith("/"):
            literal = match
        else:
            continue  # `~`/`~*` regex locations are handled separately
        # Match against the concrete PATH, not the mount prefix: a location longer
        # than the prefix (`^~ /webhooks/stripe/webhook`) still matches the request
        # and outranks this block, and testing against the prefix would skip it.
        if literal.rstrip("/") and path.startswith(literal.rstrip("/")):
            candidates.append((match, body, offset, literal))
    if candidates:
        best = max(candidates, key=lambda c: len(c[3]))
        return best[0], best[1], best[2]
    raise AssertionError(
        f"no nginx location block covers the webhook mount prefix {prefix!r}; "
        "Stripe events fall through to the frontend and never reach the handler "
        "(#456)"
    )


def test_nginx_conf_exists():
    assert NGINX_CONF.is_file(), f"missing {NGINX_CONF}"


def test_webhook_path_is_routed_to_the_backend_upstream():
    """AC1: the webhook path reaches the backend, not Next.js."""
    match, body, _ = _webhook_location()
    proxy = re.search(r"proxy_pass\s+([^;]+);", body)
    assert proxy, f"location {match} has no proxy_pass"
    target = proxy.group(1).strip()
    assert "narrative_backend" in target, (
        f"location {match} must proxy to the backend upstream, got {target!r}"
    )


def test_no_regex_location_outranks_the_webhook_block():
    """nginx prefers a matching regex location over a plain prefix one.

    The prefix block above can be perfectly correct and still never be used if some
    later regex also matches the path — so check that none does.
    """
    path = _webhook_path()
    hijackers = []
    for match, (_, _offset) in _location_blocks(_server_block()).items():
        parts = match.split()
        if not parts or parts[0] not in ("~", "~*"):
            continue
        pattern = parts[1] if len(parts) > 1 else ""
        flags = re.I if parts[0] == "~*" else 0
        try:
            if re.search(pattern, path, flags):
                hijackers.append(match)
        except re.error:  # pragma: no cover - a pattern python can't compile
            continue
    assert not hijackers, (
        f"regex location(s) {hijackers} match {path!r} and outrank the prefix "
        "block, so nginx would route the webhook past it"
    )


def test_webhook_proxy_pass_does_not_rewrite_the_uri():
    """A URI on proxy_pass replaces the matched prefix — the backend mounts the
    full ``/webhooks/stripe/webhook`` path, so the URI must pass through as-is."""
    match, body, _ = _webhook_location()
    target = re.search(r"proxy_pass\s+([^;]+);", body).group(1).strip()
    path = target.split("://", 1)[1]
    assert "/" not in path, (
        f"location {match}: proxy_pass must carry no URI part (got {target!r}), "
        "otherwise nginx rewrites the path away from the backend's mount"
    )


def test_webhook_request_is_not_rewritten():
    """AC2: Stripe HMACs the exact bytes — nothing at the edge may reshape them."""
    match, body, _ = _webhook_location()
    offenders = [d for d in REQUEST_ALTERING_DIRECTIVES if re.search(rf"^\s*{d}\s", body, re.M)]
    assert not offenders, (
        f"location {match} contains request-altering directive(s) {offenders}; "
        "Stripe signature verification hashes the exact payload"
    )


def test_webhook_uses_http_1_1_to_upstream():
    """With request buffering off, nginx streams the body — and only HTTP/1.1 can
    chunk it when there is no Content-Length. The default to upstream is 1.0."""
    match, body, _ = _webhook_location()
    assert re.search(r"proxy_http_version\s+1\.1\s*;", body), (
        f"location {match} must set `proxy_http_version 1.1`"
    )


def test_webhook_body_is_capped_at_the_edge():
    """The endpoint is unauthenticated and the backend buffers the whole body before
    verifying anything, so the edge has to bound it."""
    match, body, _ = _webhook_location()
    m = re.search(r"client_max_body_size\s+(\d+)([kKmM]?)\s*;", body)
    assert m, (
        f"location {match} must set its own `client_max_body_size` — it otherwise "
        f"inherits the server-wide 100M on an unauthenticated endpoint"
    )
    assert f"{m.group(1)}{m.group(2).lower()}" == WEBHOOK_BODY_CAP, (
        f"location {match}: {m.group(0)!r} is not the pinned cap {WEBHOOK_BODY_CAP!r}. "
        "Change both together if the cap is meant to move."
    )


def test_webhook_location_precedes_the_catch_all():
    """nginx picks the longest prefix match, so ordering is not strictly required —
    but a reader must not have to know that. Keep the specific block first."""
    text = _server_block()
    _, _, offset = _webhook_location()
    catch_all = _location_blocks(text).get("/")
    assert catch_all, "expected a catch-all `location /` block"
    assert offset < catch_all[1], (
        "the webhook location should appear before the catch-all `location /`"
    )


def test_stripe_signature_header_is_not_stripped():
    """AC3: nginx forwards client request headers by default, so the only ways to
    lose ``Stripe-Signature`` here are to override it or to turn forwarding off."""
    match, body, _ = _webhook_location()
    assert not re.search(r"proxy_set_header\s+Stripe-Signature\b", body, re.I), (
        f"location {match} must not override the Stripe-Signature header"
    )
    assert not re.search(r"proxy_pass_request_headers\s+off\s*;", body), (
        f"location {match} must not disable request header forwarding"
    )


# --- #596: the guard looks at one server block, whatever else the file holds ---------

_APPENDED_SERVER = """
server {{
    listen 9100;
    location /webhooks/stripe/webhook {{
        proxy_pass http://{upstream};
        proxy_http_version 1.1;
        client_max_body_size 2m;
    }}
    location / {{
        proxy_pass http://narrative_frontend;
    }}
}}
"""


def _use_config(monkeypatch, tmp_path, text: str) -> None:
    """Point this module's guard at ``text`` instead of the repository's config."""
    import sys

    path = tmp_path / "nginx.conf"
    path.write_text(text)
    monkeypatch.setattr(sys.modules[__name__], "NGINX_CONF", path)


def _the_guard_passes() -> bool:
    try:
        test_webhook_path_is_routed_to_the_backend_upstream()
        test_no_regex_location_outranks_the_webhook_block()
        test_webhook_location_precedes_the_catch_all()
    except AssertionError:
        return False
    return True


def test_another_servers_longer_location_is_not_a_false_red(monkeypatch, tmp_path):
    """A second server with a longer location that proxies to the frontend: nginx never
    weighs it against the TLS server's, so the guard must still pass."""
    _use_config(monkeypatch, tmp_path, NGINX_CONF.read_text() + _APPENDED_SERVER.format(upstream="narrative_frontend"))

    assert _the_guard_passes()


def test_another_servers_correct_location_is_not_a_false_green(monkeypatch, tmp_path):
    """The TLS server's webhook block is broken, and a second server holds a longer
    location that does proxy to the backend. The guard must still fail."""
    real = NGINX_CONF.read_text()
    start = real.index("location /webhooks/")
    broken = real[:start] + real[start:].replace("narrative_backend", "narrative_frontend", 1)
    assert broken != real, "the mutation must change the webhook block's upstream"
    _use_config(monkeypatch, tmp_path, broken + _APPENDED_SERVER.format(upstream="narrative_backend"))

    assert not _the_guard_passes()


def test_a_second_tls_server_fails_loudly_with_the_count(monkeypatch, tmp_path):
    second_tls = _APPENDED_SERVER.format(upstream="narrative_backend").replace("listen 9100;", "listen 443 ssl;")
    _use_config(monkeypatch, tmp_path, NGINX_CONF.read_text() + second_tls)

    try:
        _server_block()
    except AssertionError as refused:
        assert "found 2" in str(refused)
    else:
        raise AssertionError("two servers on 443 must not be guarded as if they were one")

