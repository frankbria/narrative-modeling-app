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
 * Uses storage state from global setup for authentication
 * This is more secure and efficient than SKIP_AUTH bypass
 */
export const test = base.extend<AuthFixtures>({
  /**
   * Test user fixture - provides test user credentials
   */
  testUser: async ({}, use) => {
    const user = {
      email: process.env.TEST_USER_EMAIL || 'test@narrativeml.com',
      id: 'test-user-12345',
      name: 'Test User',
    };
    await use(user);
  },

  /**
   * Authenticated page fixture - uses pre-authenticated session
   * The global-setup.ts script handles authentication and saves the session state
   * This fixture just uses that saved state
   */
  authenticatedPage: async ({ page }, use) => {
    // The session is already loaded from storage state (configured in playwright.config.ts)
    // Just navigate to the dashboard
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await use(page);
  },
});

export { expect } from '@playwright/test';
