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

import os

from openai import AsyncOpenAI, OpenAI

# Per-request timeout for every OpenAI call, in seconds. Env-overridable but
# always well under the gunicorn worker timeout (120s), even across breaker
# retries (see module docstring).
OPENAI_REQUEST_TIMEOUT = float(os.getenv("OPENAI_REQUEST_TIMEOUT", "30"))


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
