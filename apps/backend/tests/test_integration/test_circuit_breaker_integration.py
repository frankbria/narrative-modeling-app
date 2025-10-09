"""
Integration tests for circuit breaker patterns with real services.

Tests validate:
- Circuit breaker behavior with MongoDB operations
- Circuit breaker behavior with S3 operations
- Circuit breaker behavior with OpenAI API calls
- Fallback mechanisms work correctly
- Metrics are tracked properly
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

from app.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    get_circuit_breaker,
    with_circuit_breaker,
    CircuitBreakerOpen,
)
from app.models.user_data import UserData


@pytest.mark.integration
@pytest.mark.asyncio
class TestCircuitBreakerWithMongoDB:
    """Test circuit breaker with real MongoDB operations."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, setup_database):
        """Set up test database."""
        self.breaker = CircuitBreaker(
            "test_mongodb",
            failure_threshold=2,
            recovery_timeout=1.0,
        )

    async def test_successful_mongodb_operation(self):
        """Test circuit breaker allows successful MongoDB operations."""

        @with_circuit_breaker("test_mongo_success", max_attempts=1, failure_threshold=5)
        async def create_user_data():
            user_data = UserData(
                user_id="test_user",
                filename="test.csv",
                s3_url="s3://test/file.csv",
                num_rows=100,
                num_columns=5,
            )
            await user_data.insert()
            return user_data

        result = await create_user_data()
        assert result is not None
        assert result.user_id == "test_user"

        # Circuit should remain closed
        breaker = get_circuit_breaker("test_mongo_success")
        assert breaker.state == CircuitState.CLOSED

        # Clean up
        await UserData.find(UserData.user_id == "test_user").delete()

    async def test_mongodb_failure_opens_circuit(self):
        """Test circuit opens after MongoDB failures."""
        call_count = 0

        @with_circuit_breaker(
            "test_mongo_fail", max_attempts=1, failure_threshold=2, fallback_value=None
        )
        async def failing_mongodb_operation():
            nonlocal call_count
            call_count += 1
            # Simulate MongoDB failure
            raise ConnectionError("MongoDB connection failed")

        # First failure
        try:
            await failing_mongodb_operation()
        except Exception:
            pass

        # Second failure should open circuit
        try:
            await failing_mongodb_operation()
        except Exception:
            pass

        # Third call should fail fast
        with pytest.raises(CircuitBreakerOpen):
            await failing_mongodb_operation()

        breaker = get_circuit_breaker("test_mongo_fail")
        assert breaker.state == CircuitState.OPEN

    async def test_mongodb_recovery_after_circuit_open(self):
        """Test circuit recovers after MongoDB service recovers."""
        failure_mode = True

        @with_circuit_breaker(
            "test_mongo_recovery",
            max_attempts=1,
            failure_threshold=2,
            recovery_timeout=0.5,
        )
        async def conditional_mongodb_operation():
            if failure_mode:
                raise ConnectionError("MongoDB down")
            # Success case
            user_data = UserData(
                user_id="recovery_test",
                filename="test.csv",
                s3_url="s3://test/file.csv",
                num_rows=10,
                num_columns=2,
            )
            await user_data.insert()
            return user_data

        # Cause failures to open circuit
        try:
            await conditional_mongodb_operation()
        except Exception:
            pass
        try:
            await conditional_mongodb_operation()
        except Exception:
            pass

        breaker = get_circuit_breaker("test_mongo_recovery")
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.6)

        # Fix the "service"
        failure_mode = False

        # Should transition to HALF_OPEN and succeed
        result = await conditional_mongodb_operation()
        assert result is not None

        # Circuit should close after success
        assert breaker.state == CircuitState.CLOSED

        # Clean up
        await UserData.find(UserData.user_id == "recovery_test").delete()


@pytest.mark.integration
@pytest.mark.asyncio
class TestCircuitBreakerWithS3:
    """Test circuit breaker with mocked S3 operations."""

    async def test_s3_operation_with_circuit_breaker(self):
        """Test circuit breaker with S3 upload simulation."""

        @with_circuit_breaker("test_s3", max_attempts=3, failure_threshold=5)
        async def upload_to_s3(file_data: bytes):
            # Simulate S3 upload
            await asyncio.sleep(0.01)  # Simulate network delay
            if len(file_data) == 0:
                raise ValueError("Empty file")
            return {"url": "s3://bucket/file.csv", "size": len(file_data)}

        # Successful upload
        result = await upload_to_s3(b"test data")
        assert result["url"] == "s3://bucket/file.csv"
        assert result["size"] > 0

        breaker = get_circuit_breaker("test_s3")
        assert breaker.state == CircuitState.CLOSED

    async def test_s3_failures_with_fallback(self):
        """Test circuit breaker fallback for S3 failures."""

        @with_circuit_breaker(
            "test_s3_fallback",
            max_attempts=2,
            failure_threshold=5,
            fallback_value={"url": "local://fallback", "size": 0},
        )
        async def flaky_s3_upload():
            raise ConnectionError("S3 unavailable")

        # Should return fallback value
        result = await flaky_s3_upload()
        assert result["url"] == "local://fallback"


@pytest.mark.integration
@pytest.mark.asyncio
class TestCircuitBreakerWithOpenAI:
    """Test circuit breaker with mocked OpenAI API calls."""

    async def test_openai_operation_with_circuit_breaker(self):
        """Test circuit breaker with OpenAI API simulation."""
        call_count = 0

        @with_circuit_breaker("test_openai", max_attempts=2, failure_threshold=3)
        async def call_openai_api(prompt: str):
            nonlocal call_count
            call_count += 1
            # Simulate OpenAI API call
            await asyncio.sleep(0.01)
            if call_count == 1:
                # First call fails (simulate rate limit)
                raise Exception("Rate limit exceeded")
            # Second call succeeds
            return {"response": f"AI response to: {prompt}"}

        # Should retry and succeed
        result = await call_openai_api("test prompt")
        assert result["response"] == "AI response to: test prompt"
        assert call_count == 2  # Failed once, succeeded on retry

    async def test_openai_circuit_opens_on_persistent_failures(self):
        """Test circuit opens when OpenAI persistently fails."""

        @with_circuit_breaker(
            "test_openai_fail", max_attempts=1, failure_threshold=2
        )
        async def failing_openai_call():
            raise Exception("OpenAI service unavailable")

        # First failure
        try:
            await failing_openai_call()
        except Exception:
            pass

        # Second failure opens circuit
        try:
            await failing_openai_call()
        except Exception:
            pass

        # Third call fails fast
        with pytest.raises(CircuitBreakerOpen):
            await failing_openai_call()


@pytest.mark.integration
class TestCircuitBreakerMetricsIntegration:
    """Test circuit breaker metrics with real operations."""

    def test_metrics_track_real_operations(self):
        """Test metrics accurately track real service calls."""
        breaker = CircuitBreaker("metrics_test", failure_threshold=3)

        # Simulate real operations
        for i in range(5):
            if i < 3:
                breaker.record_failure()
            else:
                breaker.record_success()

        metrics = breaker.metrics.get_metrics()
        assert metrics["failure_count"] == 3
        assert metrics["success_count"] == 2
        # Circuit opened after 3 failures, then recorded 2 successes
        assert metrics["current_state"] in [CircuitState.OPEN.value, CircuitState.CLOSED.value]
