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

  await uploadPage.goto('/datasets/upload');
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

- `BASE_URL`: Base URL for tests (default: http://localhost:3000)
- `SKIP_AUTH`: Skip authentication (set to 'true' for dev)
- `TEST_USER_EMAIL`: Test user email
- `TEST_USER_PASSWORD`: Test user password

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
- Set `SKIP_AUTH=true` for development
- Verify test user credentials
- Check auth UI selectors in `fixtures/auth.ts`

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
