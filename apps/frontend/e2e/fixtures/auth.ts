import { test as base, Page } from '@playwright/test';

export type AuthFixtures = {
  authenticatedPage: Page;
  testUser: {
    email: string;
    id: string;
    name: string;
  };
};

/**
 * Extended test with authentication fixtures
 * Provides authenticated page context and test user credentials
 */
export const test = base.extend<AuthFixtures>({
  /**
   * Test user fixture - provides test user credentials
   */
  testUser: async ({}, use) => {
    const user = {
      email: process.env.TEST_USER_EMAIL || 'test@narrativeml.com',
      id: 'test-user-id',
      name: 'Test User',
    };
    await use(user);
  },

  /**
   * Authenticated page fixture - auto-login before tests
   * This fixture handles the authentication flow automatically
   */
  authenticatedPage: async ({ page, testUser }, use) => {
    // Check if we're using SKIP_AUTH mode for development
    const skipAuth = process.env.SKIP_AUTH === 'true';

    if (skipAuth) {
      // In dev mode with SKIP_AUTH, just navigate to dashboard
      await page.goto('/dashboard');
    } else {
      // Navigate to login page
      await page.goto('/auth/signin');

      // Wait for page to load
      await page.waitForLoadState('networkidle');

      // Fill in credentials (adjust selectors based on your actual auth UI)
      const emailInput = page.locator('input[name="email"], input[type="email"]').first();
      const passwordInput = page.locator('input[name="password"], input[type="password"]').first();

      if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
        await emailInput.fill(testUser.email);
        await passwordInput.fill(process.env.TEST_USER_PASSWORD || 'test-password');

        // Submit form
        const submitButton = page.locator('button[type="submit"]').first();
        await submitButton.click();

        // Wait for redirect to dashboard
        await page.waitForURL('**/dashboard', { timeout: 10000 });
      } else {
        // If already logged in or auth is bypassed, just go to dashboard
        await page.goto('/dashboard');
      }
    }

    // Wait for dashboard to be ready
    await page.waitForLoadState('networkidle');

    await use(page);
  },
});

export { expect } from '@playwright/test';
