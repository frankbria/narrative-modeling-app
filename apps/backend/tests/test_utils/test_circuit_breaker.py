"""
Unit tests for circuit breaker implementation.

Tests validate:
- State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Fail-fast behavior when circuit is OPEN
- Recovery timeout logic
- Consecutive failure/success tracking
- Thread safety
- Metrics recording
- Decorator usage
"""

import asyncio
import time
import threading
from unittest.mock import AsyncMock, Mock
import pytest

from app.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerMetrics,
    CircuitBreakerOpen,
    get_circuit_breaker,
    get_all_circuit_metrics,
    with_circuit_breaker,
    with_sync_circuit_breaker,
)


@pytest.mark.unit
class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics tracking."""

    def test_initial_state(self):
        """Test metrics start with zero values."""
        metrics = CircuitBreakerMetrics()

        assert metrics.failure_count == 0
        assert metrics.success_count == 0
        assert metrics.consecutive_failures == 0
        assert metrics.consecutive_successes == 0
        assert metrics.last_failure_time is None
        assert metrics.last_success_time is None
        assert len(metrics.state_changes) == 0

    def test_record_success(self):
        """Test recording successful operations."""
        metrics = CircuitBreakerMetrics()

        metrics.record_success()

        assert metrics.success_count == 1
        assert metrics.consecutive_successes == 1
        assert metrics.consecutive_failures == 0
        assert metrics.last_success_time is not None

    def test_record_failure(self):
        """Test recording failed operations."""
        metrics = CircuitBreakerMetrics()

        metrics.record_failure()

        assert metrics.failure_count == 1
        assert metrics.consecutive_failures == 1
        assert metrics.consecutive_successes == 0
        assert metrics.last_failure_time is not None

    def test_consecutive_tracking(self):
        """Test consecutive success/failure tracking."""
        metrics = CircuitBreakerMetrics()

        # Build up consecutive failures
        metrics.record_failure()
        metrics.record_failure()
        metrics.record_failure()
        assert metrics.consecutive_failures == 3
        assert metrics.consecutive_successes == 0

        # Success resets consecutive failures
        metrics.record_success()
        assert metrics.consecutive_failures == 0
        assert metrics.consecutive_successes == 1

    def test_state_change_recording(self):
        """Test state change tracking."""
        metrics = CircuitBreakerMetrics()

        metrics.record_state_change(CircuitState.OPEN)
        metrics.record_state_change(CircuitState.HALF_OPEN)

        assert len(metrics.state_changes) == 2
        assert metrics.state_changes[0][0] == CircuitState.OPEN
        assert metrics.state_changes[1][0] == CircuitState.HALF_OPEN

    def test_get_metrics(self):
        """Test metrics dictionary output."""
        metrics = CircuitBreakerMetrics()
        metrics.record_state_change(CircuitState.CLOSED)
        metrics.record_failure()
        metrics.record_success()

        result = metrics.get_metrics()

        assert result["failure_count"] == 1
        assert result["success_count"] == 1
        assert result["current_state"] == CircuitState.CLOSED.value
        assert result["state_changes"] == 1

    def test_thread_safety(self):
        """Test metrics are thread-safe."""
        metrics = CircuitBreakerMetrics()

        def record_operations():
            for _ in range(100):
                metrics.record_success()
                metrics.record_failure()

        threads = [threading.Thread(target=record_operations) for _ in range(10)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # 10 threads * 100 operations each = 1000 of each
        assert metrics.success_count == 1000
        assert metrics.failure_count == 1000


@pytest.mark.unit
class TestCircuitBreaker:
    """Test circuit breaker state machine."""

    def test_initial_state_is_closed(self):
        """Test circuit starts in CLOSED state."""
        breaker = CircuitBreaker("test_service")

        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True

    def test_opens_after_failure_threshold(self):
        """Test circuit opens after consecutive failures."""
        breaker = CircuitBreaker("test_service", failure_threshold=3)

        # First 2 failures don't open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        # 3rd failure opens circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_fail_fast_when_open(self):
        """Test circuit fails fast when OPEN."""
        breaker = CircuitBreaker("test_service", failure_threshold=2)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Should not allow execution
        assert breaker.can_execute() is False

    def test_transitions_to_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        breaker = CircuitBreaker(
            "test_service",
            failure_threshold=2,
            recovery_timeout=0.1  # 100ms for fast testing
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # Should transition to HALF_OPEN
        assert breaker.can_execute() is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        """Test success in HALF_OPEN state closes circuit."""
        breaker = CircuitBreaker(
            "test_service",
            failure_threshold=2,
            recovery_timeout=0.1
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Wait and transition to HALF_OPEN
        time.sleep(0.2)
        breaker.can_execute()  # Triggers transition
        assert breaker.state == CircuitState.HALF_OPEN

        # Success closes circuit
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self):
        """Test failure in HALF_OPEN state reopens circuit."""
        breaker = CircuitBreaker(
            "test_service",
            failure_threshold=2,
            recovery_timeout=0.1
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Wait and transition to HALF_OPEN
        time.sleep(0.2)
        breaker.can_execute()
        assert breaker.state == CircuitState.HALF_OPEN

        # Failure reopens circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_half_open_max_calls_limit(self):
        """Test HALF_OPEN state limits number of test calls."""
        breaker = CircuitBreaker(
            "test_service_half_open",
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_max_calls=1
        )

        # Open and transition to HALF_OPEN
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(0.2)

        # First call allowed
        first_call = breaker.can_execute()
        assert first_call is True
        assert breaker.state == CircuitState.HALF_OPEN

        # Second call not allowed (max_calls=1)
        # Still in HALF_OPEN but calls exhausted
        second_call = breaker.can_execute()
        assert second_call is False
        assert breaker.state == CircuitState.HALF_OPEN

    def test_success_resets_failure_count(self):
        """Test successes reset consecutive failure count."""
        breaker = CircuitBreaker("test_service", failure_threshold=3)

        # Build up failures
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.metrics.consecutive_failures == 2

        # Multiple successes reset
        breaker.record_success()
        breaker.record_success()
        assert breaker.metrics.consecutive_failures == 0

    def test_metrics_tracking(self):
        """Test circuit breaker tracks metrics correctly."""
        breaker = CircuitBreaker("test_service", failure_threshold=2)

        breaker.record_success()
        breaker.record_failure()
        breaker.record_failure()  # Opens circuit

        metrics = breaker.metrics.get_metrics()
        assert metrics["success_count"] == 1
        assert metrics["failure_count"] == 2
        assert metrics["current_state"] == CircuitState.OPEN.value

    def test_thread_safety(self):
        """Test circuit breaker is thread-safe."""
        breaker = CircuitBreaker("test_service", failure_threshold=10)

        def stress_test():
            for _ in range(50):
                if breaker.can_execute():
                    breaker.record_success()
                breaker.record_failure()

        threads = [threading.Thread(target=stress_test) for _ in range(10)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have recorded operations without crashes
        metrics = breaker.metrics.get_metrics()
        assert metrics["failure_count"] > 0
        assert metrics["success_count"] >= 0


@pytest.mark.unit
class TestCircuitBreakerGlobal:
    """Test global circuit breaker management."""

    def test_get_circuit_breaker(self):
        """Test getting or creating circuit breaker."""
        breaker1 = get_circuit_breaker("service1")
        breaker2 = get_circuit_breaker("service1")
        breaker3 = get_circuit_breaker("service2")

        # Same service returns same instance
        assert breaker1 is breaker2
        # Different service returns different instance
        assert breaker1 is not breaker3

    def test_get_all_circuit_metrics(self):
        """Test getting metrics for all services."""
        breaker1 = get_circuit_breaker("service1")
        breaker2 = get_circuit_breaker("service2")

        breaker1.record_success()
        breaker2.record_failure()

        all_metrics = get_all_circuit_metrics()

        assert "service1" in all_metrics
        assert "service2" in all_metrics
        assert all_metrics["service1"]["success_count"] == 1
        assert all_metrics["service2"]["failure_count"] == 1


@pytest.mark.unit
class TestCircuitBreakerException:
    """Test CircuitBreakerOpen exception."""

    def test_exception_attributes(self):
        """Test exception has correct attributes."""
        exc = CircuitBreakerOpen("test_service", 60.0)

        assert exc.service_name == "test_service"
        assert exc.retry_after == 60.0
        assert "test_service" in str(exc)
        assert "60.0" in str(exc)


@pytest.mark.unit
@pytest.mark.asyncio
class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator for async functions."""

    async def test_decorator_success(self):
        """Test decorator allows successful operations."""
        call_count = 0

        @with_circuit_breaker("test_service", max_attempts=1, failure_threshold=5)
        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_operation()

        assert result == "success"
        assert call_count == 1

        # Circuit should remain closed
        breaker = get_circuit_breaker("test_service")
        assert breaker.state == CircuitState.CLOSED

    async def test_decorator_retries_on_failure(self):
        """Test decorator retries failed operations."""
        from tenacity import RetryError
        call_count = 0

        @with_circuit_breaker("test_service_2", max_attempts=3, failure_threshold=5)
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")

        with pytest.raises(RetryError):
            await failing_operation()

        # Should have retried 3 times
        assert call_count == 3

    async def test_decorator_opens_circuit(self):
        """Test decorator opens circuit after failures."""
        from tenacity import RetryError

        @with_circuit_breaker("test_service_3", max_attempts=1, failure_threshold=2)
        async def failing_operation():
            raise ValueError("Test error")

        # First failure
        with pytest.raises(RetryError):
            await failing_operation()

        # Second failure opens circuit
        with pytest.raises(RetryError):
            await failing_operation()

        # Third attempt should fail fast with CircuitBreakerOpen
        # Note: tenacity wraps it in RetryError even though it's not retried
        with pytest.raises(RetryError) as exc_info:
            await failing_operation()

        # Verify it was CircuitBreakerOpen that caused the failure
        assert isinstance(exc_info.value.__cause__, CircuitBreakerOpen)

    async def test_decorator_fallback_value(self):
        """Test decorator returns fallback value on failure."""
        @with_circuit_breaker(
            "test_service_4",
            max_attempts=1,
            failure_threshold=5,
            fallback_value={"status": "fallback"}
        )
        async def failing_operation():
            raise ValueError("Test error")

        result = await failing_operation()

        assert result == {"status": "fallback"}

    async def test_decorator_specific_exceptions(self):
        """Test decorator only retries specific exceptions."""
        call_count = 0

        @with_circuit_breaker(
            "test_service_5",
            max_attempts=3,
            failure_threshold=5,
            exceptions=(ValueError,)  # Only retry ValueError
        )
        async def mixed_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retryable")
            else:
                raise TypeError("Not retryable")

        with pytest.raises(TypeError):
            await mixed_errors()

        # Should have retried ValueError then hit TypeError
        assert call_count == 2


@pytest.mark.unit
class TestSyncCircuitBreakerDecorator:
    """Test circuit breaker decorator for sync functions."""

    def test_sync_decorator_success(self):
        """Test sync decorator allows successful operations."""
        call_count = 0

        @with_sync_circuit_breaker("sync_service", max_attempts=1, failure_threshold=5)
        def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_operation()

        assert result == "success"
        assert call_count == 1

    def test_sync_decorator_retries(self):
        """Test sync decorator retries failed operations."""
        from tenacity import RetryError
        call_count = 0

        @with_sync_circuit_breaker("sync_service_2", max_attempts=3, failure_threshold=5)
        def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")

        with pytest.raises(RetryError):
            failing_operation()

        assert call_count == 3

    def test_sync_decorator_fallback(self):
        """Test sync decorator returns fallback value."""
        @with_sync_circuit_breaker(
            "sync_service_3",
            max_attempts=1,
            failure_threshold=5,
            fallback_value="default"
        )
        def failing_operation():
            raise ValueError("Test error")

        result = failing_operation()

        assert result == "default"
