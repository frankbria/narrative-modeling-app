import { test, expect } from '../fixtures';

/**
 * Playwright Setup Validation Tests
 * These tests verify that the E2E testing infrastructure is properly configured
 */

test.describe('E2E Testing Setup', () => {
  test('should load the home page @smoke', async ({ page }) => {
    await page.goto('/');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify page loaded successfully
    expect(page.url()).toContain('localhost:3000');
  });

  test('should navigate to authentication page', async ({ page }) => {
    await page.goto('/auth/signin');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify we're on the signin page
    expect(page.url()).toContain('/auth/signin');
  });

  test('should have working authenticated page fixture @smoke', async ({ authenticatedPage }) => {
    // The authenticatedPage fixture should handle login automatically
    expect(authenticatedPage.url()).toMatch(/dashboard/);

    // Verify we're authenticated by checking for common dashboard elements
    const isOnDashboard = authenticatedPage.url().includes('dashboard');
    expect(isOnDashboard).toBeTruthy();
  });

  test('should be able to use test user fixture', async ({ testUser }) => {
    // Verify test user data structure
    expect(testUser).toHaveProperty('email');
    expect(testUser).toHaveProperty('id');
    expect(testUser).toHaveProperty('name');

    // Verify values are not empty
    expect(testUser.email).toBeTruthy();
    expect(testUser.id).toBeTruthy();
    expect(testUser.name).toBeTruthy();
  });

  test('should support multiple browsers', async ({ page, browserName }) => {
    await page.goto('/');

    // Verify browser type is recognized
    expect(['chromium', 'firefox', 'webkit']).toContain(browserName);

    console.log(`Test running on: ${browserName}`);
  });
});

test.describe('Page Objects', () => {
  test('should create UploadPage instance', async ({ authenticatedPage }) => {
    const { UploadPage } = await import('../pages/UploadPage');
    const uploadPage = new UploadPage(authenticatedPage);

    // Navigate to upload page
    await uploadPage.goto('/datasets/upload');

    // Verify we're on the upload page
    expect(authenticatedPage.url()).toContain('/datasets/upload');
  });

  test('should use BasePage methods', async ({ page }) => {
    const { BasePage } = await import('../pages/BasePage');
    const basePage = new BasePage(page);

    // Test navigation
    await basePage.goto('/');

    // Test locator
    const bodyLocator = basePage.locator('body');
    expect(await bodyLocator.isVisible()).toBeTruthy();
  });
});

test.describe('Test Data Fixtures', () => {
  test('should provide test CSV data', async ({ testCSV }) => {
    // Verify CSV buffer exists
    expect(testCSV).toBeDefined();
    expect(testCSV.length).toBeGreaterThan(0);

    // Verify it contains CSV content
    const csvContent = testCSV.toString();
    expect(csvContent).toContain('age,income,purchased');
  });

  test('should read sample CSV file', async ({ page }) => {
    const fs = await import('fs');
    const path = await import('path');

    const csvPath = path.join(__dirname, '../test-data/sample.csv');
    const csvExists = fs.existsSync(csvPath);

    expect(csvExists).toBeTruthy();

    if (csvExists) {
      const content = fs.readFileSync(csvPath, 'utf-8');
      expect(content).toContain('age,income,purchased');
    }
  });
});

test.describe('Configuration', () => {
  test('should have proper viewport size', async ({ page }) => {
    const viewportSize = page.viewportSize();

    // Verify viewport is set
    expect(viewportSize).toBeDefined();
    expect(viewportSize?.width).toBeGreaterThan(0);
    expect(viewportSize?.height).toBeGreaterThan(0);
  });

  test('should support screenshots on failure', async ({ page }) => {
    // This test verifies screenshot capability is available
    await page.goto('/');

    // Take a test screenshot
    const screenshot = await page.screenshot();
    expect(screenshot).toBeDefined();
    expect(screenshot.length).toBeGreaterThan(0);
  });

  test('should support trace collection', async ({ page, context }) => {
    // Verify tracing is available (it's configured to start on retry)
    // This just ensures the API is available
    await page.goto('/');

    // The trace will be collected automatically on test retry/failure
    expect(context).toBeDefined();
  });
});
