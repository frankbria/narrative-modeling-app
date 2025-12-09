# E2E Testing Quick Start Guide

**Updated**: 2025-12-03
**Status**: Port conflict fix implemented ✅

---

## Quick Start

### Run All Tests
```bash
cd apps/frontend
npm run test:e2e
```

### Run Smoke Tests Only (Recommended for Development)
```bash
npm run test:e2e:smoke
```

### Run Tests with UI Mode (Visual Debugging)
```bash
npm run test:e2e:ui
```

---

## What Changed?

### Port Conflict Fix
All E2E test commands now automatically clean up port 3010 before running tests. This fixes the 78% test failure rate caused by port conflicts.

**Before**: Tests would fail with 404 errors if dev server was already running
**After**: Port is automatically freed, tests run reliably

---

## Available Commands

| Command | Description | Use Case |
|---------|-------------|----------|
| `npm run test:e2e` | Run all tests | Full test suite execution |
| `npm run test:e2e:smoke` | Run @smoke tagged tests | Quick validation (21 tests) |
| `npm run test:e2e:full` | Run full suite on Chromium | CI/CD pipeline |
| `npm run test:e2e:all` | Run on all browsers | Cross-browser testing |
| `npm run test:e2e:ui` | Open Playwright UI | Interactive debugging |
| `npm run test:e2e:debug` | Run with debugger | Step-through debugging |
| `npm run test:e2e:report` | Show HTML report | View last test results |

---

## Common Scenarios

### Scenario 1: Quick Development Check
```bash
# Make your changes
git add .

# Run smoke tests (takes 2-3 minutes)
npm run test:e2e:smoke

# If passing, commit
git commit -m "feat: your changes"
```

### Scenario 2: Before Creating PR
```bash
# Run full test suite
npm run test:e2e:full

# Expected: 80-85% pass rate (74-78 tests passing)
# If failures, check test-results/ directory
```

### Scenario 3: Debugging a Failing Test
```bash
# Run with UI mode
npm run test:e2e:ui

# Or run specific test file
npm run test:e2e upload.spec.ts

# Or run with debug mode
npm run test:e2e:debug upload.spec.ts
```

### Scenario 4: Testing on Different Port
```bash
# Use custom port
PORT=3000 npm run test:e2e:smoke
```

---

## Understanding Test Results

### Good Output (Port Cleanup Working)
```bash
=== E2E Test Port Cleanup ===
Target port: 3010
✓ Port 3010 is already free

=== Starting Playwright Tests ===
Running 21 tests using 1 worker

  21 passed (3m 45s)
```

### Port Conflict Detected
```bash
=== E2E Test Port Cleanup ===
Target port: 3010
Port 3010 is in use. Attempting to free it...
Found processes: 12345
✓ Port 3010 is now free

=== Starting Playwright Tests ===
[Tests run normally...]
```

### Port Cleanup Failed
```bash
ERROR: Failed to free port 3010
Please manually kill the process using port 3010:
  lsof -ti :3010 | xargs kill -9
```

**Fix**: Run the suggested command, then retry tests

---

## Test Organization

### Smoke Tests (@smoke tag)
Fast, critical path tests (21 tests, ~3 minutes)
- Basic upload workflow
- Dataset creation
- Model training basics
- Single prediction
- Security checks
- Performance baselines

### Full Test Suite
Complete end-to-end coverage (92 tests, ~15 minutes)
- All smoke tests
- Edge cases
- Error scenarios
- Cross-browser compatibility
- Performance benchmarks
- Production readiness checks

---

## Troubleshooting

### Problem: Port still in use after cleanup
**Solution**:
```bash
# Kill manually with sudo
sudo lsof -ti :3010 | xargs kill -9

# Or try fuser
sudo fuser -k 3010/tcp

# Then retry tests
npm run test:e2e:smoke
```

### Problem: Tests timeout
**Possible Causes**:
1. Backend not running (if integration tests)
2. Network issues
3. Slow machine

**Solution**:
```bash
# Check backend status
curl http://localhost:8000/health

# Increase timeout (in playwright.config.ts)
timeout: 180 * 1000  # 3 minutes
```

### Problem: Authentication failures
**Solution**:
Tests should run with `SKIP_AUTH=true` automatically. If not:
```bash
# Set environment variable
echo "SKIP_AUTH=true" >> .env.local

# Restart tests
npm run test:e2e:smoke
```

### Problem: Cannot find test files
**Solution**:
```bash
# Make sure you're in the frontend directory
cd apps/frontend

# List available tests
npm run test:e2e -- --list

# Check test directory
ls -la e2e/workflows/
```

