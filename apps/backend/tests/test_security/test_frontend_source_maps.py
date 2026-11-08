"""Browser source maps reach Sentry and nobody else (#1158).

The frontend build uploads its source maps to Sentry when a token is supplied, and
the image must never serve a `.map` file or carry the token in a layer. These pin
the pieces that guarantee it; the real build is exercised in the PR's demo.
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
DOCKERFILE = (REPO / "apps/frontend/Dockerfile").read_text()
NEXT_CONFIG = (REPO / "apps/frontend/next.config.mjs").read_text()


def _build_run() -> str:
    """The builder stage's `npm run build` instruction, continuation lines joined."""
    joined = DOCKERFILE.replace("\\\n", " ")
    return next(line for line in joined.splitlines() if line.startswith("RUN") and "npm run build" in line)


def test_the_token_reaches_the_build_only_as_a_secret_mount():
    assert "--mount=type=secret,id=sentry_auth_token,required=false" in _build_run()
    assert not re.search(r"^\s*(ARG|ENV)\s+SENTRY_AUTH_TOKEN", DOCKERFILE, re.MULTILINE)


def test_the_build_deletes_every_source_map_it_leaves_behind():
    """Sentry deletes what it uploaded; this also covers a failed upload."""
    assert re.search(r"&&\s*find \.next/static -name '\*\.map' -delete", _build_run())


def test_compose_supplies_the_token_from_an_optional_file():
    compose = yaml.safe_load((REPO / "docker-compose.staging.yml").read_text())

    assert compose["services"]["frontend"]["build"]["secrets"] == ["sentry_auth_token"]
    assert compose["secrets"]["sentry_auth_token"] == {"file": "${SENTRY_AUTH_TOKEN_FILE:-/dev/null}"}


def test_without_a_token_the_sdk_generates_no_source_maps():
    """With nothing to upload to, a generated map could only be served."""
    assert "withSentryConfig(" in NEXT_CONFIG
    assert re.search(r"disable:\s*!process\.env\.SENTRY_AUTH_TOKEN", NEXT_CONFIG)
    assert "deleteSourcemapsAfterUpload: true" in NEXT_CONFIG
