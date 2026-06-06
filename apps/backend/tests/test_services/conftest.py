"""
Shared fixtures for service-layer tests.
"""

import pytest

from app.utils import circuit_breaker


def _reset_all_breakers():
    with circuit_breaker._circuit_breakers_lock:
        for breaker in circuit_breaker._circuit_breakers.values():
            breaker.reset()


@pytest.fixture(autouse=True)
def reset_circuit_breakers():
    """
    Reset all circuit breakers between tests.

    Circuit breakers are intentionally global in production (they protect
    shared services across requests), but that state leaks across tests:
    security tests that exercise failure paths open the "s3" breaker, and
    subsequent tests that expect successful calls then fail with
    CircuitBreakerOpen. Decorators capture breaker instances at import time,
    so each instance is reset in-place (clearing the registry would not
    affect captured references).
    """
    _reset_all_breakers()
    yield
    _reset_all_breakers()
