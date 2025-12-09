# E2E Testing Guide for Narrative Modeling App

## Overview

This guide covers the comprehensive End-to-End (E2E) testing infrastructure for the Narrative Modeling App, including setup, execution, and best practices.

## Test Infrastructure

### Framework: Playwright

- **Version**: Latest
- **Language**: TypeScript
- **Pattern**: Page Object Model (POM)
- **Fixtures**: Custom fixtures for authentication, data, and AI mocking
- **Location**: `apps/frontend/e2e/`

### Test Suite Statistics

- **Total Test Specs**: 14 (6 existing + 8 new)
- **Total Tests**: 268+ tests
- **Test Categories**:
  - Workflow tests (upload, transform, train, predict): 129 tests
  - Dataset metadata: 15 tests
  - Transformation config: 17 tests
  - Model config: 19 tests
  - Data versioning: 13 tests
  - Complete AI workflow: 9 tests
  - AI recommendations: 15 tests
  - Performance: 21 tests
  - Production readiness: 24 tests
  - Error scenarios: 24 tests

## Project Structure

```
apps/frontend/e2e/
├── fixtures/
│   ├── index.ts                 # Combined fixtures
│   ├── auth.ts                  # Authentication fixtures
│   ├── data.ts                  # Data upload/cleanup fixtures
│   └── ai-mock.ts               # AI mocking provider
├── pages/
│   ├── BasePage.ts              # Base page object
│   ├── UploadPage.ts            # File upload page
│   ├── TransformPage.ts         # Transformation page
│   ├── TrainPage.ts             # Model training page
│   ├── PredictPage.ts           # Prediction page
│   ├── DatasetPage.ts           # Dataset metadata page
│   ├── ModelConfigPage.ts       # Model configuration page
│   ├── VersioningPage.ts        # Data versioning page
│   └── WorkflowPage.ts          # AI workflow orchestration
├── helpers/
│   ├── PerformanceMonitor.ts    # Performance metrics collection
│   ├── ConsoleErrorCollector.ts # Console error monitoring
│   ├── SecurityTester.ts        # Security testing utilities
│   ├── WorkflowOrchestrator.ts  # Multi-step workflow coordination
│   └── index.ts                 # Helper exports
├── workflows/
│   ├── setup.spec.ts            # Infrastructure validation
│   ├── upload.spec.ts           # Dataset upload workflows
│   ├── transform.spec.ts        # Data transformation workflows
│   ├── train.spec.ts            # Model training workflows
│   ├── predict.spec.ts          # Prediction workflows
│   ├── error-scenarios.spec.ts  # Error handling
│   ├── dataset-metadata.spec.ts # Dataset metadata management
│   ├── transformation-config.spec.ts  # Transformation configuration
│   ├── model-config.spec.ts     # Model configuration
│   ├── data-versioning.spec.ts  # Data versioning UI
│   ├── complete-ai-workflow.spec.ts   # Full AI-guided workflows
│   ├── ai-recommendations.spec.ts     # AI validation
│   ├── performance.spec.ts      # Performance benchmarks
│   └── production-readiness.spec.ts   # Production quality gates
├── test-data/
│   ├── sample.csv               # Basic test dataset
│   ├── diverse-types.csv        # Schema inference testing
│   ├── missing-values.csv       # Imputation testing
│   ├── large-dataset.csv        # Performance testing
│   ├── generate-test-data.ts    # Test data generator
│   └── ai-test-datasets/
│       ├── binary-classification.csv
│       ├── multiclass-classification.csv
│       ├── regression.csv
│       ├── timeseries.csv
│       └── clustering.csv
├── playwright.config.ts         # Playwright configuration
├── performance-results-schema.json  # Performance metrics schema
└── README.md                    # Quick start guide
```

## Getting Started

### Prerequisites

1. **Install Dependencies**:
   ```bash
   cd apps/frontend
   npm install
   ```

