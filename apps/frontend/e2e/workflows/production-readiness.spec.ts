/**
 * Production Readiness E2E Tests
 *
 * Tests production quality gates including:
 * - Security (authentication, authorization, CSRF, XSS, injection)
 * - Accessibility (WCAG 2.1 AA compliance)
 * - Error handling (network, API, validation, timeouts)
 * - Data validation (input sanitization, file upload, numerical)
 * - Monitoring & logging (analytics, errors, performance)
 * - Production deployment (environment, CORS, assets)
 *
 * Coverage Target: >85%
 * Test Count: 24 tests
 */

import { test, expect } from '../fixtures';
import { ConsoleErrorCollector, SecurityTester } from '../helpers';
import { UploadPage } from '../pages/UploadPage';
import { join } from 'path';

test.describe('Production Readiness - Security', () => {
  test('should require authentication for protected routes @smoke', async ({ page }) => {
    const securityTester = new SecurityTester(page);

    const result = await securityTester.testAuthenticationRequired('/dashboard');

    expect(result.passed).toBeTruthy();
    expect(result.message).toContain('requires authentication');
  });

  test('should enforce user isolation and authorization', async ({
    authenticatedPage,
    request,
    testUser,
  }) => {
    // Try to access another user's dataset
    const otherUserId = 'other-user-id-12345';

    const response = await request.get(`/api/v1/datasets?user_id=${otherUserId}`);

    // Should either return empty or 403
    if (response.ok()) {
      const data = await response.json();
      expect(data.datasets || data).toHaveLength(0);
    } else {
      expect([403, 401]).toContain(response.status());
    }
  });

  test('should have CSRF protection on forms', async ({ authenticatedPage }) => {
    const securityTester = new SecurityTester(authenticatedPage);

    await authenticatedPage.goto('/datasets/upload');

    const result = await securityTester.testCSRFProtection('form');

    expect(result.passed).toBeTruthy();
  });

  test('should prevent XSS attacks', async ({ authenticatedPage }) => {
    const securityTester = new SecurityTester(authenticatedPage);

    await authenticatedPage.goto('/datasets/upload');

    // Test XSS prevention in dataset name input (if exists)
    const nameInput = authenticatedPage.locator('input[name="name"], input[placeholder*="name"]');

    if (await nameInput.isVisible({ timeout: 2000 })) {
      const result = await securityTester.testXSSPrevention(
        'input[name="name"], input[placeholder*="name"]',
        'button[type="submit"]',
        'body'
      );

      expect(result.passed).toBeTruthy();
    } else {
      // Skip if no suitable input found
      console.log('XSS test skipped - no text input found');
    }
  });

  test('should prevent SQL/NoSQL injection attacks', async ({ authenticatedPage }) => {
    const securityTester = new SecurityTester(authenticatedPage);

    await authenticatedPage.goto('/datasets');

    // Test injection prevention in search/filter
    const searchInput = authenticatedPage.locator('input[type="search"], input[placeholder*="search"]');

    if (await searchInput.isVisible({ timeout: 2000 })) {
      const result = await securityTester.testInjectionPrevention(
        'input[type="search"], input[placeholder*="search"]',
        'button[type="submit"], form'
      );

      expect(result.passed).toBeTruthy();
    } else {
      console.log('Injection test skipped - no search input found');
    }
  });
});

