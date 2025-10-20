# Integration Tests

This directory contains integration tests that require real service dependencies (MongoDB, Redis, S3, OpenAI).

> **📚 For comprehensive testing documentation covering all test types, CI/CD workflows, and best practices, see [Testing Guide](/docs/testing/guide.md)**

## Prerequisites

### Using Docker Compose (Recommended)

Start the test services:

```bash
cd apps/backend
docker-compose -f docker-compose.test.yml up -d
```

This will start:
- MongoDB on port 27018
- Redis on port 6380
- LocalStack (S3) on port 4566

Stop the services when done:

```bash
docker-compose -f docker-compose.test.yml down
```

### Manual Setup

If you prefer not to use Docker, ensure you have:
- MongoDB running on `mongodb://localhost:27017` (or configure `TEST_MONGODB_URI`)
- Redis running on port 6379 (or configure `TEST_REDIS_URL`)
- AWS credentials configured for S3 access (or LocalStack)

## Environment Variables

Configure in `.env` file (or use defaults):

```bash
# MongoDB Test Configuration (no authentication for local testing)
TEST_MONGODB_URI=mongodb://localhost:27018
TEST_MONGODB_DB=narrative_test

# Redis Test Configuration (no authentication for local testing)
TEST_REDIS_URL=redis://localhost:6380/0

# S3 Test Configuration (LocalStack with placeholder credentials)
# Note: LocalStack accepts any credentials - these never touch real AWS
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1
S3_ENDPOINT_URL=http://localhost:4566

# OpenAI Test Configuration (mocked, not used)
OPENAI_API_KEY=sk-test-key-for-mocking
```

**Security Note**: The test services run WITHOUT authentication for local testing only.
DO NOT use these configurations in production environments.

## Running Tests

### Run all integration tests:
```bash
uv run pytest tests/integration/ -v -m integration
```

### Run specific test file:
```bash
uv run pytest tests/integration/test_mongodb_fixtures.py -v -m integration
```

### Run with coverage:
```bash
uv run pytest tests/integration/ -v -m integration --cov=app --cov-report=term-missing
```

### Run specific test:
```bash
uv run pytest tests/integration/test_mongodb_fixtures.py::test_user_data_fixture -v -m integration
```

## Test Fixtures

### MongoDB Fixtures

Located in `tests/conftest.py`:

- `setup_database`: Initializes Beanie and cleans up after tests
- `mongo_client`: Provides a MongoDB client
- `test_user_data`: Creates a test UserData document
- `test_trained_model`: Creates a test TrainedModel document
- `test_batch_job`: Creates a test BatchJob document

Usage example:
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_example(test_user_data):
    assert test_user_data.id is not None
    assert test_user_data.user_id == "test_user_123"
```

### Redis Fixtures

Located in `tests/conftest.py`:

- `redis_client`: Provides a Redis client for testing
- `test_redis_job`: Creates a test job in Redis queue

Usage example:
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_example(redis_client):
    await redis_client.set("test_key", "test_value")
    value = await redis_client.get("test_key")
    assert value == "test_value"
```

### S3 Fixtures

Located in `tests/conftest.py`:

- `s3_client`: Provides an S3 client (LocalStack or real AWS)
- `test_s3_bucket`: Creates and manages a test S3 bucket
- `test_s3_file`: Uploads a test file to S3

Usage example:
```python
@pytest.mark.integration
def test_s3_example(s3_client, test_s3_bucket):
    s3_client.put_object(
        Bucket=test_s3_bucket,
        Key="test.txt",
        Body=b"test content"
    )
```

### OpenAI Fixtures

Located in `tests/conftest.py`:

- `mock_openai`: Mocks OpenAI API responses
- `test_openai_response`: Provides canned OpenAI responses

Usage example:
```python
@pytest.mark.integration
def test_openai_example(mock_openai):
    # OpenAI calls will be intercepted and mocked
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "test"}]
    )
    assert response is not None
```

## Test Isolation

Each test should be isolated and not depend on the state from other tests:

1. **Fixtures handle setup and teardown**: Use fixtures that automatically clean up after tests
2. **Use unique identifiers**: Generate unique IDs for test data to avoid collisions
3. **Clean database between tests**: The `setup_database` fixture clears all collections after each test
4. **Reset mocks**: Mock fixtures reset their state between tests

## Coverage Goals

- Target: >85% coverage for all integration test files
- Each fixture type should have comprehensive tests
- Test both success and failure scenarios
- Verify proper cleanup and isolation

## Troubleshooting

### MongoDB Connection Issues
```bash
# Check if MongoDB is running
docker ps | grep mongo

# Check MongoDB logs
docker logs narrative-mongodb-test
```

### Redis Connection Issues
```bash
# Check if Redis is running
docker ps | grep redis

# Test Redis connection (no password required for test instance)
redis-cli -p 6380 ping
```

### LocalStack/S3 Issues
```bash
# Check if LocalStack is running
docker ps | grep localstack

# Check LocalStack logs
docker logs narrative-localstack-test

# Test S3 endpoint
curl http://localhost:4566/_localstack/health
```

### Running Tests Without Docker

If tests fail because services aren't running:
1. Start services manually or use Docker Compose
2. Or skip integration tests: `pytest -m "not integration"`

## Best Practices

1. **Mark all integration tests**: Use `@pytest.mark.integration` decorator
2. **Use async fixtures**: For async operations, use `@pytest_asyncio.fixture`
3. **Clean up resources**: Always clean up test data in fixture teardown
4. **Test realistic scenarios**: Integration tests should simulate real-world usage
5. **Keep tests fast**: Use fixtures to share setup when possible
6. **Document complex tests**: Add docstrings explaining test purpose and setup
