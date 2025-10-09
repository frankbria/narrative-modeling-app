"""
Circuit breaker implementation for external service resilience.

Provides decorators and utilities for implementing circuit breaker patterns
to prevent cascading failures when external services (S3, OpenAI, MongoDB) are unavailable.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, ParamSpec
from functools import wraps
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states following the standard pattern."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerMetrics:
    """Metrics tracking for circuit breaker state and performance."""

    def __init__(self):
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None
        self.state_changes: list[tuple[CircuitState, float]] = []

    def record_success(self):
        """Record a successful operation."""
        self.success_count += 1
        self.last_success_time = time.time()

    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

    def record_state_change(self, new_state: CircuitState):
        """Record a circuit state transition."""
        self.state_changes.append((new_state, time.time()))

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics as dictionary."""
        current_state = self.state_changes[-1][0] if self.state_changes else CircuitState.CLOSED
        return {
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "current_state": current_state.value,
            "state_changes": len(self.state_changes),
        }


# Global metrics tracking for monitoring
_circuit_metrics: Dict[str, CircuitBreakerMetrics] = {}


def get_circuit_metrics(service_name: str) -> CircuitBreakerMetrics:
    """Get or create metrics tracker for a service."""
    if service_name not in _circuit_metrics:
        _circuit_metrics[service_name] = CircuitBreakerMetrics()
    return _circuit_metrics[service_name]


def get_all_circuit_metrics() -> Dict[str, Dict[str, Any]]:
    """Get metrics for all tracked services."""
    return {
        service: metrics.get_metrics()
        for service, metrics in _circuit_metrics.items()
    }


def with_circuit_breaker(
    service_name: str,
    max_attempts: int = 3,
    max_wait_seconds: int = 60,
    exceptions: tuple = (Exception,),
    fallback_value: Optional[Any] = None,
):
    """
    Decorator to apply circuit breaker pattern to async functions.

    Args:
        service_name: Name of the service for metrics tracking
        max_attempts: Maximum number of retry attempts
        max_wait_seconds: Maximum wait time between retries (seconds)
        exceptions: Tuple of exceptions to retry on
        fallback_value: Value to return if all retries fail (None = raise exception)

    Example:
        @with_circuit_breaker("s3", max_attempts=5, fallback_value={})
        async def upload_to_s3(file_data):
            # S3 upload logic
            pass
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        metrics = get_circuit_metrics(service_name)

        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=2, min=2, max=max_wait_seconds),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
        )
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                result = await func(*args, **kwargs)
                metrics.record_success()
                return result
            except exceptions as e:
                metrics.record_failure()
                logger.error(f"Circuit breaker failure for {service_name}: {str(e)}")

                # If fallback value is provided, return it instead of raising
                if fallback_value is not None:
                    logger.warning(f"Returning fallback value for {service_name}")
                    return fallback_value

                raise

        return async_wrapper

    return decorator


def with_sync_circuit_breaker(
    service_name: str,
    max_attempts: int = 3,
    max_wait_seconds: int = 60,
    exceptions: tuple = (Exception,),
    fallback_value: Optional[Any] = None,
):
    """
    Decorator to apply circuit breaker pattern to synchronous functions.

    Same as with_circuit_breaker but for sync functions.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        metrics = get_circuit_metrics(service_name)

        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=2, min=2, max=max_wait_seconds),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
        )
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                result = func(*args, **kwargs)
                metrics.record_success()
                return result
            except exceptions as e:
                metrics.record_failure()
                logger.error(f"Circuit breaker failure for {service_name}: {str(e)}")

                if fallback_value is not None:
                    logger.warning(f"Returning fallback value for {service_name}")
                    return fallback_value

                raise

        return sync_wrapper

    return decorator


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker open for {service_name}. "
            f"Retry after {retry_after:.1f} seconds."
        )
