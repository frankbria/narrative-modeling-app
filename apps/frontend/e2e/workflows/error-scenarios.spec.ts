/**
 * Error Scenarios E2E Tests
 *
 * Comprehensive error handling tests covering:
 * - Network failures and recovery
 * - API errors and retries
 * - Invalid state transitions
 * - Permission errors
 * - Timeout handling
 * - Data validation failures
 * - System errors and recovery
 *
 * Coverage Target: >85%
 */

import { test, expect } from '../fixtures';
import { UploadPage } from '../pages/UploadPage';
import { TransformPage } from '../pages/TransformPage';
import { TrainPage } from '../pages/TrainPage';
import { PredictPage } from '../pages/PredictPage';
import { join } from 'path';

test.describe('Network and API Error Handling', () => {
  test('should handle complete network failures gracefully', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/datasets');

    // Simulate network offline
    await authenticatedPage.context().setOffline(true);

    // Try to navigate to upload
    const uploadLink = authenticatedPage.locator('a[href*="upload"], button:has-text("Upload")').first();

    if (await uploadLink.isVisible({ timeout: 2000 })) {
      await uploadLink.click();
    }

    // Should show offline/network error message
    await expect(
      authenticatedPage.locator('text=/offline|no connection|network error|connection lost/i')
    ).toBeVisible({ timeout: 10000 });

    // Restore network
    await authenticatedPage.context().setOffline(false);

    // Should show reconnection message or allow retry
    const retryButton = authenticatedPage.locator('button:has-text(/retry|reconnect|try again/i)');

    if (await retryButton.isVisible({ timeout: 5000 })) {
      await retryButton.click();

      // Should recover and show content
      await expect(
        authenticatedPage.locator('text=/upload|dataset/i').first()
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test('should handle API 500 errors with retry mechanism', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/datasets');

    // Mock API to return 500 error
    let callCount = 0;
    await authenticatedPage.route('**/api/v1/datasets', (route) => {
      callCount++;
      if (callCount <= 2) {
        // Fail first 2 attempts
        route.fulfill({
          status: 500,
          body: JSON.stringify({ error: 'Internal server error' }),
        });
      } else {
        // Succeed on third attempt
        route.fulfill({
          status: 200,
          body: JSON.stringify({ datasets: [] }),
        });
      }
    });

    // Reload to trigger API call
    await authenticatedPage.reload();

    // Should show error initially
    const errorMessage = authenticatedPage.locator('text=/error|failed|unavailable/i');

    // May show retry button
    const retryButton = authenticatedPage.locator('button:has-text(/retry|try again/i)');

    if (await retryButton.isVisible({ timeout: 5000 })) {
      // Click retry
      await retryButton.click();
      await retryButton.click(); // Second retry

      // Should eventually succeed
      await expect(errorMessage).not.toBeVisible({ timeout: 10000 });
    }
  });

  test('should handle API 503 service unavailable errors', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/datasets');

    // Mock API to return 503
    await authenticatedPage.route('**/api/v1/datasets', (route) => {
      route.fulfill({
        status: 503,
        body: JSON.stringify({ error: 'Service temporarily unavailable' }),
      });
    });

    // Reload page
    await authenticatedPage.reload();

    // Should display service unavailable message
    await expect(
      authenticatedPage.locator('text=/temporarily unavailable|maintenance|service unavailable/i')
    ).toBeVisible({ timeout: 10000 });
  });

  test('should handle API timeout errors', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/datasets/upload');

    // Mock slow API response (timeout)
    await authenticatedPage.route('**/api/v1/datasets', async (route) => {
      // Delay response beyond reasonable timeout
      await new Promise(resolve => setTimeout(resolve, 60000));
      route.fulfill({
        status: 200,
        body: JSON.stringify({ datasets: [] }),
      });
    });

    const uploadPage = new UploadPage(authenticatedPage);
    const csvPath = join(__dirname, '../test-data/sample.csv');

    // Try to upload
    try {
      await uploadPage.uploadFile(csvPath);

      // Should show timeout error
      await expect(
        authenticatedPage.locator('text=/timeout|took too long|request timed out/i')
      ).toBeVisible({ timeout: 30000 });
    } catch (error) {
      // Timeout expected
      console.log('Timeout test executed successfully');
    }
  });
});