2. **Install Playwright Browsers**:
   ```bash
   npx playwright install
   ```

3. **Environment Variables**:
   Create `.env.local` or set environment variables:
   ```bash
   # Optional: Skip authentication for faster local testing
   SKIP_AUTH=true

   # Optional: Use AI mocking for deterministic tests
   USE_AI_MOCK=true

   # Test user credentials (if auth not skipped)
   TEST_USER_EMAIL=test@narrativeml.com
   TEST_USER_PASSWORD=test-password

   # API base URL
   BASE_URL=http://localhost:3000
   ```

### Running Tests

#### Run All Tests
```bash
npm run test:e2e
```

#### Run Specific Test File
```bash
npx playwright test dataset-metadata.spec.ts
```

#### Run Tests by Tag
```bash
# Run smoke tests only (critical paths)
npx playwright test --grep @smoke

# Run AI integration tests
npx playwright test --grep @ai-integration

# Run concurrency tests
npx playwright test --grep @concurrency
```

#### Run Tests in UI Mode (Interactive)
```bash
npx playwright test --ui
```

#### Run Tests in Debug Mode
```bash
npx playwright test --debug
```

#### Run Tests in Specific Browser
```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

### Viewing Test Reports

After test execution:
```bash
npx playwright show-report
```

## Test Patterns and Best Practices

### 1. Page Object Model (POM)

**Always use page objects** for UI interactions to maintain code reusability and readability.

**Good Example**:
```typescript
import { test, expect } from '../fixtures';
import { DatasetPage } from '../pages/DatasetPage';

test('should upload dataset', async ({ authenticatedPage, uploadTestDataset }) => {
  const datasetPage = new DatasetPage(authenticatedPage);
  const datasetId = await uploadTestDataset();

  await datasetPage.gotoDatasetDetail(datasetId);
  await expect(datasetPage.datasetTitle).toBeVisible();
});
```

**Bad Example** (avoid):
```typescript
test('should upload dataset', async ({ page }) => {
  await page.click('button:has-text("Upload")'); // Direct page interaction
  // Hard to maintain, not reusable
});
```

### 2. Multi-Fallback Selector Strategy

Use multiple selector strategies for resilience to UI changes:

```typescript
// Priority: data-testid > class > text > generic
await page.click('[data-testid="upload-button"], .upload-btn, button:has-text("Upload")');
```

### 3. Fixtures for Setup/Cleanup

**Always use fixtures** for test data setup and cleanup:

```typescript
test('should process dataset', async ({ uploadTestDataset, cleanupDataset }) => {
  const datasetId = await uploadTestDataset(); // Setup

  // ... test logic ...

  await cleanupDataset(datasetId); // Cleanup (automatic via afterEach)
});
```

### 4. Playwright Auto-Waiting

**Prefer Playwright's auto-waiting** over fixed timeouts:

**Good**:
```typescript
await page.waitForSelector('text=/Upload complete/', { timeout: 30000 });
await page.click('button:has-text("Continue")'); // Auto-waits
```

**Bad** (avoid):
```typescript
await page.waitForTimeout(2000); // Flaky, unreliable
await page.click('button:has-text("Continue")');
```

### 5. Test Isolation

**Each test should be independent** and not rely on previous test state:

```typescript
test.beforeEach(async ({ uploadTestDataset }) => {
  datasetId = await uploadTestDataset(); // Fresh data for each test
});

test.afterEach(async ({ cleanupDataset }) => {
  if (datasetId) {
    await cleanupDataset(datasetId); // Clean up after each test
  }
});
```

### 6. AI Mocking Strategy

For tests involving AI calls, use the hybrid mocking approach:

```typescript
import { test } from '../fixtures';

