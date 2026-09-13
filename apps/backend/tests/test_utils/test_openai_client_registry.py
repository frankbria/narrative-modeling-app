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

# A client construction call: `OpenAI(` / `AsyncOpenAI(` with NO space before the
# paren — that is how a real call is written (ruff E211 forbids `OpenAI (…)`), so
# this never matches prose like "MongoDB + S3 + OpenAI (#503)" or "OpenAI (can be
# …)" in a comment/docstring. Also excludes `OpenAIError`, type annotations like
# `OpenAI | None` (no paren), and imports.
_CONSTRUCTION = re.compile(r"\b(?:Async)?OpenAI\(")


@pytest.mark.unit
def test_no_raw_openai_construction_outside_factory():
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        if path == FACTORY:
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if _CONSTRUCTION.search(line):
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
def test_timeout_worst_case_stays_under_the_worker_timeout():
    # gunicorn runs with --timeout 120; the breaker retries up to 3 attempts with
    # backoff. Even the worst case must finish before the worker is killed (#501).
    from app.utils import openai_client as oc

    assert OPENAI_REQUEST_TIMEOUT > 0
    worst_case = (
        oc._MAX_BREAKER_ATTEMPTS * OPENAI_REQUEST_TIMEOUT
        + oc._BREAKER_BACKOFF_BUDGET_SECONDS
    )
    assert worst_case < oc._WORKER_TIMEOUT_SECONDS


@pytest.mark.unit
def test_too_large_env_timeout_is_clamped(monkeypatch):
    import importlib

    from app.utils import openai_client as oc

    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT", "300")  # absurd; would kill workers
    reloaded = importlib.reload(oc)
    try:
        assert reloaded.OPENAI_REQUEST_TIMEOUT == reloaded.OPENAI_TIMEOUT_CEILING
        worst = (
            reloaded._MAX_BREAKER_ATTEMPTS * reloaded.OPENAI_REQUEST_TIMEOUT
            + reloaded._BREAKER_BACKOFF_BUDGET_SECONDS
        )
        assert worst < reloaded._WORKER_TIMEOUT_SECONDS
    finally:
        monkeypatch.delenv("OPENAI_REQUEST_TIMEOUT", raising=False)
        importlib.reload(oc)  # restore module state for other tests
