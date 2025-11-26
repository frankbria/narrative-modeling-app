# E2E Full Suite GitHub Actions Failure Analysis

**Analysis Date**: 2025-12-09
**Workflow Run ID**: 20051767612
**Branch**: snyk-upgrade-928b90bb2492d00fe44bb0a6dbf77601 (representative failure)

## Executive Summary
The E2E Full Suite workflow is experiencing **systematic infrastructure failures** with an 82% failure rate (88/105 tests failing across all shards). The primary root cause is **file input element not being found during upload operations**, causing cascading timeouts across 207+ file upload attempts. This appears to be a navigation/routing issue where tests cannot reach or properly initialize the upload page.

---

## Test Results Overview

### Chromium Browser (3 shards)
| Shard | Failed | Passed | Total | Pass Rate |
|-------|--------|--------|-------|-----------|
| 1/3   | 31     | 4      | 35    | 11%       |
| 2/3   | 24     | 11     | 35    | 31%       |
| 3/3   | 33     | 2      | 35    | 6%        |
| **Total** | **88** | **17** | **105** | **16%** |

### Additional Browsers
- **Firefox**: 2/3 shards failed, 1/3 cancelled (timeout after 20 minutes)
- **Webkit**: 2/3 shards failed, 1/3 cancelled (timeout after 20 minutes)

---

## Critical Error Patterns

### 1. File Upload Timeout Errors (PRIMARY ISSUE)
**Count**: 207 occurrences across all shards

**Error Message**:
```
Error: locator.setInputFiles: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('input[type="file"]')
```

**Location**: `apps/frontend/e2e/pages/UploadPage.ts:18`

**Root Cause**: The file input element `input[type="file"]` is **never found** on the page, indicating:
- Upload page not rendering correctly
- Navigation to upload route failing silently
- Route misconfiguration in CI environment
- Authentication bypass not working properly for protected routes

**Impact**: Blocks all upload-dependent workflows:
- Direct upload tests (upload.spec.ts)
- Transform tests (require uploaded dataset)
- Training tests (require dataset)
- Prediction tests (require trained model)
- Error scenario tests (require various states)

---

### 2. Element Not Found Errors
**Count**: 18 occurrences

**Error Message**:
```
Error: expect(locator).toBeVisible() failed
Error: element(s) not found
```

**Affected Tests**:
- Network error handling scenarios
- API error recovery mechanisms
- Session expiration handling
- Unauthorized access tests

**Root Cause**: Expected error UI elements not implemented or not visible:
- Console logs show: "Error handling UI not yet implemented"
- "Timeout handling not yet implemented"

**Category**: Application feature gap (not infrastructure)

---

### 3. CSS Selector Parsing Errors
**Count**: 6 occurrences

**Error Message**:
```
Error: locator.isVisible: Unexpected token "/" while parsing css selector "button:has-text(/retry|try again/i)".
Did you mean to CSS.escape it?
```

**Affected Tests**:
- "should handle API 500 errors with retry mechanism"

**Root Cause**: Invalid CSS selector syntax - regex pattern used incorrectly in `has-text()`

**Category**: Test infrastructure bug (easy fix)

---

### 4. General Test Timeouts
**Count**: 441 timeout messages (30000ms exceeded)

**Root Cause**: Cascading effect from file upload failures - tests hang waiting for elements that never appear

---

## Failed Test Categorization

### Category A: Upload Infrastructure Failures (33 tests)
**Root Cause**: Cannot find file input element

Tests from `upload.spec.ts`:
1. should upload valid CSV file successfully @smoke
2. should validate file format and reject non-CSV files
3. should verify metadata storage after upload @smoke
4. should detect and display schema information
5. should handle concurrent uploads
6. should display upload progress indicator @smoke
7. should allow canceling an in-progress upload
8. should preserve uploaded files across page refreshes
9. should display data preview after successful upload
10. should provide option to download uploaded dataset
11. should detect and warn about PII in uploaded data
12. should validate CSV structure and show errors for malformed files
13. should handle empty CSV files gracefully

### Category B: Transform Workflow Failures (17 tests)
**Root Cause**: Cannot upload prerequisite dataset