test('should get AI recommendations @ai-integration', async ({
  authenticatedPage,
  aiMock
}) => {
  test.setTimeout(120000); // Extended timeout for AI calls

  // Mock AI responses in CI, use real AI locally
  await aiMock.mockAIRecommendations(authenticatedPage, 'binary_classification');

  // ... test logic ...
});
```

**Control via Environment Variables**:
- `USE_AI_MOCK=true` - Use mocked AI responses (fast, deterministic)
- `USE_AI_MOCK=false` or unset - Use real AI (accurate, slower)

### 7. Performance Testing

Use the `PerformanceMonitor` helper for tracking performance:

```typescript
import { PerformanceMonitor } from '../helpers';

test('should load page quickly', async ({ authenticatedPage }) => {
  const monitor = new PerformanceMonitor(authenticatedPage);

  const tti = await monitor.measurePageLoad('/dashboard');
  expect(tti).toBeLessThan(2000); // <2s

  await monitor.persistMetrics(); // Save to performance-results.json
});
```

### 8. Error Handling

Monitor console errors during tests:

```typescript
import { ConsoleErrorCollector } from '../helpers';

test('should have no console errors', async ({ authenticatedPage }) => {
  const errorCollector = new ConsoleErrorCollector(authenticatedPage);

  // ... perform actions ...

  const errors = errorCollector.getErrors();
  expect(errors).toHaveLength(0);
});
```

### 9. Security Testing

Use `SecurityTester` for security validations:

```typescript
import { SecurityTester } from '../helpers';

test('should prevent XSS', async ({ authenticatedPage }) => {
  const securityTester = new SecurityTester(authenticatedPage);

  const xssPayload = '<script>alert("xss")</script>';
  const prevented = await securityTester.testXSSPrevention(xssPayload, 'input[name="title"]');

  expect(prevented).toBe(true);
});
```

## Test Data Management

### Generating Test Data

Run the test data generator to create AI validation datasets:

```bash
cd apps/frontend/e2e/test-data
npx tsx generate-test-data.ts
```

This creates:
- 5 AI test datasets (binary classification, multiclass, regression, time series, clustering)
- 3 standard test datasets (diverse types, missing values, large dataset)

### Using Test Data in Tests

```typescript
import { readFileSync } from 'fs';
import { join } from 'path';