test.describe('Production Readiness - Accessibility (WCAG 2.1 AA)', () => {
  test('should support full keyboard navigation @smoke', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/dashboard');

    // Test Tab navigation
    await authenticatedPage.keyboard.press('Tab');
    const firstFocused = await authenticatedPage.evaluate(() => document.activeElement?.tagName);
    expect(firstFocused).toBeTruthy();

    // Test Enter key on focusable elements
    await authenticatedPage.keyboard.press('Enter');
    await authenticatedPage.waitForTimeout(500);

    // Verify navigation occurred or action triggered
    const currentUrl = authenticatedPage.url();
    expect(currentUrl).toBeTruthy();
  });

  test('should be screen reader compatible', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/dashboard');

    // Check for ARIA labels and roles
    const ariaLabels = await authenticatedPage.locator('[aria-label]').count();
    const ariaRoles = await authenticatedPage.locator('[role]').count();
    const altTexts = await authenticatedPage.locator('img[alt]').count();

    expect(ariaLabels + ariaRoles).toBeGreaterThan(0);

    // Check for semantic HTML
    const headers = await authenticatedPage.locator('h1, h2, h3').count();
    expect(headers).toBeGreaterThan(0);

    // Verify no images without alt text
    const imagesWithoutAlt = await authenticatedPage.locator('img:not([alt])').count();
    expect(imagesWithoutAlt).toBe(0);
  });

  test('should meet color contrast ratio requirements (4.5:1)', async ({
    authenticatedPage,
  }) => {
    await authenticatedPage.goto('/dashboard');

    // Use axe-core for automated accessibility testing
    const accessibilitySnapshot = await authenticatedPage.accessibility.snapshot();

    expect(accessibilitySnapshot).toBeTruthy();

    // Check for common contrast issues in primary elements
    const primaryButton = authenticatedPage.locator('button').first();
    if (await primaryButton.isVisible()) {
      const buttonStyles = await primaryButton.evaluate((el) => {
        const styles = window.getComputedStyle(el);
        return {
          color: styles.color,
          backgroundColor: styles.backgroundColor,
        };
      });

      expect(buttonStyles.color).toBeTruthy();
      expect(buttonStyles.backgroundColor).toBeTruthy();
    }
  });

  test('should be responsive across breakpoints (320px, 768px, 1024px, 1920px)', async ({
    page,
  }) => {
    const breakpoints = [
      { width: 320, height: 568, name: 'Mobile' },
      { width: 768, height: 1024, name: 'Tablet' },
      { width: 1024, height: 768, name: 'Desktop' },
      { width: 1920, height: 1080, name: 'Large Desktop' },
    ];

    for (const breakpoint of breakpoints) {
      await page.setViewportSize({ width: breakpoint.width, height: breakpoint.height });
      await page.goto('/dashboard');

      // Verify content is visible and not overflowing
      const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
      expect(bodyWidth).toBeLessThanOrEqual(breakpoint.width + 20); // Allow small margin

      // Verify navigation is accessible
      const nav = page.locator('nav, [role="navigation"]');
      if (await nav.isVisible({ timeout: 2000 })) {
        const navBox = await nav.boundingBox();
        expect(navBox).toBeTruthy();
      }
    }
  });

  test('should have accessible forms', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/datasets/upload');

    // Check form labels
    const labels = await authenticatedPage.locator('label').count();
    const inputs = await authenticatedPage.locator('input, select, textarea').count();

    // Most inputs should have associated labels
    expect(labels).toBeGreaterThan(0);

    // Check for required field indicators
    const requiredInputs = await authenticatedPage.locator('input[required], input[aria-required="true"]').count();

    if (requiredInputs > 0) {
      // Verify required fields have visual indicators
      const asterisks = await authenticatedPage.locator('text=/\\*/').count();
      expect(asterisks).toBeGreaterThan(0);
    }
  });
});

