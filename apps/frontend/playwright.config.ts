import { defineConfig, devices } from '@playwright/test';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// require('dotenv').config();

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './e2e',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Use 4 workers on CI for better performance (GitHub Actions has 2 cores, 4 workers is optimal) */
  workers: process.env.CI ? 4 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',

  /* Global setup - authenticate once before all tests */
  globalSetup: require.resolve('./e2e/global-setup'),

  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: process.env.BASE_URL || `http://localhost:${process.env.PORT || '3010'}`,

    /* Use the authenticated session state from global setup */
    storageState: './e2e/.auth/user.json',

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Screenshot on failure */
    screenshot: 'only-on-failure',

    /* Video on failure */
    video: 'retain-on-failure',

    /* Default timeout for each action (click, fill, etc.) */
    actionTimeout: 15000,

    /* Navigation timeout */
    navigationTimeout: 30000,
  },

  /* Configure projects for major browsers */
  projects: [
    // Smoke tests: Quick validation on Chromium only
    {
      name: 'chromium-smoke',
      use: { ...devices['Desktop Chrome'] },
      grep: /@smoke/,
      testMatch: /.*\.spec\.ts/,
    },

    // Full suite: All tests on Chromium (default for CI)
    {
      name: 'chromium-full',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /.*\.spec\.ts/,
    },

    // Full suite: Firefox (optional, run on demand)
    {
      name: 'firefox-full',
      use: { ...devices['Desktop Firefox'] },
      testMatch: /.*\.spec\.ts/,
    },

    // Full suite: WebKit (optional, run on demand)
    {
      name: 'webkit-full',
      use: { ...devices['Desktop Safari'] },
      testMatch: /.*\.spec\.ts/,
    },

    /* Test against mobile viewports. */
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    // },
  ],

  /* Run your local dev server before starting the tests */
  webServer: {
    command: `PORT=${process.env.PORT || '3010'} npm run dev`,
    url: `http://localhost:${process.env.PORT || '3010'}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
    env: {
      NODE_ENV: 'development',
      PORT: process.env.PORT || '3010',
      TEST_USER_EMAIL: process.env.TEST_USER_EMAIL || 'test@narrativeml.com',
      TEST_USER_PASSWORD: process.env.TEST_USER_PASSWORD || 'test-password-123',
    },
  },
});
