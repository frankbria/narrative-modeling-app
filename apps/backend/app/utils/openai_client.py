"""Central OpenAI client construction (#501).

Every OpenAI client in the codebase MUST be built here so two invariants hold
everywhere at once:

* **A request timeout.** Without one a hung upstream blocks past
  ``gunicorn --timeout 120``, the worker is killed, and every in-flight request
  dies with it. The default (30s) is comfortably below that ceiling.
* **``max_retries=0``.** The shared circuit breaker (``with_circuit_breaker``)
  already owns retry/backoff. Leaving the SDK's own default of 2 retries in
  place would stack under 2-3 breaker attempts, so one logical call could run
  ``breaker_attempts × 3 × timeout`` seconds and blow past the worker timeout —
  the very failure this issue is about. Letting the breaker be the only retry
  layer keeps worst-case latency bounded and predictable.

``tests/test_utils/test_openai_client_registry.py`` fails on any raw
``OpenAI(`` / ``AsyncOpenAI(`` construction outside this module, so a new call
site cannot silently reintroduce a timeout-less client.
"""

from __future__ import annotations

import logging
import os

from openai import AsyncOpenAI, OpenAI

logger = logging.getLogger(__name__)

#: The model every call site uses unless `OPENAI_MODEL` says otherwise (#474).
#: One constant because the model is the dominant per-unit cost behind the plan
#: limits in ADR-003: the limits are sized to hold even at gpt-4 prices, and this
#: default is what gives them their margin.
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def openai_model(env_name: str = "OPENAI_MODEL") -> str:
    """The model name for a call site, read per call so tests can override it.

    Blank counts as unset: staging passes optional env through as "" (#457).
    """
    return (os.getenv(env_name) or "").strip() or DEFAULT_OPENAI_MODEL

# The whole point of the timeout is that one logical call can never outlast the
# gunicorn worker timeout. The circuit breaker retries up to 3 attempts with a
# few seconds of exponential backoff between them, so worst case is
# ``attempts × timeout + backoff``. Derive the largest per-request timeout that
# keeps that under the worker timeout (with headroom) and clamp the configured
# value to it — a too-generous env override must not silently reintroduce the
# hung-worker failure this module exists to prevent (#501).
_WORKER_TIMEOUT_SECONDS = 120.0
_MAX_BREAKER_ATTEMPTS = 3
_BREAKER_BACKOFF_BUDGET_SECONDS = 8.0
_HEADROOM = 0.9
OPENAI_TIMEOUT_CEILING = (
    _WORKER_TIMEOUT_SECONDS * _HEADROOM - _BREAKER_BACKOFF_BUDGET_SECONDS
) / _MAX_BREAKER_ATTEMPTS  # ≈ 33.3s

_configured_timeout = float(os.getenv("OPENAI_REQUEST_TIMEOUT", "30"))
if _configured_timeout > OPENAI_TIMEOUT_CEILING:
    logger.warning(
        "OPENAI_REQUEST_TIMEOUT=%.1fs exceeds the safe ceiling %.1fs "
        "(%d breaker attempts must stay under the %.0fs worker timeout); "
        "clamping.",
        _configured_timeout,
        OPENAI_TIMEOUT_CEILING,
        _MAX_BREAKER_ATTEMPTS,
        _WORKER_TIMEOUT_SECONDS,
    )
    _configured_timeout = OPENAI_TIMEOUT_CEILING
elif _configured_timeout <= 0:
    _configured_timeout = 30.0

# Per-request timeout for every OpenAI call, in seconds.
OPENAI_REQUEST_TIMEOUT = _configured_timeout


def build_openai_client(api_key: str) -> OpenAI:
    """A synchronous OpenAI client with the standard timeout and no SDK retries."""
    return OpenAI(
        api_key=api_key,
        timeout=OPENAI_REQUEST_TIMEOUT,
        max_retries=0,
    )


def build_async_openai_client(api_key: str) -> AsyncOpenAI:
    """An async OpenAI client with the standard timeout and no SDK retries."""
    return AsyncOpenAI(
        api_key=api_key,
        timeout=OPENAI_REQUEST_TIMEOUT,
        max_retries=0,
    )