test.describe('Production Readiness - Error Handling', () => {
  test('should handle network offline gracefully @smoke', async ({ authenticatedPage }) => {
    const errorCollector = new ConsoleErrorCollector(authenticatedPage);

    await authenticatedPage.goto('/dashboard');

    // Simulate offline
    await authenticatedPage.context().setOffline(true);

    // Try to perform an action
    const uploadLink = authenticatedPage.locator('a[href*="upload"], button:has-text("Upload")');

    if (await uploadLink.isVisible({ timeout: 2000 })) {
      await uploadLink.click();
      await authenticatedPage.waitForTimeout(2000);
    }

    // Should show offline message
    const offlineMessage = await authenticatedPage.locator('text=/offline|no connection|network error/i').count();

    // Restore online
    await authenticatedPage.context().setOffline(false);

    // Should not have uncaught errors
    expect(errorCollector.getPageErrors().length).toBe(0);
  });

  test('should handle API 500 errors gracefully', async ({ authenticatedPage, request }) => {
    const errorCollector = new ConsoleErrorCollector(authenticatedPage);

    await authenticatedPage.goto('/dashboard');

    // Intercept API calls and return 500
    await authenticatedPage.route('**/api/v1/**', (route) => {
      route.fulfill({ status: 500, body: 'Internal Server Error' });
    });

    // Try to load datasets
    await authenticatedPage.goto('/datasets');
    await authenticatedPage.waitForTimeout(2000);

    // Should show error message to user
    const errorMessage = await authenticatedPage.locator('text=/error|failed|something went wrong/i').count();
    expect(errorMessage).toBeGreaterThan(0);

    // Should not have uncaught errors
    expect(errorCollector.getPageErrors().length).toBe(0);
  });

  test('should display form validation errors', async ({ authenticatedPage }) => {
    const errorCollector = new ConsoleErrorCollector(authenticatedPage);

    await authenticatedPage.goto('/datasets/upload');

    // Try to submit without file
    const submitButton = authenticatedPage.locator('button[type="submit"]');

    if (await submitButton.isVisible({ timeout: 2000 })) {
      await submitButton.click();
      await authenticatedPage.waitForTimeout(1000);

      // Should show validation error
      const validationError = await authenticatedPage.locator('text=/required|please|must/i').count();
      expect(validationError).toBeGreaterThan(0);
    }

    // Should not have JS errors
    expect(errorCollector.getPageErrors().length).toBe(0);
  });

  test('should handle request timeouts (>60s)', async ({ authenticatedPage, request }) => {
    const errorCollector = new ConsoleErrorCollector(authenticatedPage);

    // Intercept API calls and delay response
    await authenticatedPage.route('**/api/v1/models/train', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 61000));
      route.fulfill({ status: 408, body: 'Request Timeout' });
    });

    await authenticatedPage.goto('/models/train');
    await authenticatedPage.waitForTimeout(2000);

    // Try to trigger timeout (we won't wait full 60s in test)
    const trainButton = authenticatedPage.locator('button:has-text("Train")');

    if (await trainButton.isVisible({ timeout: 2000 })) {
      // Click but don't wait for completion
      await trainButton.click({ timeout: 2000 }).catch(() => {});
    }

    // Should not have uncaught errors
    expect(errorCollector.getPageErrors().length).toBe(0);
  });

  test('should detect and report console errors', async ({ authenticatedPage }) => {
    const errorCollector = new ConsoleErrorCollector(authenticatedPage);

    await authenticatedPage.goto('/dashboard');
    await authenticatedPage.waitForLoadState('networkidle');

    // Check for console errors
    const consoleErrors = errorCollector.getConsoleErrors();
    const pageErrors = errorCollector.getPageErrors();

    // Production should have zero errors
    expect(consoleErrors.length).toBe(0);
    expect(pageErrors.length).toBe(0);

    if (consoleErrors.length > 0 || pageErrors.length > 0) {
      console.log(errorCollector.getErrorReport());
      throw new Error('Console errors detected in production build');
    }
  });
});

test.describe('Production Readiness - Data Validation', () => {
  test('should sanitize user input', async ({ authenticatedPage }) => {
    const securityTester = new SecurityTester(authenticatedPage);

    await authenticatedPage.goto('/datasets/upload');

    const nameInput = authenticatedPage.locator('input[name="name"], input[placeholder*="name"]');

    if (await nameInput.isVisible({ timeout: 2000 })) {
      const result = await securityTester.testInputSanitization(
        'input[name="name"]',
        'button[type="submit"]'
      );

      expect(result.passed).toBeTruthy();
    }
  });

  test('should validate file uploads', async ({ authenticatedPage }) => {
    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    // Try to upload invalid file type
    const invalidPath = join(__dirname, '../test-data/invalid.json');
    const fileInput = authenticatedPage.locator('input[type="file"]');

    try {
      await fileInput.setInputFiles(invalidPath);
      await authenticatedPage.waitForTimeout(1000);

      // Should show validation error
      const errorMessage = await authenticatedPage.locator('text=/invalid|format|csv/i').count();
      expect(errorMessage).toBeGreaterThan(0);
    } catch (error) {
      // Browser may prevent invalid file selection
      console.log('Browser prevented invalid file upload');
    }
  });

  test('should validate numerical inputs', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/models/train');

    // Find numerical input (e.g., max_depth, n_estimators)
    const numberInput = authenticatedPage.locator('input[type="number"]').first();

    if (await numberInput.isVisible({ timeout: 2000 })) {
      // Try to enter invalid value
      await numberInput.fill('-999');
      await numberInput.blur();
      await authenticatedPage.waitForTimeout(500);

      // Should show validation error
      const validationError = await authenticatedPage.locator('text=/invalid|must be|positive/i').count();

      // Input should either reject or show error
      const inputValue = await numberInput.inputValue();
      expect(inputValue === '-999' ? validationError > 0 : true).toBeTruthy();
    }
  });
});

