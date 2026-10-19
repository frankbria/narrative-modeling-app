import { defineConfig, devices } from '@playwright/test';
import base from './playwright.config';

/**
 * Re-records the public /how-it-works images (#772): `npm run capture:how-it-works`.
 * The normal run never matches `*.capture.ts`, so nothing here runs in CI.
 */
export default defineConfig({
  ...base,
  testMatch: /.*\.capture\.ts/,
  workers: 1,
  reporter: 'list',
  projects: [{ name: 'capture', use: { ...devices['Desktop Chrome'] } }],
});
