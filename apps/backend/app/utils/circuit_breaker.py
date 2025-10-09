"""
Circuit breaker implementation for external service resilience.

Provides decorators and utilities for implementing circuit breaker patterns
to prevent cascading failures when external services (S3, OpenAI, MongoDB) are unavailable.

This implementation follows the standard circuit breaker pattern:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit is open after failures, requests fail fast
- HALF_OPEN: Testing if service has recovered
"""

import asyncio
import logging
import time
import threading
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
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None
        self.state_changes: list[tuple[CircuitState, float]] = []
        self._lock = threading.Lock()

    def record_success(self):
        """Record a successful operation."""
        with self._lock:
            self.success_count += 1
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            self.last_success_time = time.time()

    def record_failure(self):
        """Record a failed operation."""
        with self._lock:
            self.failure_count += 1
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            self.last_failure_time = time.time()

    def record_state_change(self, new_state: CircuitState):
        """Record a circuit state transition."""
        with self._lock:
            self.state_changes.append((new_state, time.time()))
            logger.info(f"Circuit state changed to {new_state.value}")

    def reset_consecutive_counts(self):
        """Reset consecutive failure/success counters."""
        with self._lock:
            self.consecutive_failures = 0
            self.consecutive_successes = 0

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics as dictionary."""
        with self._lock:
            current_state = self.state_changes[-1][0] if self.state_changes else CircuitState.CLOSED
            return {
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "consecutive_failures": self.consecutive_failures,
                "consecutive_successes": self.consecutive_successes,
                "last_failure_time": self.last_failure_time,
                "last_success_time": self.last_success_time,
                "current_state": current_state.value,
                "state_changes": len(self.state_changes),
            }


class CircuitBreaker:
    """
    Circuit breaker implementation with state management.

    Prevents cascading failures by:
    1. Tracking failures and opening circuit after threshold
    2. Failing fast when circuit is open
    3. Testing service recovery in half-open state
    4. Automatically closing circuit when service recovers
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ):
        """
        Initialize circuit breaker.

        Args:
            service_name: Name of the service for logging/metrics
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery (OPEN → HALF_OPEN)
            half_open_max_calls: Number of test calls allowed in HALF_OPEN state
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self.half_open_calls = 0
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()

        # Record initial state
        self.metrics.record_state_change(CircuitState.CLOSED)

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.state != CircuitState.OPEN:
            return False

        if self.metrics.last_failure_time is None:
            return False

        time_since_failure = time.time() - self.metrics.last_failure_time
        return time_since_failure >= self.recovery_timeout

    def _transition_state(self, new_state: CircuitState):
        """Transition to a new circuit state."""
        if new_state == self.state:
            return

        logger.info(
            f"Circuit breaker '{self.service_name}': {self.state.value} → {new_state.value}"
        )

        self.state = new_state
        self.metrics.record_state_change(new_state)

        if new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0

    def record_success(self):
        """Record successful operation and update state."""
        with self._lock:
            self.metrics.record_success()

            if self.state == CircuitState.HALF_OPEN:
                # Success in half-open state -> close circuit
                logger.info(f"Circuit breaker '{self.service_name}': Service recovered")
                self._transition_state(CircuitState.CLOSED)
                self.metrics.reset_consecutive_counts()
            elif self.state == CircuitState.CLOSED:
                # Reset failure counter on success
                if self.metrics.consecutive_successes >= 2:
                    self.metrics.reset_consecutive_counts()

    def record_failure(self):
        """Record failed operation and update state."""
        with self._lock:
            self.metrics.record_failure()

            if self.state == CircuitState.HALF_OPEN:
                # Failure in half-open state -> back to open
                logger.warning(
                    f"Circuit breaker '{self.service_name}': Recovery failed, reopening circuit"
                )
                self._transition_state(CircuitState.OPEN)
            elif self.state == CircuitState.CLOSED:
                # Check if we should open the circuit
                if self.metrics.consecutive_failures >= self.failure_threshold:
                    logger.error(
                        f"Circuit breaker '{self.service_name}': "
                        f"Opening circuit after {self.metrics.consecutive_failures} failures"
                    )
                    self._transition_state(CircuitState.OPEN)

    def can_execute(self) -> bool:
        """Check if operation can be executed based on circuit state."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # Check if we should attempt recovery
                if self._should_attempt_reset():
                    logger.info(
                        f"Circuit breaker '{self.service_name}': "
                        f"Attempting recovery after {self.recovery_timeout}s"
                    )
                    self._transition_state(CircuitState.HALF_OPEN)
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open state
                if self.half_open_calls < self.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False

            return False

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self.state


# Global circuit breakers for each service
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_circuit_breakers_lock = threading.Lock()


def get_circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> CircuitBreaker:
    """Get or create circuit breaker for a service."""
    with _circuit_breakers_lock:
        if service_name not in _circuit_breakers:
            _circuit_breakers[service_name] = CircuitBreaker(
                service_name=service_name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        return _circuit_breakers[service_name]


def get_all_circuit_metrics() -> Dict[str, Dict[str, Any]]:
    """Get metrics for all tracked services."""
    with _circuit_breakers_lock:
        return {
            service: breaker.metrics.get_metrics()
            for service, breaker in _circuit_breakers.items()
        }


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker open for {service_name}. "
            f"Retry after {retry_after:.1f} seconds."
        )


def with_circuit_breaker(
    service_name: str,
    max_attempts: int = 3,
    max_wait_seconds: int = 60,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    exceptions: tuple = (Exception,),
    fallback_value: Optional[Any] = None,
):
    """
    Decorator to apply circuit breaker pattern to async functions.

    Combines circuit breaker pattern with retry logic for resilience.

    Args:
        service_name: Name of the service for metrics tracking
        max_attempts: Maximum number of retry attempts
        max_wait_seconds: Maximum wait time between retries (seconds)
        failure_threshold: Consecutive failures before opening circuit
        recovery_timeout: Seconds before attempting recovery
        exceptions: Tuple of exceptions to retry on
        fallback_value: Value to return if all retries fail (None = raise exception)

    Example:
        @with_circuit_breaker("s3", max_attempts=5, fallback_value={})
        async def upload_to_s3(file_data):
            # S3 upload logic
            pass
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        breaker = get_circuit_breaker(service_name, failure_threshold, recovery_timeout)

        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=2, min=2, max=max_wait_seconds),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
        )
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Check circuit state before attempting operation
            if not breaker.can_execute():
                logger.warning(
                    f"Circuit breaker '{service_name}' is OPEN, failing fast"
                )
                raise CircuitBreakerOpen(service_name, recovery_timeout)

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except exceptions as e:
                breaker.record_failure()
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
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    exceptions: tuple = (Exception,),
    fallback_value: Optional[Any] = None,
):
    """
    Decorator to apply circuit breaker pattern to synchronous functions.

    Same as with_circuit_breaker but for sync functions.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        breaker = get_circuit_breaker(service_name, failure_threshold, recovery_timeout)

        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=2, min=2, max=max_wait_seconds),
            retry=retry_if_exception_type(exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
        )
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if not breaker.can_execute():
                logger.warning(
                    f"Circuit breaker '{service_name}' is OPEN, failing fast"
                )
                raise CircuitBreakerOpen(service_name, recovery_timeout)

            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except exceptions as e:
                breaker.record_failure()
                logger.error(f"Circuit breaker failure for {service_name}: {str(e)}")

                if fallback_value is not None:
                    logger.warning(f"Returning fallback value for {service_name}")
                    return fallback_value

                raise

        return sync_wrapper

    return decorator