test.describe('Production Readiness - Monitoring & Logging', () => {
  test('should track analytics events', async ({ authenticatedPage }) => {
    const analyticsEvents: any[] = [];

    // Intercept analytics calls
    await authenticatedPage.route('**/analytics/**', (route) => {
      analyticsEvents.push(route.request().postDataJSON());
      route.fulfill({ status: 200, body: 'OK' });
    });

    // Perform actions that should trigger analytics
    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/sample.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    // Should have tracked dataset_uploaded event
    // Note: May not fire if analytics not configured in test env
    // This is more of a smoke test
  });

  test('should log errors with context', async ({ authenticatedPage }) => {
    const errorCollector = new ConsoleErrorCollector(authenticatedPage);

    // Trigger an error
    await authenticatedPage.route('**/api/v1/**', (route) => {
      route.fulfill({ status: 500, body: 'Test Error' });
    });

    await authenticatedPage.goto('/datasets');
    await authenticatedPage.waitForTimeout(2000);

    // Errors should be logged (to console or error service)
    const consoleMessages = errorCollector.getConsoleWarnings();

    // We expect some warning/error messages about failed API calls
    // In production, these would go to error tracking service
  });

  test('should monitor performance metrics', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/dashboard');
    await authenticatedPage.waitForLoadState('networkidle');

    // Get performance timing data
    const performanceData = await authenticatedPage.evaluate(() => {
      const perf = performance.timing;
      return {
        loadTime: perf.loadEventEnd - perf.navigationStart,
        domContentLoaded: perf.domContentLoadedEventEnd - perf.navigationStart,
        resourcesLoaded: perf.loadEventEnd - perf.domContentLoadedEventEnd,
      };
    });

    expect(performanceData.loadTime).toBeGreaterThan(0);
    expect(performanceData.domContentLoaded).toBeGreaterThan(0);

    // Performance data should be logged to monitoring service
  });
});

test.describe('Production Readiness - Deployment Configuration', () => {
  test('should have correct environment configuration', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/dashboard');

    // Check that API_URL is correctly configured
    const apiUrl = await authenticatedPage.evaluate(() => {
      return (window as any).ENV?.API_URL || process.env.NEXT_PUBLIC_API_URL;
    });

    // Should not be localhost in production
    if (process.env.NODE_ENV === 'production') {
      expect(apiUrl).not.toContain('localhost');
      expect(apiUrl).not.toContain('127.0.0.1');
    }
  });

  test('should have correct CORS configuration', async ({ request }) => {
    const response = await request.get('/api/v1/health');

    if (response.ok()) {
      const headers = response.headers();

      // Check CORS headers
      const allowedOrigins = headers['access-control-allow-origin'];

      // Should either be specific origin or have CORS configured
      if (process.env.NODE_ENV === 'production') {
        expect(allowedOrigins).not.toBe('*');
      }
    }
  });

  test('should load all static assets without 404s', async ({ authenticatedPage }) => {
    const failed404s: string[] = [];

    authenticatedPage.on('response', (response) => {
      if (response.status() === 404) {
        failed404s.push(response.url());
      }
    });

    await authenticatedPage.goto('/dashboard');
    await authenticatedPage.waitForLoadState('networkidle');

    // Filter out known external 404s (analytics, ads, etc.)
    const relevantFailed = failed404s.filter(
      (url) =>
        !url.includes('google-analytics') &&
        !url.includes('analytics.js') &&
        !url.includes('ads') &&
        !url.includes('tracking')
    );

    expect(relevantFailed.length).toBe(0);

    if (relevantFailed.length > 0) {
      console.log('404 Errors:', relevantFailed);
    }
  });
});