Tests from `transform.spec.ts`:
1. should display data preview after upload
2. should apply one-hot encoding transformation @smoke
3. should apply label encoding transformation
4. should apply standard scaling transformation @smoke
5. should apply min-max scaling transformation
6. should handle imputation for missing values
7. should validate transformation on non-numeric columns
8. should allow adding multiple transformations
9. should allow removing transformations before applying
10. should display transformation preview before applying
11. should validate required fields before applying transformation
12. should save transformation pipeline
13. should load saved transformation pipeline
14. should clear all transformations
15. should handle feature engineering transformations
16. should show transformation history
17. should allow undoing transformations

### Category C: Training Workflow Failures (27 tests)
**Root Cause**: Cannot upload prerequisite dataset

Tests from `train.spec.ts`:
1. should navigate to training page from dataset
2. should display available algorithms
3. should train model with selected target column @smoke
4. should display training progress updates @smoke
5. should wait for training completion and show success @smoke
6. should display model metrics after training @smoke
7. should validate target column selection is required
8. should handle training failure gracefully
9. should allow canceling training
10. should allow configuring hyperparameters
11. should support different problem types (classification vs regression)
12. should display feature importance after training
13. should allow downloading trained model
14. should save trained model to database
15. should show training history for dataset
16. should support cross-validation configuration
17. should display training time and resource usage
18. should support train-test split configuration
19. should handle imbalanced dataset warning
20. should support ensemble methods
21. should handle insufficient data error
22. should handle algorithm not supported error
23. should handle network timeout during training

### Category D: Prediction Workflow Failures (11 tests)
**Root Cause**: Cannot create prerequisite trained model (blocked by upload)

Tests from `predict.spec.ts`:
1. should navigate to prediction page for trained model
2. should make single prediction with valid feature values @smoke
3. should display confidence score with prediction @smoke
4. should validate feature value types before prediction
5. should handle missing required feature values
6. should display prediction result in appropriate format
7. should navigate to batch prediction mode
8. should upload CSV file for batch predictions
9. should process batch predictions and display results
10. should allow downloading batch prediction results
11. should validate batch file format

### Category E: Error Scenario Failures (18 tests)
**Root Cause**: Mix of upload failures + unimplemented error UI

Tests from `error-scenarios.spec.ts`:
1. should handle complete network failures gracefully (UI not implemented)
2. should handle API 500 errors with retry mechanism (CSS selector bug)
3. should handle API 503 service unavailable errors (UI not implemented)
4. should handle API timeout errors (UI not implemented)
5. should prevent training without selecting target column (upload blocked)
6. should prevent prediction with missing feature values (upload blocked)
7. should validate transformation prerequisites (upload blocked)
8. should detect and reject corrupted upload files (CSS selector bug)
9. should handle unauthorized access attempts (UI not implemented)
10. should handle forbidden access (403) errors (upload blocked)
11. should handle expired session gracefully (UI not implemented)
12. should handle deleted resource errors (upload blocked)
13. should prevent invalid state transitions (upload blocked)
14. should handle quota or rate limit errors (CSS selector bug)
15. should auto-retry failed requests with exponential backoff (UI not implemented)
16. should provide manual retry after error (CSS selector bug)
17. should preserve form data after error (CSS selector bug)
18. should handle concurrent errors gracefully (CSS selector bug)

### Category F: Setup/Infrastructure Tests (2 tests)
**Root Cause**: Page object initialization

Tests from `setup.spec.ts`:
1. should create UploadPage instance
2. should use BasePage methods

---

## CI Environment vs Local Dev Differences

### Confirmed CI Configuration
```bash
SKIP_AUTH: true
NEXTAUTH_URL: http://localhost:3000
```

### Potential CI-Specific Issues

1. **Middleware/Auth Bypass Not Working**
   - `SKIP_AUTH=true` may not be properly configured in middleware
   - Protected routes might be blocking access
   - Session/cookie handling differences in CI

2. **Route Configuration**
   - Upload route may not be registered correctly
   - Next.js App Router path resolution issues
   - Missing or misconfigured page.tsx file

