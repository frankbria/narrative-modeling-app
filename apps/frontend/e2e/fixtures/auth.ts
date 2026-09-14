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
   * @deprecated Not used — specs import the fixtures from `../fixtures` (index.ts),
   * and only this module's `AuthFixtures` TYPE is re-exported there. This bare
   * `goto('/dashboard')` has no skip-onboarding handling and would land a first-time
   * user on /onboarding: exactly the #578 flake. Use the hardened `authenticatedPage`
   * in `e2e/fixtures/index.ts`; do not revive this one.
   */
  authenticatedPage: async ({ page }, use) => {
    await page.goto('/dashboard?skipOnboarding=true');
    await page.waitForLoadState('networkidle');

    await use(page);
  },
});

export { expect } from '@playwright/test';
