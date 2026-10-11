"""Staging is noindex at the edge, and only production is indexable (#830).

Staging serves the same pages as production, so a crawler that finds it competes
with production for the same content. The header is set in nginx rather than in a
`robots.ts`, so it covers the app, the API and every error response alike.

Production renders this same template (#832), which is why the header is keyed on
the hostname instead of being hard-coded: a `map` defaults every host to
`noindex, nofollow` and names the production host as the one exception. It fails
closed. A new hostname is unindexable until someone lists it here and in the map.

Two nginx rules make the placement load-bearing:

* `add_header` in a location **replaces** every inherited one, so a location with
  its own header silently drops this one (and HSTS, which is how static assets were
  being served without it).
* this file is included at `http` level on a VPS shared with other sites, so a
  header outside a `server` block would land on all of them.

Text-based for the same reason as its siblings: CI has no nginx binary.
"""

import re

from tests.test_security.test_nginx_webhook_route import NGINX_CONF, _location_blocks

#: The only hostnames a crawler may index (#765 D4).
INDEXABLE_HOSTS = {"www.sheetpredict.app"}

HEADER = "add_header X-Robots-Tag $narrative_robots_tag always;"


def _robots_map() -> dict[str, str]:
    m = re.search(
        r"^map \$host \$narrative_robots_tag \{$(.*?)^\}$",
        NGINX_CONF.read_text(),
        re.S | re.M,
    )
    assert m, "expected `map $host $narrative_robots_tag { ... }` at http level"
    return dict(re.findall(r'^\s*(\S+)\s+"([^"]*)";', m.group(1), re.M))


def _server_blocks() -> list[str]:
    # Server blocks open and close at column 0; nothing nested does.
    return re.findall(r"^server \{$(.*?)^\}$", NGINX_CONF.read_text(), re.S | re.M)


def test_every_host_is_noindex_by_default():
    assert _robots_map()["default"] == "noindex, nofollow"


def test_only_the_production_hosts_are_indexable():
    exceptions = {h: v for h, v in _robots_map().items() if h != "default"}
    # An empty value is what makes nginx omit the header altogether.
    assert exceptions == dict.fromkeys(INDEXABLE_HOSTS, "")


def test_every_server_block_sends_the_header():
    blocks = _server_blocks()
    assert len(blocks) == 2, "expected the :80 redirect block and the :443 block"
    for block in blocks:
        # Four spaces: declared on the server itself, not inside one location.
        assert re.search(rf"^    {re.escape(HEADER)}$", block, re.M), block[:120]


def test_no_location_drops_the_inherited_headers():
    for block in _server_blocks():
        for match, (body, _) in _location_blocks(block).items():
            assert not re.search(r"^\s*add_header\b", body, re.M), (
                f"location {match} declares its own add_header, which discards "
                "X-Robots-Tag and every security header set on the server"
            )


def test_no_header_is_set_for_the_whole_shared_box():
    assert not re.search(r"^add_header\b", NGINX_CONF.read_text(), re.M)