test('should handle specific dataset', async ({ authenticatedPage }) => {
  const csvPath = join(__dirname, '../test-data/ai-test-datasets/binary-classification.csv');
  const csvBuffer = readFileSync(csvPath);

  const fileInput = authenticatedPage.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: 'binary-classification.csv',
    mimeType: 'text/csv',
    buffer: csvBuffer
  });

  // ... continue test ...
});
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd apps/frontend
          npm ci

      - name: Install Playwright browsers
        run: |
          cd apps/frontend
          npx playwright install --with-deps

      - name: Run smoke tests
        run: |
          cd apps/frontend
          USE_AI_MOCK=true npm run test:e2e -- --grep @smoke
        env:
          SKIP_AUTH: true

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: apps/frontend/playwright-report/
```

### Test Execution Strategy

**Smoke Tests (CI - Every PR)**:
- Run: `@smoke` tagged tests only (~13 tests)
- Duration: ~5-7 minutes
- Purpose: Validate critical user paths

**Full Suite (Nightly)**:
- Run: All tests (268+ tests)
- Duration: ~30-45 minutes
- Purpose: Comprehensive validation

**AI Integration Tests (Weekly)**:
- Run: `@ai-integration` tagged tests with real AI
- Duration: ~15-20 minutes
- Purpose: Validate AI recommendation accuracy

## Troubleshooting

### Common Issues

#### 1. "Timeout waiting for selector"

**Cause**: Element not found or page not loaded

**Solution**:
- Increase timeout: `{ timeout: 60000 }`
- Use more specific selectors
- Check if page navigation completed: `await page.waitForLoadState('networkidle')`

#### 2. "Test failed with 'Element is not visible'"

**Cause**: Element not visible on page

**Solution**:
- Wait for element: `await element.waitFor({ state: 'visible' })`
- Check scroll position: `await element.scrollIntoViewIfNeeded()`
- Verify element not hidden by CSS

#### 3. "Authentication failed"

**Cause**: Authentication flow not working

**Solution**:
- Set `SKIP_AUTH=true` for local development
- Verify test user credentials in environment variables
- Check if auth UI changed (update selectors)

#### 4. "AI timeout after 120s"

**Cause**: Real AI call took too long

**Solution**:
- Use mocked AI: `USE_AI_MOCK=true`
- Increase timeout: `test.setTimeout(180000)`
- Check AI service availability

#### 5. "Database connection failed"

**Cause**: MongoDB not running

**Solution**:
- Start MongoDB: `mongod --dbpath /path/to/data`
- Check connection string in backend `.env`
- Verify backend server is running

## Performance Benchmarks

### Target Performance Metrics

| Metric | Target | Test |
|--------|--------|------|
| Dashboard load | <2s | `performance.spec.ts` |
| Dataset list (50 items) | <3s | `performance.spec.ts` |
| Dataset detail (10k rows) | <4s | `performance.spec.ts` |
| Single prediction | <100ms | `performance.spec.ts` |
| Dataset upload (5MB) | <5s | `performance.spec.ts` |
| Transformation preview | <3s | `performance.spec.ts` |
| Model training (500 rows) | <30s | `performance.spec.ts` |
| AI recommendation | <60s | `ai-recommendations.spec.ts` |

### Performance Results

Results are saved to: `apps/frontend/e2e/performance-results.json`

View results:
```bash
cat apps/frontend/e2e/performance-results.json | jq '.summary'
```

## Test Tags

| Tag | Purpose | Example |
|-----|---------|---------|
| `@smoke` | Critical path tests (run in CI) | Dashboard load, upload workflow |
| `@ai-integration` | Tests requiring AI calls | AI recommendations, problem detection |
| `@concurrency` | Concurrent load tests | Multi-user uploads, parallel predictions |
| (none) | Standard E2E tests | All other functional tests |

## Writing New Tests

### Template for New Test Spec

```typescript
import { test, expect } from '../fixtures';
import { DatasetPage } from '../pages/DatasetPage';

test.describe('Feature Name', () => {
  let datasetId: string;

  test.beforeEach(async ({ uploadTestDataset }) => {
    datasetId = await uploadTestDataset();
  });

  test.afterEach(async ({ cleanupDataset }) => {
    if (datasetId) {
      await cleanupDataset(datasetId);
      datasetId = '';
    }
  });

  test('should perform action @smoke', async ({ authenticatedPage }) => {
    const datasetPage = new DatasetPage(authenticatedPage);

    await datasetPage.gotoDatasetDetail(datasetId);

    // ... test logic ...

    expect(await datasetPage.isVisible()).toBe(true);
  });
});
```

### Checklist for New Tests

- [ ] Use page objects for UI interactions
- [ ] Use fixtures for setup/cleanup
- [ ] Tag smoke tests with `@smoke`
- [ ] Tag AI tests with `@ai-integration`
- [ ] Set appropriate timeouts (120s for AI calls)
- [ ] Use Playwright auto-waiting (avoid fixed timeouts)
- [ ] Add proper cleanup in `afterEach`
- [ ] Use descriptive test names: `should [action] when [condition]`
- [ ] Add assertions for expected behavior
- [ ] Handle error scenarios gracefully

## Additional Resources

- [Playwright Documentation](https://playwright.dev)
- [Page Object Model Pattern](https://playwright.dev/docs/pom)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [CI/CD Integration](https://playwright.dev/docs/ci)
- [Test Sharding](https://playwright.dev/docs/test-sharding)

## Support

For questions or issues:
1. Check this guide
2. Review test examples in `apps/frontend/e2e/workflows/`
3. Check Playwright documentation
4. Ask team for help

---

**Last Updated**: 2025-12-02
**Maintained By**: Development Team
**Version**: 1.0
