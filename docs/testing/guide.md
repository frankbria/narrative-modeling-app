# Testing Guide - Narrative Modeling App

Comprehensive testing guide for the Narrative Modeling App covering unit tests, integration tests, and end-to-end (E2E) tests.

## Table of Contents

- [Overview](#overview)
- [Test Types](#test-types)
- [Running Tests](#running-tests)
  - [Backend Tests](#backend-tests)
  - [Frontend Tests](#frontend-tests)
- [Writing Tests](#writing-tests)
  - [Backend Unit Tests](#backend-unit-tests)
  - [Backend Integration Tests](#backend-integration-tests)
  - [Frontend E2E Tests](#frontend-e2e-tests)
- [Test Fixtures](#test-fixtures)
- [CI/CD Pipeline](#cicd-pipeline)
- [Troubleshooting](#troubleshooting)
- [Coverage Reports](#coverage-reports)
- [Best Practices](#best-practices)

---

## Overview

The Narrative Modeling App uses a comprehensive three-tier testing strategy:

1. **Unit Tests**: Fast, isolated tests without external dependencies (Backend: Python/pytest, Frontend: TypeScript/Jest)
2. **Integration Tests**: Tests with real service dependencies (MongoDB, Redis, S3, OpenAI)
3. **E2E Tests**: Full user workflow tests with Playwright across multiple browsers

### Test Coverage Goals

- **Backend Unit Tests**: >85% code coverage (currently: 190 tests passing)
- **Backend Integration Tests**: >90% service integration coverage (currently: 42 tests passing)
- **Frontend E2E Tests**: Critical user workflows (currently: 4 workflows across 3 browsers)

---

## Test Types

### Unit Tests

**Purpose**: Test individual functions and classes in isolation

**Characteristics**:
- No external service dependencies
- Fast execution (<5 seconds)
- Run on every PR
- Mocked external dependencies

**Backend**: Located in `apps/backend/tests/test_*`
- `test_security/` - Security utilities (PII detection, validation)
- `test_processing/` - Data processing logic
- `test_utils/` - Utility functions
- `test_model_training/` - ML model logic

**Frontend**: Located in `apps/frontend/__tests__/`
- Component tests with Jest and React Testing Library

### Integration Tests

**Purpose**: Test service integrations with real dependencies

**Characteristics**:
- Require running services (MongoDB, Redis, S3, OpenAI)
- Slower execution (~10-15 minutes)
- Run nightly in CI
- Use Docker Compose for service orchestration

**Backend**: Located in `apps/backend/tests/integration/`
- `test_mongodb_fixtures.py` - MongoDB operations
- `test_redis_fixtures.py` - Redis queue operations
- `test_s3_fixtures.py` - S3 file operations
- `test_openai_fixtures.py` - OpenAI API integration
- `test_upload_workflow.py` - Upload workflow E2E

### E2E Tests

**Purpose**: Test complete user workflows in real browsers

**Characteristics**:
- Real browser automation (Chromium, Firefox, WebKit)
- Full frontend + backend interaction
- Slowest execution (~30-45 minutes)
- Run on every PR to main
- Captures screenshots and videos on failure

**Frontend**: Located in `apps/frontend/e2e/workflows/`
- `upload-workflow.spec.ts` - File upload to processing
- `transform-workflow.spec.ts` - Data transformation
- `training-workflow.spec.ts` - Model training
- `prediction-workflow.spec.ts` - Model predictions

---

## Running Tests

### Backend Tests

#### All Backend Tests
```bash
cd apps/backend
PYTHONPATH=. uv run pytest -v
```

#### Unit Tests Only (No Database Required)
```bash
cd apps/backend
PYTHONPATH=. uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ \
  tests/test_model_training/test_problem_detector.py \
  tests/test_model_training/test_feature_engineer.py -v
```

#### Integration Tests Only (Requires Services)
```bash
cd apps/backend

# Start test services
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
PYTHONPATH=. uv run pytest tests/integration/ -v -m integration

# Stop services
docker-compose -f docker-compose.test.yml down -v
```

#### With Coverage
```bash
cd apps/backend
PYTHONPATH=. uv run pytest --cov=app --cov-report=term-missing --cov-report=xml -v
```

#### Specific Test File
```bash
cd apps/backend
PYTHONPATH=. uv run pytest tests/test_security/test_pii_detector.py -v
```

#### Specific Test Function
```bash
cd apps/backend
PYTHONPATH=. uv run pytest tests/test_security/test_pii_detector.py::test_detect_email -v
```

### Frontend Tests

#### All Frontend Unit Tests
```bash
cd apps/frontend
npm test
```

#### Watch Mode (Development)
```bash
cd apps/frontend
npm test -- --watch
```

#### With Coverage
```bash
cd apps/frontend
npm test -- --coverage
```

#### All E2E Tests
```bash
cd apps/frontend
npm run test:e2e
```

#### E2E Tests (Specific Browser)
```bash
cd apps/frontend
npm run test:e2e -- --project=chromium
npm run test:e2e -- --project=firefox
npm run test:e2e -- --project=webkit
```

#### E2E Tests (Interactive UI Mode)
```bash
cd apps/frontend
npm run test:e2e:ui
```

#### E2E Tests (Debug Mode)
```bash
cd apps/frontend
npm run test:e2e:debug
```

#### View E2E Test Report
```bash
cd apps/frontend
npm run test:e2e:report
```

---

## Writing Tests

### Backend Unit Tests

**Example: Testing a Pure Function**

```python
import pytest
from app.utils.validators import validate_email

@pytest.mark.unit
class TestEmailValidator:
    def test_valid_email(self):
        assert validate_email("test@example.com") == True

    def test_invalid_email(self):
        assert validate_email("not-an-email") == False

    def test_empty_email(self):
        with pytest.raises(ValueError):
            validate_email("")
```

**Example: Testing with Mocks**

```python
import pytest
from unittest.mock import Mock, patch
from app.services.data_processor import DataProcessor

@pytest.mark.unit
class TestDataProcessor:
    @pytest.fixture
    def processor(self):
        return DataProcessor()

    @patch('app.services.data_processor.openai_client')
    def test_analyze_data(self, mock_openai, processor):
        # Arrange
        mock_openai.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Analysis result"))]
        )

        # Act
        result = processor.analyze_data("test data")

        # Assert
        assert result == "Analysis result"
        mock_openai.chat.completions.create.assert_called_once()
```

**Example: Async Unit Test**

```python
import pytest
from app.services.dataset_service import DatasetService

@pytest.mark.unit
@pytest.mark.asyncio
class TestDatasetService:
    async def test_validate_dataset(self):
        service = DatasetService()
        result = await service.validate_dataset({"name": "test"})
        assert result.is_valid == True
```

### Backend Integration Tests

**Example: Testing MongoDB Operations**

```python
import pytest
from app.models.user_data import UserData

@pytest.mark.integration
@pytest.mark.asyncio
class TestUserDataModel:
    async def test_create_user_data(self, setup_database):
        # Arrange
        user_data = UserData(
            user_id="test_user_123",
            dataset_name="Test Dataset",
            file_path="s3://bucket/test.csv"
        )

        # Act
        await user_data.save()

        # Assert
        assert user_data.id is not None

        # Verify in database
        found = await UserData.find_one(UserData.user_id == "test_user_123")
        assert found is not None
        assert found.dataset_name == "Test Dataset"
```

**Example: Testing S3 Operations**

```python
import pytest

@pytest.mark.integration
class TestS3Upload:
    def test_upload_file(self, s3_client, test_s3_bucket):
        # Arrange
        test_content = b"test,data\n1,2\n3,4"
        key = "test_upload.csv"

        # Act
        s3_client.put_object(
            Bucket=test_s3_bucket,
            Key=key,
            Body=test_content
        )

        # Assert
        response = s3_client.get_object(Bucket=test_s3_bucket, Key=key)
        assert response['Body'].read() == test_content
```

**Example: Testing Redis Queue**

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
class TestRedisQueue:
    async def test_enqueue_job(self, redis_client):
        # Arrange
        job_data = {"task": "process_dataset", "dataset_id": "123"}

        # Act
        await redis_client.rpush("jobs:queue", str(job_data))

        # Assert
        result = await redis_client.lpop("jobs:queue")
        assert result is not None
```

### Frontend E2E Tests

**Example: Basic E2E Test**

```typescript
import { test, expect } from '../fixtures';

test.describe('Upload Workflow', () => {
  test('should upload CSV file successfully', async ({ authenticatedPage }) => {
    // Arrange
    await authenticatedPage.goto('/datasets/upload');

    // Act
    const fileInput = authenticatedPage.locator('input[type="file"]');
    await fileInput.setInputFiles('e2e/test-data/sample.csv');
    await authenticatedPage.click('button:has-text("Upload")');

    // Assert
    await expect(authenticatedPage.locator('text=Upload successful')).toBeVisible();
  });
});
```

**Example: E2E Test with Fixtures**

```typescript
import { test, expect } from '../fixtures';

test('complete upload and transform workflow', async ({
  authenticatedPage,
  uploadTestDataset,
  cleanupDataset
}) => {
  // Upload dataset
  const datasetId = await uploadTestDataset();

  try {
    // Navigate to dataset
    await authenticatedPage.goto(`/datasets/${datasetId}`);

    // Verify dataset loaded
    await expect(authenticatedPage.locator('h1')).toContainText('Dataset Details');

    // Apply transformation
    await authenticatedPage.click('button:has-text("Transform")');
    await authenticatedPage.selectOption('select[name="transform"]', 'normalize');
    await authenticatedPage.click('button:has-text("Apply")');

    // Assert transformation succeeded
    await expect(authenticatedPage.locator('text=Transformation complete')).toBeVisible();
  } finally {
    await cleanupDataset(datasetId);
  }
});
```

**Example: Page Object Pattern**

```typescript
// pages/UploadPage.ts
import { Page } from '@playwright/test';

export class UploadPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/datasets/upload');
  }

  async uploadFile(filePath: string) {
    const fileInput = this.page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);
    await this.page.click('button:has-text("Upload")');
  }

  async waitForUploadComplete() {
    await this.page.waitForSelector('text=Upload successful', { timeout: 30000 });
  }

  async getDatasetId(): Promise<string> {
    const url = this.page.url();
    const match = url.match(/datasets\/([^/]+)/);
    return match ? match[1] : '';
  }
}

// Usage in test
test('upload with page object', async ({ authenticatedPage }) => {
  const uploadPage = new UploadPage(authenticatedPage);

  await uploadPage.goto();
  await uploadPage.uploadFile('e2e/test-data/sample.csv');
  await uploadPage.waitForUploadComplete();

  const datasetId = await uploadPage.getDatasetId();
  expect(datasetId).toBeTruthy();
});
```

---

## Test Fixtures

### Backend Fixtures

All fixtures are defined in `apps/backend/tests/conftest.py`.

#### MongoDB Fixtures

**`setup_database`**: Initializes Beanie and cleans up after tests
```python
@pytest.mark.integration
async def test_example(setup_database):
    # Database is ready
    user_data = UserData(user_id="test")
    await user_data.save()
```

**`test_user_data`**: Creates a test UserData document
```python
@pytest.mark.integration
async def test_with_user_data(test_user_data):
    assert test_user_data.id is not None
    assert test_user_data.user_id == "test_user_123"
```

**`test_trained_model`**: Creates a test TrainedModel document
```python
@pytest.mark.integration
async def test_with_model(test_trained_model):
    assert test_trained_model.id is not None
```

#### Redis Fixtures

**`redis_client`**: Provides Redis client
```python
@pytest.mark.integration
async def test_redis(redis_client):
    await redis_client.set("key", "value")
    result = await redis_client.get("key")
    assert result == "value"
```

**`test_redis_job`**: Creates a test job in Redis
```python
@pytest.mark.integration
async def test_job(test_redis_job):
    assert test_redis_job["status"] == "pending"
```

#### S3 Fixtures

**`s3_client`**: Provides S3 client (LocalStack)
```python
@pytest.mark.integration
def test_s3(s3_client):
    s3_client.put_object(Bucket="test", Key="file.txt", Body=b"data")
```

**`test_s3_bucket`**: Creates and manages test bucket
```python
@pytest.mark.integration
def test_bucket(test_s3_bucket):
    assert test_s3_bucket.startswith("test-bucket-")
```

**`test_s3_file`**: Uploads test file
```python
@pytest.mark.integration
def test_file(test_s3_file):
    bucket, key = test_s3_file
    # File is already uploaded
```

#### OpenAI Fixtures

**`mock_openai`**: Mocks OpenAI API responses
```python
@pytest.mark.integration
def test_ai(mock_openai):
    # OpenAI calls are mocked
    response = openai.ChatCompletion.create(...)
```

### Frontend E2E Fixtures

All fixtures are defined in `apps/frontend/e2e/fixtures/`.

#### Authentication Fixtures

**`authenticatedPage`**: Provides logged-in page
```typescript
test('test with auth', async ({ authenticatedPage }) => {
  // Already authenticated
  await authenticatedPage.goto('/dashboard');
});
```

**`testUser`**: Provides test credentials
```typescript
test('test with user', async ({ testUser }) => {
  console.log(testUser.email); // test@narrativeml.com
});
```

#### Data Management Fixtures

**`uploadTestDataset`**: Uploads test dataset
```typescript
test('test with dataset', async ({ uploadTestDataset, cleanupDataset }) => {
  const datasetId = await uploadTestDataset();
  // ... test logic ...
  await cleanupDataset(datasetId);
});
```

**`cleanupDataset`**: Cleans up test dataset
```typescript
test('cleanup example', async ({ cleanupDataset }) => {
  const datasetId = "test-dataset-123";
  await cleanupDataset(datasetId);
});
```

---

## CI/CD Pipeline

### Pipeline Overview

The testing pipeline consists of three workflows that run automatically:

1. **Unit Tests** - Run on every PR and push to main
2. **E2E Tests** - Run on every PR and push to main
3. **Integration Tests** - Run nightly at 2 AM UTC

### Unit Tests Workflow

**File**: `.github/workflows/unit-tests.yml`

**Triggers**:
- Pull requests to main
- Pushes to main

**Jobs**:
1. **Backend Unit Tests** (15-minute timeout)
   - Python 3.11, uv package manager
   - Tests: `test_security/`, `test_processing/`, `test_utils/`
   - Coverage uploaded to Codecov (backend-unit flag)
   - Artifacts: `coverage.xml` (30-day retention)

2. **Frontend Unit Tests** (10-minute timeout)
   - Node 18, npm package manager
   - Tests: Jest with coverage
   - Coverage uploaded to Codecov (frontend-unit flag)
   - Artifacts: `coverage/` directory (30-day retention)

**Quality Gates**:
- All tests must pass for PR approval
- Coverage reports uploaded automatically
- Test failures block PR merging

### E2E Tests Workflow

**File**: `.github/workflows/e2e-tests.yml`

**Triggers**:
- Pull requests to main
- Pushes to main

**Configuration**:
- 60-minute timeout
- Browser matrix: Chromium, Firefox, WebKit
- Node 18, npm package manager
- Fail-fast: false (run all browsers)

**Environment Variables**:
- `CI=true`
- `SKIP_AUTH=true` (auth bypass for CI)

**Artifacts**:
1. **Test Results** (on failure)
   - Path: `apps/frontend/test-results/`
   - Name: `test-results-{browser}`
   - Retention: 30 days

2. **Playwright Report** (always)
   - Path: `apps/frontend/playwright-report/`
   - Name: `playwright-report-{browser}`
   - Retention: 30 days

**Quality Gates**:
- All E2E tests must pass across all browsers
- Test artifacts uploaded for debugging
- Browser matrix ensures cross-browser compatibility

### Integration Tests Workflow

**File**: `.github/workflows/integration-tests.yml`

**Triggers**:
- Schedule: Nightly at 2 AM UTC (`cron: '0 2 * * *'`)
- Manual: `workflow_dispatch` (manual trigger)

**Configuration**:
- 30-minute timeout
- Python 3.11, uv package manager
- Docker Compose for services

**Service Setup**:
1. MongoDB (port 27018)
2. Redis (port 6380)
3. LocalStack S3 (port 4566)

**Health Checks** (60s timeout each):
- MongoDB: `mongosh --eval "db.adminCommand('ping')"`
- Redis: `redis-cli ping`
- LocalStack: `curl http://localhost:4566/_localstack/health`

**Environment Variables**:
```bash
TEST_MONGODB_URI=mongodb://localhost:27018
TEST_MONGODB_DB=narrative_test
TEST_REDIS_URL=redis://localhost:6380/0
S3_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1
OPENAI_API_KEY=sk-test-key-for-mocking
```

**Artifacts**:
1. **Coverage Report** (always)
   - File: `coverage.xml`
   - Upload: Codecov (backend-integration flag)
   - Retention: 30 days

2. **Test Results** (on failure)
   - Path: `apps/backend/test-results/`
   - Name: `integration-test-results`
   - Retention: 30 days

**Cleanup**:
- Always runs (even on failure)
- `docker-compose down -v`
- Removes containers and volumes

**Quality Gates**:
- All integration tests must pass
- Real service dependencies validated
- Coverage reports uploaded
- Proper cleanup prevents resource leaks

### Workflow Execution Times

| Workflow | Expected Duration | Timeout |
|----------|------------------|---------|
| Backend Unit Tests | ~5-8 minutes | 15 minutes |
| Frontend Unit Tests | ~3-5 minutes | 10 minutes |
| E2E Tests (per browser) | ~15-30 minutes | 60 minutes |
| Integration Tests | ~10-15 minutes | 30 minutes |

### Manual Workflow Triggers

**Integration Tests** (via GitHub UI):
1. Go to Actions tab
2. Select "Integration Tests" workflow
3. Click "Run workflow"
4. Select branch
5. Click "Run workflow" button

---

## Troubleshooting

### Backend Unit Test Issues

#### Tests Hang During Import
**Symptom**: pytest hangs before collecting tests

**Cause**: App initialization in module-level imports

**Fix**: Move imports inside fixture functions or test methods

#### MongoDB Connection Errors in Unit Tests
**Symptom**: `pymongo.errors.ServerSelectionTimeoutError`

**Cause**: Test uses `setup_database` fixture but not marked as integration

**Fix**: Add `@pytest.mark.integration` decorator
```python
@pytest.mark.integration  # Add this
@pytest.mark.asyncio
async def test_example(setup_database):
    # Test code
```

#### CircuitBreakerOpen Wrapped in RetryError
**Symptom**: Test expects `CircuitBreakerOpen` but gets `RetryError`

**Explanation**: Tenacity's `@retry` wraps all exceptions

**Fix**: Check the `__cause__` attribute
```python
with pytest.raises(RetryError) as exc_info:
    await failing_operation()

assert isinstance(exc_info.value.__cause__, CircuitBreakerOpen)
```

### Backend Integration Test Issues

#### MongoDB Connection Issues
```bash
# Check if MongoDB is running
docker ps | grep mongo

# Check MongoDB logs
docker logs narrative-mongodb-test

# Test connection
mongosh --host localhost --port 27018
```

#### Redis Connection Issues
```bash
# Check if Redis is running
docker ps | grep redis

# Test Redis connection
redis-cli -p 6380 ping
```

#### LocalStack/S3 Issues
```bash
# Check if LocalStack is running
docker ps | grep localstack

# Check LocalStack logs
docker logs narrative-localstack-test

# Test S3 endpoint
curl http://localhost:4566/_localstack/health
```

#### Running Tests Without Docker
If tests fail because services aren't running:
1. Start services: `docker-compose -f docker-compose.test.yml up -d`
2. Or skip integration tests: `pytest -m "not integration"`

### Frontend E2E Test Issues

#### Tests Timeout
**Solution**:
- Increase timeout: `test.setTimeout(60000)`
- Check if dev server is running
- Verify BASE_URL is correct

#### Authentication Issues
**Solution**:
- Set `SKIP_AUTH=true` for development
- Verify test user credentials
- Check auth UI selectors in `fixtures/auth.ts`

#### Page Not Found
**Solution**:
- Ensure dev server is running: `npm run dev`
- Check route exists in Next.js app
- Verify BASE_URL environment variable

#### Flaky Tests
**Solution**:
- Use Playwright's auto-waiting instead of fixed timeouts
- Ensure tests are isolated
- Check for race conditions

#### Browser Not Installed
**Solution**:
```bash
cd apps/frontend
npx playwright install
```

### General CI/CD Issues

#### Workflow Fails to Start
**Check**:
- Workflow file syntax (YAML validation)
- Required secrets configured (CODECOV_TOKEN)
- Branch protection rules

#### Artifacts Not Uploaded
**Check**:
- Path exists in workflow
- Artifact name is unique
- Retention policy not exceeded

#### Coverage Not Reported
**Check**:
- Codecov token configured
- Coverage file generated
- Network connectivity to Codecov

---

## Coverage Reports

### Backend Coverage

**Generate Coverage Report**:
```bash
cd apps/backend
PYTHONPATH=. uv run pytest --cov=app --cov-report=term-missing --cov-report=xml -v
```

**View Coverage in Terminal**:
```bash
PYTHONPATH=. uv run pytest --cov=app --cov-report=term-missing
```

**Generate HTML Coverage Report**:
```bash
PYTHONPATH=. uv run pytest --cov=app --cov-report=html
open htmlcov/index.html
```

**Coverage Goals**:
- **Unit Tests**: >85% coverage
- **Integration Tests**: ~90% coverage
- **Combined**: >85% overall backend coverage

**Current Coverage**:
- Unit tests: 190 tests, >85% coverage
- Integration tests: 42 tests, ~90% coverage

### Frontend Coverage

**Generate Coverage Report**:
```bash
cd apps/frontend
npm test -- --coverage
```

**View Coverage in Terminal**:
Coverage is automatically displayed after running tests

**Coverage Goals**:
- **Jest Tests**: >80% coverage
- **E2E Tests**: Behavioral validation (not coverage-based)

### Codecov Integration

**Coverage Tracking**:
- **Tool**: Codecov
- **Dashboard**: https://codecov.io/gh/{org}/{repo}

**Flags**:
- `backend-unit` - Backend unit test coverage
- `frontend-unit` - Frontend unit test coverage
- `backend-integration` - Integration test coverage

**Upload**: Automatic on every test run in CI

**Viewing Reports**:
1. Visit Codecov dashboard
2. View coverage trends over time
3. Compare coverage across PRs
4. Identify uncovered code

---

## Best Practices

### General Testing Principles

1. **Test Pyramid**: More unit tests, fewer integration tests, even fewer E2E tests
2. **Test Isolation**: Each test should be independent and not rely on others
3. **Descriptive Names**: Test names should clearly describe what is being tested
4. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification
5. **DRY with Caution**: Extract common test code, but keep tests readable
6. **Fast Tests**: Keep unit tests fast (<1 second each)

### Backend Testing Best Practices

1. **Mark All Tests**: Use `@pytest.mark.unit` or `@pytest.mark.integration`
2. **Use Appropriate Fixtures**: Don't use database fixtures for unit tests
3. **Mock External Services**: Mock S3, OpenAI, external APIs in unit tests
4. **Test Error Paths**: Test both success and failure scenarios
5. **Cleanup After Tests**: Use fixtures for automatic cleanup
6. **Avoid App Imports in Unit Tests**: Use lazy imports to prevent app initialization

### Frontend E2E Testing Best Practices

1. **Use Page Objects**: Encapsulate page interactions in page objects
2. **Use Fixtures**: Leverage fixtures for common setup/teardown
3. **Wait Properly**: Use Playwright's auto-waiting, avoid arbitrary timeouts
4. **Isolate Tests**: Each test should be independent
5. **Clean Up**: Always clean up test data in finally blocks
6. **Parallel Tests**: Tests run in parallel - ensure isolation
7. **Descriptive Assertions**: Use clear, descriptive assertions

### Integration Testing Best Practices

1. **Real Services**: Use real MongoDB, Redis, S3 (LocalStack)
2. **Docker Compose**: Use `docker-compose.test.yml` for consistency
3. **Health Checks**: Wait for services to be ready before testing
4. **Test Realistic Scenarios**: Simulate real-world usage patterns
5. **Keep Tests Fast**: Use fixtures to share setup when possible
6. **Document Complex Tests**: Add docstrings explaining test purpose

### CI/CD Best Practices

1. **Separation of Concerns**: Unit tests on every PR, integration tests nightly
2. **Quality Gates**: Test failures block PR merging
3. **Artifact Management**: Preserve test results and coverage reports
4. **Resource Efficiency**: Use appropriate timeouts, clean up Docker resources
5. **Developer Experience**: Manual triggers for integration tests, clear failure reporting
6. **Security**: No secrets in workflow files, use environment variables

---

## Quick Reference

### Common Test Commands

```bash
# Backend - All tests
cd apps/backend && PYTHONPATH=. uv run pytest -v

# Backend - Unit tests only (fast)
cd apps/backend && PYTHONPATH=. uv run pytest -m "not integration" -v

# Backend - Integration tests only
cd apps/backend && PYTHONPATH=. uv run pytest -m integration -v

# Backend - With coverage
cd apps/backend && PYTHONPATH=. uv run pytest --cov=app --cov-report=term-missing -v

# Frontend - Unit tests
cd apps/frontend && npm test

# Frontend - Unit tests with coverage
cd apps/frontend && npm test -- --coverage

# Frontend - E2E tests
cd apps/frontend && npm run test:e2e

# Frontend - E2E tests (specific browser)
cd apps/frontend && npm run test:e2e -- --project=chromium
```

### Docker Commands for Integration Tests

```bash
# Start services
cd apps/backend && docker-compose -f docker-compose.test.yml up -d

# Check service status
docker ps

# View logs
docker logs narrative-mongodb-test
docker logs narrative-redis-test
docker logs narrative-localstack-test

# Stop services
cd apps/backend && docker-compose -f docker-compose.test.yml down -v
```

### CI Workflow Trigger Commands

```bash
# View workflow status
gh workflow view

# Run integration tests manually
gh workflow run integration-tests.yml

# View workflow logs
gh run view --log
```

---

## Additional Resources

- **Backend Integration Tests**: `apps/backend/tests/integration/README.md`
- **Frontend E2E Tests**: `apps/frontend/e2e/README.md`
- **Backend Infrastructure**: `apps/backend/docs/TEST_INFRASTRUCTURE.md`
- **Sprint 9 Documentation**: `apps/backend/tests/integration/STORY_9.*_IMPLEMENTATION.md`
- **CI/CD Workflows**: `.github/workflows/`

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check the specific README files for backend integration or E2E tests
2. Review the TEST_INFRASTRUCTURE.md for backend test architecture
3. Examine CI workflow logs for CI/CD issues
4. Consult the troubleshooting sections above
5. Review existing tests for examples

---

**Last Updated**: Sprint 9 Story 9.5 - Test Documentation
**Coverage**: Unit Tests (190), Integration Tests (42), E2E Tests (4 workflows × 3 browsers)
**CI Status**: ✅ All tests passing across all test types
