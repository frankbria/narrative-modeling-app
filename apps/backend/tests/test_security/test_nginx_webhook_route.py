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

#: Stripe events are a few KB. Anything near the server-wide 100M on an
#: unauthenticated endpoint is a free memory-pressure lever.
MAX_WEBHOOK_BODY_MB = 8


def _server_block() -> str:
    """The HTTPS server block — the one that terminates real traffic."""
    text = NGINX_CONF.read_text()
    # The plain-HTTP block only redirects; take everything from the TLS listener on.
    m = re.search(r"^\s*listen\s+(\[::\]:)?443\b", text, re.M)
    assert m, "expected a `listen 443` TLS server block"
    return text[m.start() :]


def _location_blocks(text: str) -> dict[str, tuple[str, int]]:
    """Map each ``location <match>`` to its (brace-balanced body, start offset)."""
    blocks: dict[str, tuple[str, int]] = {}
    for m in re.finditer(r"^[^\S\n]*location\s+([^\s{]+(?:\s+[^\s{]+)?)\s*\{", text, re.M):
        match = m.group(1).strip()
        depth, i = 1, m.end()
        while depth and i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        blocks[match] = (text[m.end() : i - 1], m.start())
    return blocks


def _webhook_mount_prefix() -> str:
    """The prefix ``main.py`` actually mounts the webhook router under."""
    m = re.search(r'prefix="(/webhooks/[^"]*)"', MAIN_PY.read_text())
    assert m, "expected main.py to mount a /webhooks/... router prefix"
    return m.group(1)


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
    candidates = [
        (match, body, offset)
        for match, (body, offset) in _location_blocks(_server_block()).items()
        # Prefix locations only (no `~`/`=` modifier) — the webhook is a plain path.
        # `location /` is excluded: falling through to it is what caused #456.
        if match.startswith("/")
        and match.rstrip("/")
        and prefix.startswith(match.rstrip("/"))
    ]
    if candidates:
        return max(candidates, key=lambda c: len(c[0]))
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
    size, unit = int(m.group(1)), m.group(2).lower()
    megabytes = size / 1024 if unit == "k" else size
    assert 0 < megabytes <= MAX_WEBHOOK_BODY_MB, (
        f"location {match}: client_max_body_size {m.group(0)!r} is outside the "
        f"sane range for Stripe events (0 < n <= {MAX_WEBHOOK_BODY_MB}M)"
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
