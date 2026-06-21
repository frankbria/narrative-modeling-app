# Test Infrastructure Documentation

## Overview

This document describes the test infrastructure setup for the backend application, including test organization, fixtures, and best practices.

> **📚 For a comprehensive testing guide covering all test types (unit, integration, E2E) and CI/CD workflows, see [Testing Guide](/docs/testing/guide.md).**

## Type checking (mypy, blocking — issue #219)

CI runs mypy as a **blocking** gate: a plain `uv run mypy app/` that fails on any error. The pre-existing-error baseline (`apps/backend/mypy-baseline.txt`) was burned down to zero and removed (#226), so there is nothing to tolerate.

- **Check locally the way CI does:** `uv run mypy app/` — must report `Success: no issues found`.

## Service Prerequisites

The full backend suite (`uv run pytest`) passes locally with these services
(issue #160 acceptance criteria). Tests whose optional service is unavailable
**skip with an explicit reason** naming the prerequisite; they never fail for
a missing service.

| Service | Endpoint | Needed by | How to start | If absent |
|---|---|---|---|---|
| MongoDB | `localhost:27017` (`TEST_MONGODB_URI`) | `tests/test_api/`, `tests/test_integration/`, `tests/integration/`, `tests/load/`, any test using `setup_database` or the app lifespan | local `mongod` (or Docker) | **required** — DB-backed tests error |
| Redis (test instance) | `localhost:6380` (`TEST_REDIS_URL`) | `tests/integration/test_redis_fixtures.py` and other tests using the `redis_client` fixture | `docker compose -f docker-compose.test.yml up -d` | tests skip with reason |
| S3 (LocalStack) | `localhost:4566` (`S3_ENDPOINT_URL`) | `tests/integration/test_s3_fixtures.py` and S3-gated integration tests | `docker compose -f docker-compose.test.yml up -d` | tests skip with reason (fail in CI) |
| OpenAI | n/a (mocked) | `tests/integration/test_openai_fixtures.py` | never calls the network: AI tests mock the client | tests still run (no service needed) |

Notes:
- **`CI_REQUIRE_SERVICES` (issue #221):** locally, a test whose backing service
  is unavailable skips with a reason (the Redis/S3 rows above). In CI we
  provision the services on purpose, so `ci.yml`'s `backend-integration` job sets
  `CI_REQUIRE_SERVICES=true` and `require_service()` (`tests/conftest.py`)
  **fails** instead of skipping — the gate can never go green while silently
  under-testing S3/Redis. LocalStack is therefore a hard requirement of the job
  (the workflow `exit 1`s if LocalStack never becomes healthy).
- `tests/conftest.py` sets `ENVIRONMENT=test` (via `os.environ.setdefault`) at
  module scope, before any app import. This satisfies the `SKIP_AUTH` guard
  introduced in issue #149, which requires every set environment signal to be
  explicitly `development` or `test`. If you export `ENVIRONMENT` in your shell
  before running pytest, that value takes precedence (setdefault does not
  override an already-set variable).
- During pytest runs the app lifespan is pointed at the **test** database
  (`tests/conftest.py::_point_app_at_test_database`); it never touches the
  production `MONGODB_URI`.
- The canonical Beanie model list lives in `app/models/registry.py` and is
  shared by the app lifespan and the `setup_database` fixture.
- The dev Redis (6379) is deliberately not used by tests; the test instance
  runs on **6380** to avoid clobbering dev data.

### CI encoding

- `.github/workflows/ci.yml` — the primary PR gate (issue #150). Runs the
  service-free backend paths (`backend-unit`) plus `backend-integration`, which
  provisions a MongoDB **service container** (27017) and Redis + LocalStack via
  `docker-compose.test.yml`. It also runs frontend (eslint/tsc/build/jest) and
  MCP pytest, and exposes the aggregate `CI Success` status. Requirements are
  documented in the workflow header. All three services are **hard requirements**
  (`CI_REQUIRE_SERVICES=true`): the S3/upload/OpenAI integration suites run in
  the gate and a missing service fails the job instead of skipping (#221).
- `.github/workflows/integration-tests.yml` (manual trigger) — the standalone
  integration run; provisions Redis + LocalStack via `docker-compose.test.yml`
  and uses an Atlas test cluster for MongoDB. Requirements in the workflow header.

## Test Organization

### Test Markers

Tests are organized using pytest markers to separate unit and integration tests:

- **`@pytest.mark.unit`**: Unit tests that don't require external services (MongoDB, Redis, AWS)
- **`@pytest.mark.integration`**: Integration tests that require external services and database connections

### Directory Structure

```
tests/
├── conftest.py                  # Root fixtures with lazy imports
├── test_utils/
│   ├── conftest.py             # Unit test fixtures (no app initialization)
│   ├── test_circuit_breaker.py # Circuit breaker unit tests
│   ├── test_plotting.py        # Plotting utility tests
│   ├── test_s3.py              # S3 utility tests
│   └── test_schema_inference.py # Schema inference tests
├── test_middleware/
│   ├── conftest.py             # Minimal FastAPI app for middleware
│   └── test_api_version.py     # API versioning middleware tests
├── test_security/
│   ├── test_monitoring.py      # @pytest.mark.unit - Monitoring tests
│   ├── test_pii_detector.py    # @pytest.mark.unit - PII detection tests
│   └── test_upload_handler.py  # @pytest.mark.integration - Upload handler tests
├── test_services/
│   ├── conftest.py                  # Service test fixtures
│   ├── test_s3_endpoint_url.py      # AWS_ENDPOINT_URL / S3-compatible storage tests
│   ├── test_versioning_service.py   # Versioning service tests
│   └── ...                          # Other service unit/integration tests
├── test_processing/
│   └── ...                     # Data processing unit tests
└── test_model_training/
    └── ...                     # ML model training unit tests
```

## Lazy Loading Pattern

### Problem

Previously, `tests/conftest.py` imported `app.main` at module level, causing full FastAPI application initialization even for unit tests that don't need it. This led to:
- Tests hanging during import
- MongoDB connection attempts for unit tests
- Slow test execution

### Solution

Implemented lazy loading pattern where all app-related imports are moved inside fixture functions:

**Before:**
```python
import pytest
from app.main import app
from app.config import settings
# ... more imports

@pytest_asyncio.fixture(scope="function")
async def setup_database(request):
    client = AsyncIOMotorClient(settings.TEST_MONGODB_URI)
    # ... setup code
```

**After:**
```python
import pytest

@pytest_asyncio.fixture(scope="function")
async def setup_database(request):
    """Set up test database before each test and clean up after.

    Only runs for tests marked with @pytest.mark.integration
    """
    # Skip for unit tests
    if "unit" in request.keywords:
        yield
        return

    # Lazy imports for integration tests
    from motor.motor_asyncio import AsyncIOMotorClient
    from beanie import init_beanie
    from app.config import settings
    # ... rest of imports

    client = AsyncIOMotorClient(settings.TEST_MONGODB_URI)
    # ... setup code
```

## Test Fixtures

### Root Fixtures (`tests/conftest.py`)

- **`setup_database`**: Initializes MongoDB for integration tests, skips for unit tests
- **`async_test_client`**: Creates async test client for FastAPI (lazy imports app)
- **`authorized_client`**: Sync test client with auth override
- **`async_authorized_client`**: Async test client with auth override
- **`mock_user_id`**: Returns test user ID
- **`mock_dataset_id`**: Returns test dataset ID
- **`mock_user_data`**: Creates mock UserData object

### Utils Fixtures (`tests/test_utils/conftest.py`)

Minimal conftest for pure unit tests:
```python
"""
Unit test configuration for utils tests.

These tests don't require FastAPI app or database initialization.
"""

import pytest

# No app imports here - these are pure unit tests
# Tests in this directory should be marked with @pytest.mark.unit
```

### Middleware Fixtures (`tests/test_middleware/conftest.py`)

Provides minimal FastAPI app for middleware testing:
```python
import pytest
from fastapi import FastAPI

@pytest.fixture
def minimal_app():
    """Create a minimal FastAPI app for middleware testing."""
    return FastAPI()
```

## Running Tests

### Unit Tests Only

```bash
# Run all unit tests (fast, no MongoDB required)
PYTHONPATH=. uv run pytest -m "not integration" -v

# Run specific test directories
PYTHONPATH=. uv run pytest tests/test_utils/ tests/test_middleware/ -v

# Run with quiet mode and no traceback
PYTHONPATH=. uv run pytest -m "not integration" -q --tb=no
```

### Integration Tests Only

```bash
# Requires MongoDB running
PYTHONPATH=. uv run pytest -m integration -v
```

### All Tests

```bash
# Runs both unit and integration tests
PYTHONPATH=. uv run pytest -v
```

## Test Results Summary

Current test status (as of Story 8.3 completion):
- **190 unit tests passing**
- **9 integration tests** (require MongoDB)
- **1 skipped** (deprecated version test)

### Test Distribution

- Utils: 53 tests
- Middleware: 21 tests
- Security: 21 tests (12 unit, 9 integration)
- Processing: 66 tests
- Model Training: 22 tests
- **Total: 190 unit tests, all passing**

## Circuit Breaker Tests

Location: `tests/test_utils/test_circuit_breaker.py`

**28 tests covering:**
- Metrics tracking (thread-safe)
- State machine transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Fail-fast behavior when circuit is OPEN
- Recovery timeout logic
- Consecutive failure/success tracking
- Decorator usage (async and sync)
- Global circuit breaker management
- Exception handling (CircuitBreakerOpen)

**Key fixes:**
1. Fixed exception type expectations (tenacity wraps in `RetryError`)
2. Fixed HALF_OPEN state call counter increment
3. Added unique service names to prevent test contamination
4. Verified proper state transitions and limits

## API Versioning Tests

Location: `tests/test_middleware/test_api_version.py`

**21 tests covering:**
- Version parsing from Accept header
- Version parsing from URL path
- Default version behavior
- Unsupported version handling (406 responses)
- Deprecation warnings
- Version headers in responses
- Version negotiation priority (URL > Header > Default)
- Error handling (malformed patterns, missing headers)

**Key fix:**
- Updated middleware to handle both `request.path` and `request.url.path` for compatibility with starlette's TestClient

## Best Practices

### 1. Mark All Tests

```python
@pytest.mark.unit
class TestMyFeature:
    def test_something(self):
        # Unit test code
        pass

@pytest.mark.integration
class TestMyIntegration:
    async def test_with_database(self, setup_database):
        # Integration test code
        pass
```

### 2. Use Appropriate Fixtures

- Unit tests: Don't use `setup_database`, `authorized_client` if not needed
- Integration tests: Mark with `@pytest.mark.integration` and use fixtures

### 3. Avoid App Imports in Test Files

For unit tests, avoid importing from `app.main` or other modules that trigger app initialization. If you need app components:

```python
# Bad (for unit tests)
from app.main import app
from app.config import settings

# Good (lazy import in test)
def test_something():
    from app.utils.some_util import utility_function
    # Test the utility function
```

### 4. Create Conftest for New Test Directories

When adding a new test directory, create a `conftest.py` that either:
- Provides minimal fixtures (like `test_utils/conftest.py`)
- Provides specialized fixtures (like `test_middleware/conftest.py`)

## Troubleshooting

### Tests Hang During Import

**Symptom**: pytest hangs before collecting tests

**Cause**: App initialization in module-level imports

**Fix**: Move imports inside fixture functions or test methods

### MongoDB Connection Errors in Unit Tests

**Symptom**: `pymongo.errors.ServerSelectionTimeoutError` in unit tests

**Cause**: Test is using `setup_database` fixture but not marked as integration

**Fix**: Add `@pytest.mark.integration` decorator to test class

### CircuitBreakerOpen Wrapped in RetryError

**Symptom**: Test expects `CircuitBreakerOpen` but gets `RetryError`

**Explanation**: Tenacity's `@retry` decorator wraps all exceptions, including non-retriable ones

**Fix**: Check the `__cause__` attribute:
```python
with pytest.raises(RetryError) as exc_info:
    await failing_operation()

assert isinstance(exc_info.value.__cause__, CircuitBreakerOpen)
```

## Future Improvements

1. Add pytest-timeout plugin for better test timeout handling
2. Consider test parallelization with pytest-xdist
3. Add coverage reporting with pytest-cov
4. Create test data factories for common test objects
5. Add performance benchmarking for critical paths

---

## Related Documentation

- **[Comprehensive Testing Guide](/docs/testing/guide.md)** - Complete guide for all test types
- **[Integration Tests README](/apps/backend/tests/integration/README.md)** - Integration test setup and usage
- **[E2E Tests README](/apps/frontend/e2e/README.md)** - End-to-end testing with Playwright
- **[CI/CD Workflows](/.github/workflows/)** - Automated testing pipelines
- **[Sprint 9 Implementation](/apps/backend/tests/integration/)** - Sprint 9 story implementation docs
