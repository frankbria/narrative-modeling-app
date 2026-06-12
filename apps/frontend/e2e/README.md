# E2E Testing with Playwright

This directory contains end-to-end tests for the Narrative Modeling App using Playwright.

> **📚 For comprehensive testing documentation covering all test types, CI/CD workflows, and best practices, see [Testing Guide](/docs/testing/guide.md)**

## Structure

```
e2e/
├── fixtures/           # Test fixtures (auth, data management)
│   ├── auth.ts        # Authentication fixtures
│   ├── data.ts        # Data management fixtures
│   └── index.ts       # Combined exports
├── pages/             # Page Object Models
│   ├── BasePage.ts    # Base page object with common methods
│   └── UploadPage.ts  # Upload page object
├── workflows/         # E2E workflow tests
│   └── setup.spec.ts  # Setup validation tests
├── utils/             # Utility functions
└── test-data/         # Test data files
    └── sample.csv     # Sample CSV for testing
```

## Prerequisites

The harness (`test-e2e.sh`) starts the backend and frontend itself, but two services must already be running:

- **MongoDB** on `localhost:27017`
- **S3-compatible storage** — upload workflows hard-require it (issue #191). Start LocalStack first:
  ```bash
  docker compose -f ../backend/docker-compose.test.yml up -d localstack
  ```
  `test-e2e.sh` auto-detects LocalStack on `:4566` and exports `AWS_ENDPOINT_URL`; the seed script creates the `test-bucket` bucket. To use other S3-compatible storage (e.g. MinIO), set `AWS_ENDPOINT_URL` (and real credentials — values starting with `test-` put parts of the backend in mock mode) before running.

Without storage the harness prints a loud warning and every upload-dependent spec fails in `beforeEach` with a `uploadTestDataset failed at "upload ..."` error naming the backend failure.

If the upload flow's UI changes, run `workflows/upload-fixture-smoke.spec.ts` first — it validates the shared upload fixture in isolation and fails with a precise step-level error before other specs die opaquely.

## Running Tests

### Smoke Tests (Fast - ~5-7 minutes)
Quick validation of critical paths:
```bash
npm run test:e2e:smoke
```

### Full Suite Tests (~20-30 minutes)
Comprehensive testing on Chromium:
```bash
npm run test:e2e:full
```

All browsers (Chromium, Firefox, WebKit):
```bash
npm run test:e2e:all
```

### Legacy Commands
All tests (default):
```bash
npm run test:e2e
```

### Interactive UI Mode
```bash
npm run test:e2e:ui
```

### Debug Mode
```bash
npm run test:e2e:debug
```

### View Test Report
```bash
npm run test:e2e:report
```

## Test Strategy

### Smoke Tests (@smoke) - 13 tests
Fast, critical-path tests that run on every PR:

- **Setup**: Infrastructure validation (2 tests)
- **Upload**: CSV upload workflow (3 tests)
- **Transform**: Basic transformations (2 tests)
- **Train**: Model training flow (4 tests)
- **Predict**: Predictions (2 tests)

### Full Suite - 129 tests
Comprehensive E2E testing that runs on main branch:

- All smoke tests
- Edge cases and error scenarios
- All transformation types
- All ML algorithms
- Security validation
- Performance testing

## CI/CD Integration

**Pull Requests** → Smoke tests only
- Workflow: `.github/workflows/smoke-tests.yml`
- Duration: ~5-7 minutes
- Browser: Chromium only

**Main Branch** → Full suite
- Workflow: `.github/workflows/e2e-tests.yml`
- Duration: ~20-30 minutes per browser
- Browsers: Chromium, Firefox, WebKit

## Test Fixtures

### Authentication Fixture
Provides automatic authentication for tests:

```typescript
import { test, expect } from '../fixtures';

test('my test', async ({ authenticatedPage }) => {
  // authenticatedPage is already logged in
  await expect(authenticatedPage).toHaveURL(/dashboard/);
});
```

### Test User Fixture
Provides test user credentials:

```typescript
test('user test', async ({ testUser }) => {
  console.log(testUser.email); // test@narrativeml.com
});
```

### Data Fixtures
Utilities for test data management:

```typescript
test('upload test', async ({ uploadTestDataset, cleanupDataset }) => {
  const datasetId = await uploadTestDataset();

  // ... test logic ...

  await cleanupDataset(datasetId);
});
```

## Page Objects

Page objects encapsulate page interactions:

```typescript
import { UploadPage } from '../pages/UploadPage';

test('upload', async ({ authenticatedPage }) => {
  const uploadPage = new UploadPage(authenticatedPage);

  await uploadPage.goto('/upload');
  await uploadPage.uploadFile('path/to/file.csv');
  await uploadPage.waitForUploadComplete();

  const datasetId = await uploadPage.getDatasetId();
});
```

## Writing Tests

### Basic Test Structure
```typescript
import { test, expect } from '../fixtures';

test.describe('Feature Name', () => {
  test('should do something', async ({ authenticatedPage }) => {
    // Arrange
    await authenticatedPage.goto('/some-page');

    // Act
    await authenticatedPage.click('button');

    // Assert
    await expect(authenticatedPage.locator('text=Success')).toBeVisible();
  });
});
```

### With Fixtures
```typescript
test('upload workflow', async ({
  authenticatedPage,
  uploadTestDataset,
  cleanupDataset
}) => {
  const datasetId = await uploadTestDataset();

  try {
    // Test logic
    await authenticatedPage.goto(`/datasets/${datasetId}`);
    // ...
  } finally {
    await cleanupDataset(datasetId);
  }
});
```

## Environment Variables

- `BASE_URL`: Base URL for tests (default: http://localhost:3010)
- `TEST_USER_EMAIL`: Test user email for E2E authentication (default: test@narrativeml.com)
- `TEST_USER_PASSWORD`: Test user password for E2E authentication (default: test-password-123)

## CI/CD Integration

Tests run automatically on:
- Pull requests to main
- Pushes to main

See `.github/workflows/e2e-tests.yml` for configuration.

## Debugging

### Screenshots
Screenshots are captured on failure and saved to `test-results/`

### Videos
Videos are captured on failure and saved to `test-results/`

### Traces
Traces are captured on first retry and can be viewed with:
```bash
npx playwright show-trace path/to/trace.zip
```

### Debug in VS Code
1. Set breakpoint in test
2. Run test in debug mode: `npm run test:e2e:debug`
3. Playwright Inspector will open

## Best Practices

1. **Use Page Objects**: Encapsulate page interactions in page objects
2. **Use Fixtures**: Leverage fixtures for common setup/teardown
3. **Descriptive Names**: Use clear, descriptive test names
4. **Isolate Tests**: Each test should be independent
5. **Clean Up**: Always clean up test data
6. **Wait Properly**: Use Playwright's auto-waiting; avoid arbitrary timeouts
7. **Parallel Tests**: Tests run in parallel by default - ensure isolation

## Troubleshooting

### Tests Timeout
- Increase timeout in test: `test.setTimeout(60000)`
- Check if dev server is running
- Verify BASE_URL is correct

### Authentication Issues
- Verify `TEST_USER_EMAIL` and `TEST_USER_PASSWORD` match the test user credentials
- Ensure Playwright global setup successfully signs in and saves storage state to `e2e/.auth/user.json`
- Check that the dev server is running in development mode (enables Credentials provider)
- Verify auth UI selectors in `e2e/global-setup.ts` match the signin page

### Page Not Found
- Ensure dev server is running: `npm run dev`
- Check route exists in Next.js app

### Flaky Tests
- Use Playwright's auto-waiting instead of fixed timeouts
- Ensure tests are isolated and don't depend on each other
- Check for race conditions in the application

## Coverage

Story 9.1 Acceptance Criteria:
- ✅ Playwright configured for Chromium, Firefox, and WebKit
- ✅ Test fixtures for authenticated users and test data
- ✅ Parallel test execution enabled
- ✅ Screenshots and videos captured on failure
- ✅ Can run `npm run test:e2e` successfully

## Next Steps

1. Add more page objects (TransformPage, TrainPage, etc.)
2. Implement critical workflow tests (Story 9.2)
3. Add integration with test services (Story 9.3)
4. Expand CI/CD pipeline (Story 9.4)