3. **Timing/Race Conditions**
   - Next.js dev server startup timing
   - Page hydration delays
   - Client-side navigation not completing

4. **Build/Bundle Differences**
   - Different build output in CI vs local dev
   - Missing environment variables
   - Static/dynamic rendering mismatches

---

## Specific Error Messages for Upload Navigation

### Primary Error (from upload.spec.ts:21)
```
Test timeout of 30000ms exceeded.

Error: locator.setInputFiles: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('input[type="file"]')

  at pages/UploadPage.ts:18

  16 |   async uploadFile(filePath: string) {
  17 |     const fileInput = this.locator('input[type="file"]');
> 18 |     await fileInput.setInputFiles(filePath);
     |     ^
  19 |   }
```

### Cascading Impact
Once the upload fails, all subsequent tests in the workflow fail because they depend on:
1. Uploaded dataset existence
2. Dataset metadata in database
3. Dataset ID for navigation
4. File availability in S3/storage

---

## Recommendations for Next Investigation Steps

### Immediate Priority (High Impact)

1. **Verify Upload Route Accessibility**
   ```bash
   # Check if upload page loads in CI
   - Add debug screenshot before setInputFiles
   - Log current URL and page HTML
   - Verify route registration in App Router
   ```

2. **Validate Auth Bypass Configuration**
   ```bash
   # Confirm middleware skips auth when SKIP_AUTH=true
   - Review apps/frontend/middleware.ts
   - Check protected route list
   - Verify environment variable loading
   ```

3. **Check File Input Element Rendering**
   ```bash
   # Debug why input[type="file"] not found
   - Screenshot upload page on load
   - Log page.locator('input').count()
   - Check for client-side rendering delays
   ```

4. **Fix CSS Selector Bug**
   ```typescript
   // Replace regex in has-text with proper syntax
   // BROKEN: button:has-text(/retry|try again/i)
   // FIXED: button >> text=/retry|try again/i
   ```

### Secondary Priority (Medium Impact)

5. **Implement Missing Error UI**
   - Add error message display components
   - Implement retry buttons
   - Add timeout handling UI

6. **Review CI Environment Variables**
   ```bash
   # Ensure all required vars are set
   - SKIP_AUTH=true
   - NEXT_PUBLIC_API_URL
   - Database connection strings
   ```

7. **Check Next.js Server Logs**
   - Review server startup in CI
   - Check for route registration errors
   - Verify middleware execution

8. **Download and Analyze Artifacts**
   ```bash
   # Get screenshots/videos from failed tests
   gh run download 20051767612 -n test-results-chromium-full-shard-1-3
   gh run download 20051767612 -n playwright-report-chromium-full-shard-1-3
   ```

### Testing Recommendations

9. **Add Diagnostic Tests**
   ```typescript
   test('DIAGNOSTIC: Upload page loads', async ({ page }) => {
     await page.goto('/upload');
     await page.screenshot({ path: 'upload-page-loaded.png' });
     const inputCount = await page.locator('input').count();
     console.log(`Found ${inputCount} input elements`);
     const html = await page.content();
     console.log('Page HTML:', html.substring(0, 500));
   });
   ```

10. **Test Auth Bypass Independently**
    ```typescript
    test('DIAGNOSTIC: Auth bypass works', async ({ page }) => {
      await page.goto('/upload');
      const url = page.url();
      expect(url).not.toContain('/signin');
      expect(url).toContain('/upload');
    });
    ```

---

## Success Criteria

Before considering this issue resolved:

1. ✅ Upload page loads successfully in CI
2. ✅ File input element is found by selector
3. ✅ At least one full upload workflow passes
4. ✅ Pass rate increases from 16% to > 80%
5. ✅ CSS selector bugs fixed
6. ✅ Error UI implemented or tests marked as pending

---

## Appendix: Console Logs Found

```
Timeout test executed successfully
Malformed file test executed
Rate limit test executed
Error handling UI not yet implemented
Timeout handling not yet implemented
```

These indicate some tests are reaching the backend API successfully, but UI elements for error states are missing.