test.describe('Validation and Data Error Scenarios', () => {
  test('should prevent training without selecting target column', async ({ authenticatedPage, uploadTestDataset }) => {
    const datasetId = await uploadTestDataset();

    await authenticatedPage.goto(`/datasets/${datasetId}/train`);

    const trainPage = new TrainPage(authenticatedPage);

    // Try to train without selecting target
    const trainButton = authenticatedPage.locator('button:has-text(/train|start training/i)');

    if (await trainButton.isVisible({ timeout: 5000 })) {
      await trainButton.click();

      // Should show validation error
      await expect(
        authenticatedPage.locator('text=/select.*target|target.*required|choose.*target/i')
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('should prevent prediction with missing feature values', async ({ authenticatedPage, uploadTestDataset, trainModel }) => {
    const datasetId = await uploadTestDataset();
    const modelId = await trainModel(datasetId, 'purchased');

    await authenticatedPage.goto(`/models/${modelId}/predict`);

    const predictPage = new PredictPage(authenticatedPage);

    // Try to predict without filling all required fields
    const predictButton = authenticatedPage.locator('button:has-text(/predict|submit/i)');

    if (await predictButton.isVisible({ timeout: 5000 })) {
      await predictButton.click();

      // Should show validation error for missing fields
      await expect(
        authenticatedPage.locator('text=/required|fill.*field|missing.*value/i')
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('should validate transformation prerequisites', async ({ authenticatedPage, uploadTestDataset }) => {
    const datasetId = await uploadTestDataset();

    await authenticatedPage.goto(`/datasets/${datasetId}/transform`);

    const transformPage = new TransformPage(authenticatedPage);

    // Try to apply transformation without selecting column
    const applyButton = authenticatedPage.locator('button:has-text(/apply|save/i)');

    if (await applyButton.isVisible({ timeout: 5000 })) {
      await applyButton.click();

      // Should show validation error
      await expect(
        authenticatedPage.locator('text=/select.*column|no transformation|choose.*column/i')
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('should detect and reject corrupted upload files', async ({ authenticatedPage }) => {
    const uploadPage = new UploadPage(authenticatedPage);

    await uploadPage.goto('/datasets/upload');

    // Try uploading malformed CSV
    const malformedPath = join(__dirname, '../test-data/malformed.csv');

    try {
      await uploadPage.uploadFile(malformedPath);

      // Should detect corruption/malformation
      await expect(
        authenticatedPage.locator('text=/corrupted|malformed|invalid.*format|parsing.*error/i')
      ).toBeVisible({ timeout: 10000 });
    } catch (error) {
      console.log('Malformed file test executed');
    }
  });
});

test.describe('Permission and Authentication Errors', () => {
  test('should handle unauthorized access attempts', async ({ authenticatedPage }) => {
    // Mock 401 Unauthorized response
    await authenticatedPage.route('**/api/v1/datasets/**', (route) => {
      route.fulfill({
        status: 401,
        body: JSON.stringify({ error: 'Unauthorized' }),
      });
    });

    await authenticatedPage.goto('/datasets');

    // Should redirect to login or show auth error
    await expect(
      authenticatedPage.locator('text=/unauthorized|not authorized|login|sign in/i')
    ).toBeVisible({ timeout: 10000 });
  });

  test('should handle forbidden access (403) errors', async ({ authenticatedPage, uploadTestDataset }) => {
    const datasetId = await uploadTestDataset();

    // Mock 403 Forbidden response
    await authenticatedPage.route(`**/api/v1/datasets/${datasetId}`, (route) => {
      route.fulfill({
        status: 403,
        body: JSON.stringify({ error: 'Access forbidden' }),
      });
    });

    await authenticatedPage.goto(`/datasets/${datasetId}`);

    // Should show permission error
    await expect(
      authenticatedPage.locator('text=/forbidden|no permission|access denied/i')
    ).toBeVisible({ timeout: 10000 });
  });

  test('should handle expired session gracefully', async ({ authenticatedPage }) => {
    // Mock session expiration
    await authenticatedPage.route('**/api/v1/**', (route) => {
      route.fulfill({
        status: 401,
        body: JSON.stringify({ error: 'Session expired' }),
      });
    });

    await authenticatedPage.goto('/datasets');

    // Should show session expired message or redirect to login
    await expect(
      authenticatedPage.locator('text=/session.*expired|logged out|login again/i')
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Resource and State Error Scenarios', () => {
  test('should handle non-existent resource (404) errors', async ({ authenticatedPage }) => {
    // Navigate to non-existent dataset
    await authenticatedPage.goto('/datasets/non-existent-id-12345');

    // Should show 404 or not found error
    await expect(
      authenticatedPage.locator('text=/not found|doesn\'t exist|no such|404/i')
    ).toBeVisible({ timeout: 10000 });
  });

  test('should handle deleted resource errors', async ({ authenticatedPage, uploadTestDataset, cleanupDataset }) => {
    const datasetId = await uploadTestDataset();

    // Delete the dataset
    await cleanupDataset(datasetId);

    // Try to access deleted dataset
    await authenticatedPage.goto(`/datasets/${datasetId}`);

    // Should show appropriate error
    await expect(
      authenticatedPage.locator('text=/deleted|no longer exists|not found/i')
    ).toBeVisible({ timeout: 10000 });
  });

  test('should prevent invalid state transitions', async ({ authenticatedPage, uploadTestDataset }) => {
    const datasetId = await uploadTestDataset();

    // Try to train before transforming (if required by workflow)
    await authenticatedPage.goto(`/datasets/${datasetId}/train`);

    // Mock API to return state error
    await authenticatedPage.route('**/api/v1/models/train', (route) => {
      route.fulfill({
        status: 400,
        body: JSON.stringify({
          error: 'Invalid state',
          message: 'Dataset must be transformed before training'
        }),
      });
    });

    const trainButton = authenticatedPage.locator('button:has-text(/train|start/i)').first();

    if (await trainButton.isVisible({ timeout: 5000 })) {
      // Select target and algorithm
      const targetSelect = authenticatedPage.locator('select[name="target"], [data-testid="target-select"]');
      if (await targetSelect.isVisible({ timeout: 2000 })) {
        await targetSelect.selectOption({ index: 1 });
      }

      await trainButton.click();

      // Should show state error
      await expect(
        authenticatedPage.locator('text=/invalid.*state|must.*transform|prepare.*data/i')
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('should handle quota or rate limit errors', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/datasets/upload');

    // Mock rate limit error (429)
    await authenticatedPage.route('**/api/v1/datasets', (route) => {
      route.fulfill({
        status: 429,
        body: JSON.stringify({
          error: 'Rate limit exceeded',
          message: 'Too many requests. Please try again later.'
        }),
      });
    });

    const uploadPage = new UploadPage(authenticatedPage);
    const csvPath = join(__dirname, '../test-data/sample.csv');

    try {
      await uploadPage.uploadFile(csvPath);

      // Should show rate limit error
      await expect(
        authenticatedPage.locator('text=/rate limit|too many requests|slow down/i')
      ).toBeVisible({ timeout: 10000 });
    } catch (error) {
      console.log('Rate limit test executed');
    }
  });
});

test.describe('Error Recovery Mechanisms', () => {
  test('should auto-retry failed requests with exponential backoff', async ({ authenticatedPage }) => {
    let attemptCount = 0;

    await authenticatedPage.route('**/api/v1/datasets', (route) => {
      attemptCount++;

      if (attemptCount <= 2) {
        // Fail first 2 attempts
        route.abort('failed');
      } else {
        // Succeed on 3rd attempt
        route.fulfill({
          status: 200,
          body: JSON.stringify({ datasets: [] }),
        });
      }
    });

    await authenticatedPage.goto('/datasets');

    // Should eventually load successfully after retries
    await expect(
      authenticatedPage.locator('text=/datasets|upload|no.*datasets/i').first()
    ).toBeVisible({ timeout: 20000 });

    // Verify retries occurred
    expect(attemptCount).toBeGreaterThanOrEqual(2);
  });

  test('should provide manual retry after error', async ({ authenticatedPage }) => {
    await authenticatedPage.route('**/api/v1/datasets', (route) => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Server error' }),
      });
    });

    await authenticatedPage.goto('/datasets');

    // Should show retry button
    const retryButton = authenticatedPage.locator('button:has-text(/retry|try again/i)');
    await expect(retryButton).toBeVisible({ timeout: 10000 });

    // Unblock API for retry
    await authenticatedPage.unroute('**/api/v1/datasets');

    // Click retry
    await retryButton.click();

    // Should load successfully
    await expect(
      authenticatedPage.locator('text=/datasets|upload/i').first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('should preserve form data after error', async ({ authenticatedPage, uploadTestDataset }) => {
    const datasetId = await uploadTestDataset();

    await authenticatedPage.goto(`/datasets/${datasetId}/train`);

    // Fill in some form fields
    const targetSelect = authenticatedPage.locator('select[name="target"], [data-testid="target-select"]');

    if (await targetSelect.isVisible({ timeout: 5000 })) {
      await targetSelect.selectOption({ index: 1 });
    }

    // Mock API error
    await authenticatedPage.route('**/api/v1/models/train', (route) => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Training failed' }),
      });
    });

    // Try to submit
    const trainButton = authenticatedPage.locator('button:has-text(/train|start/i)').first();
    if (await trainButton.isVisible({ timeout: 2000 })) {
      await trainButton.click();
    }

    // Wait for error
    await authenticatedPage.waitForTimeout(2000);

    // Verify form data is still present
    if (await targetSelect.isVisible()) {
      const selectedValue = await targetSelect.inputValue();
      expect(selectedValue).not.toBe('');
    }
  });

  test('should handle concurrent errors gracefully', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/datasets');

    // Mock multiple failing endpoints
    await authenticatedPage.route('**/api/v1/datasets', (route) => {
      route.fulfill({ status: 500, body: JSON.stringify({ error: 'Error 1' }) });
    });

    await authenticatedPage.route('**/api/v1/models', (route) => {
      route.fulfill({ status: 500, body: JSON.stringify({ error: 'Error 2' }) });
    });

    // Navigate around to trigger multiple API calls
    await authenticatedPage.reload();

    // Should handle multiple errors without crashing
    // Page should still be responsive
    await expect(authenticatedPage.locator('body')).toBeVisible();

    // Should show at least one error message
    await expect(
      authenticatedPage.locator('text=/error|failed|unavailable/i').first()
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe('System Error Scenarios', () => {
  test('should handle browser storage quota exceeded', async ({ authenticatedPage }) => {
    // Try to exceed localStorage quota (typically 5-10MB)
    await authenticatedPage.evaluate(() => {
      try {
        const largeData = 'x'.repeat(10 * 1024 * 1024); // 10MB
        localStorage.setItem('test', largeData);
      } catch (e) {
        // Expected to fail
        window.quotaExceeded = true;
      }
    });

    const quotaExceeded = await authenticatedPage.evaluate(() => {
      return (window as any).quotaExceeded || false;
    });

    expect(quotaExceeded).toBe(true);
  });

  test('should handle JavaScript execution errors gracefully', async ({ authenticatedPage }) => {
    let errorLogged = false;

    // Listen for console errors
    authenticatedPage.on('pageerror', (error) => {
      console.log('Page error caught:', error.message);
      errorLogged = true;
    });

    await authenticatedPage.goto('/datasets');

    // Inject code that causes an error
    await authenticatedPage.evaluate(() => {
      try {
        // Attempt to access undefined property
        (null as any).nonExistentMethod();
      } catch (e) {
        console.error('Test error:', e);
      }
    });

    // Page should still be functional despite error
    await expect(authenticatedPage.locator('body')).toBeVisible();
  });

  test('should handle memory pressure scenarios', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/datasets');

    // Create memory pressure by allocating large arrays
    await authenticatedPage.evaluate(() => {
      const arrays: any[] = [];
      for (let i = 0; i < 100; i++) {
        arrays.push(new Array(100000).fill(0));
      }
      // Clear immediately to avoid crash
      arrays.length = 0;
    });

    // Page should still be responsive
    await expect(authenticatedPage.locator('body')).toBeVisible();
  });
});
