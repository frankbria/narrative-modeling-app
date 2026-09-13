"""Every OpenAI client must be built through the timeout-setting factory (#501).

A raw ``OpenAI(...)`` / ``AsyncOpenAI(...)`` construction has no request timeout,
so a hung upstream blocks past the gunicorn worker timeout and kills the worker.
`app/utils/openai_client.py` is the one place allowed to construct a client; this
test fails on any other construction so a new call site cannot silently
reintroduce a timeout-less client.
"""

import re
from pathlib import Path

import pytest

from app.utils.openai_client import (
    OPENAI_REQUEST_TIMEOUT,
    build_async_openai_client,
    build_openai_client,
)

APP_DIR = Path(__file__).resolve().parents[2] / "app"
FACTORY = APP_DIR / "utils" / "openai_client.py"

# A client construction: `OpenAI(` or `AsyncOpenAI(` used as a call. Excludes
# `OpenAIError`, type annotations like `OpenAI | None` (no paren), and imports.
_CONSTRUCTION = re.compile(r"\b(?:Async)?OpenAI\s*\(")


@pytest.mark.unit
def test_no_raw_openai_construction_outside_factory():
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        if path == FACTORY:
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]  # ignore comment prose (e.g. "OpenAI (...)")
            if _CONSTRUCTION.search(code):
                offenders.append(f"{path.relative_to(APP_DIR.parent)}:{i}: {line.strip()}")
    assert not offenders, (
        "OpenAI clients must be built via app.utils.openai_client so the request "
        "timeout is always set (#501). Offending constructions:\n" + "\n".join(offenders)
    )


@pytest.mark.unit
def test_factory_sets_timeout_and_disables_sdk_retries():
    for build in (build_openai_client, build_async_openai_client):
        client = build("sk-test")
        assert client.timeout == OPENAI_REQUEST_TIMEOUT
        # The circuit breaker owns retries; the SDK must not stack its own on top,
        # or worst-case latency can exceed the gunicorn worker timeout (#501).
        assert client.max_retries == 0


@pytest.mark.unit
def test_timeout_is_comfortably_below_gunicorn_worker_timeout():
    # gunicorn runs with --timeout 120; leave headroom even across breaker retries.
    assert 0 < OPENAI_REQUEST_TIMEOUT <= 60