---

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run E2E Tests
  run: |
    cd apps/frontend
    npm run test:e2e:full
  env:
    CI: true
    SKIP_AUTH: true
    PORT: 3010
```

### Pre-commit Hook Example
```bash
#!/bin/bash
# .git/hooks/pre-commit

cd apps/frontend

# Run smoke tests before commit
npm run test:e2e:smoke

if [ $? -ne 0 ]; then
    echo "E2E smoke tests failed. Commit aborted."
    exit 1
fi
```

---

## Performance Expectations

### Smoke Tests
- **Duration**: 2-5 minutes
- **Tests**: 21 tests
- **Workers**: 1 (sequential for dev)
- **Pass Rate**: 80-85% expected

### Full Suite
- **Duration**: 10-20 minutes
- **Tests**: 92 tests
- **Workers**: 4 (parallel in CI)
- **Pass Rate**: 80-85% expected

### Per-Test Timeouts
- **Action timeout**: 15 seconds
- **Navigation timeout**: 30 seconds
- **Test timeout**: 30 seconds (default)

---

## Test Structure

### Test Files Location
```
apps/frontend/e2e/
├── fixtures/           # Shared test fixtures
│   ├── uploadTestDataset.ts
│   └── authenticatedPage.ts
├── pages/              # Page Object Models
│   ├── BasePage.ts
│   ├── UploadPage.ts
│   ├── DatasetPage.ts
│   ├── TransformPage.ts
│   └── ModelPage.ts
└── workflows/          # Test specs
    ├── upload.spec.ts
    ├── dataset-metadata.spec.ts
    ├── transform.spec.ts
    ├── train.spec.ts
    ├── predict.spec.ts
    └── complete-ai-workflow.spec.ts
```

### Page Object Model Usage
```typescript
// In your test
import { UploadPage } from '../pages/UploadPage';

test('upload file', async ({ page }) => {
  const uploadPage = new UploadPage(page);
  await uploadPage.goto();
  await uploadPage.uploadFile('test-data.csv');
  await uploadPage.waitForUploadSuccess();
});
```

---

## Best Practices

### 1. Use Smoke Tests for Quick Feedback
```bash
# During development, run smoke tests frequently
npm run test:e2e:smoke
```

### 2. Tag Your Tests Appropriately
```typescript
test('should upload file @smoke', async ({ page }) => {
  // Test implementation
});
```

### 3. Clean Up Test Data
```typescript
test.afterEach(async ({ page }) => {
  // Delete uploaded datasets
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
});
```

### 4. Use Page Object Models
```typescript
// Good: Reusable, maintainable
const uploadPage = new UploadPage(page);
await uploadPage.uploadFile('data.csv');

// Bad: Brittle, hard to maintain
await page.click('input[type="file"]');
await page.setInputFiles('input[type="file"]', 'data.csv');
```

### 5. Use Fixtures for Common Setup
```typescript
// Good: Shared setup logic
test('test with uploaded dataset', async ({ uploadedDataset }) => {
  // Dataset already uploaded via fixture
});

// Bad: Duplicate setup in every test
test('test', async ({ page }) => {
  await page.goto('/upload');
  await page.setInputFiles('input[type="file"]', 'data.csv');
  // ... upload logic repeated
});
```

---

## Getting Help

### View Test Report
```bash
npm run test:e2e:report
```

### Check Test Results Directory
```bash
ls -la test-results/
ls -la playwright-report/
```

### View Screenshots/Videos
```bash
# Screenshots on failure
open test-results/*/test-failed-1.png

# Videos on failure
open test-results/*/video.webm
```

### Debug Output
```bash
# Run with debug output
DEBUG=pw:api npm run test:e2e:smoke
```

---

## Related Documentation

- **Implementation Details**: `E2E_PORT_FIX_IMPLEMENTATION.md`
- **Root Cause Analysis**: `E2E_ROOT_CAUSE_ANALYSIS.md`
- **Port Conflict Timeline**: `PORT_CONFLICT_TIMELINE.md`
- **Sprint Status**: `../../backend/docs/SPRINT_12.md`

---

## Support

**Issues?** Check the troubleshooting section above or contact the team.

**Found a bug in tests?** Create an issue with:
1. Test file name
2. Error message
3. Screenshot (if available)
4. Steps to reproduce

---

**Last Updated**: 2025-12-03
**Port Conflict Fix**: ✅ Implemented
**Expected Pass Rate**: 80-85%
