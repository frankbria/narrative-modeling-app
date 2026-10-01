"""Every Next.js route handler must be reachable through the edge (#789).

``location /api/`` sends the ``/api`` prefix to the backend, but Next.js serves its
own route handlers under ``app/api/**``. A handler that no more specific location
claims falls into the backend block and 404s there. Before #789 that was every one
of them, and on the live box ``/api/auth/*`` was included, so sign-in 404'd on
staging. ``/api/chat`` (AIChat) and ``/api/data/{id}/preview`` (DataPreviewTable)
were still unrouted in the repo file.

The handler list comes from the frontend tree, so adding a handler without an
edge route fails here. Routing is resolved with nginx's own precedence, not file
order: an ``=`` match wins outright; then the longest prefix, which ends the search
if it is ``^~``; then the first regex in file order; then that longest prefix.
"""

import re

from tests.test_security.test_nginx_webhook_route import (
    NGINX_CONF,
    REPO_ROOT,
    _location_blocks,
    _server_block,
)

API_DIR = REPO_ROOT / "apps" / "frontend" / "app" / "api"

#: Handlers the edge deliberately sends elsewhere, with the reason.
EDGE_ROUTED_ELSEWHERE = {
    # The edge's /api/health is the backend liveness probe. The frontend's own
    # handler is reached on its container port, not through nginx.
    "/api/health",
}


def _handler_paths() -> list[str]:
    """One concrete request path per ``route.ts``, with ``[param]`` segments filled."""
    paths = []
    for route in sorted(API_DIR.rglob("route.ts")):
        segments = route.parent.relative_to(API_DIR).parts
        filled = [re.sub(r"^\[+\.*(\w+)\]+$", r"sample-\1", s) for s in segments]
        paths.append("/api/" + "/".join(filled))
    return paths


def _resolve(path: str) -> tuple[str, str]:
    """The (match, body) of the location nginx picks for ``path``."""
    blocks = _location_blocks(_server_block())
    prefixes, regexes = [], []
    for match, (body, _) in blocks.items():
        parts = match.split()
        if parts[0] == "=" and parts[1] == path:
            return match, body
        if parts[0] in ("~", "~*"):
            flags = re.I if parts[0] == "~*" else 0
            if re.search(parts[1], path, flags):
                regexes.append((match, body))
        elif parts[0] != "=":
            literal = parts[-1]
            if path.startswith(literal):
                prefixes.append((match, body, literal, parts[0] == "^~"))
    best = max(prefixes, key=lambda p: len(p[2]), default=None)
    if best and best[3]:
        return best[0], best[1]
    if regexes:  # dict order is file order
        return regexes[0]
    assert best, f"no location matches {path}"
    return best[0], best[1]


def _frontend_upstream() -> str:
    m = re.search(r"^\s*upstream\s+(\S*frontend\S*)\s*\{", NGINX_CONF.read_text(), re.M)
    assert m, "expected an `upstream ...frontend...` block"
    return m.group(1)


def test_handlers_are_discovered():
    paths = _handler_paths()
    assert "/api/chat" in paths
    assert "/api/data/sample-id/preview" in paths


def test_every_next_api_handler_reaches_the_frontend():
    upstream = _frontend_upstream()
    misrouted = {}
    for path in _handler_paths():
        if path in EDGE_ROUTED_ELSEWHERE:
            continue
        match, body = _resolve(path)
        if not re.search(
            rf"^\s*proxy_pass\s+http://{re.escape(upstream)}\s*;", body, re.M
        ):
            misrouted[path] = match
    assert not misrouted, (
        "these Next.js route handlers are routed past the frontend at the edge and "
        f"404 at the backend (#789): {misrouted}"
    )


def test_exemptions_are_live():
    stale = EDGE_ROUTED_ELSEWHERE - set(_handler_paths())
    assert not stale, f"exempted handlers no longer exist, drop them: {stale}"


def test_backend_api_still_reaches_the_backend():
    # The guard against over-correcting: a broad frontend block must not swallow
    # the backend's own /api/v1 surface.
    _, body = _resolve("/api/v1/datasets")
    assert re.search(r"^\s*proxy_pass\s+http://narrative_backend\s*;", body, re.M)
