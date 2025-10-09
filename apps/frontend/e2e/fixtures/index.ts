/**
 * Combined E2E test fixtures
 * Merges authentication and data fixtures into a single test object
 */

import { test as base } from '@playwright/test';
import type { AuthFixtures } from './auth';
import type { DataFixtures } from './data';

// Import fixture implementations
import { readFileSync } from 'fs';
import { join } from 'path';

// Merge all fixtures
export const test = base.extend<AuthFixtures & DataFixtures>({
  // Auth fixtures
  testUser: async ({}, use) => {
    const user = {
      email: process.env.TEST_USER_EMAIL || 'test@narrativeml.com',
      id: 'test-user-id',
      name: 'Test User',
    };
    await use(user);
  },

  authenticatedPage: async ({ page, testUser }, use) => {
    const skipAuth = process.env.SKIP_AUTH === 'true';

    if (skipAuth) {
      await page.goto('/dashboard');
    } else {
      await page.goto('/auth/signin');
      await page.waitForLoadState('networkidle');

      const emailInput = page.locator('input[name="email"], input[type="email"]').first();
      const passwordInput = page.locator('input[name="password"], input[type="password"]').first();

      if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
        await emailInput.fill(testUser.email);
        await passwordInput.fill(process.env.TEST_USER_PASSWORD || 'test-password');

        const submitButton = page.locator('button[type="submit"]').first();
        await submitButton.click();

        await page.waitForURL('**/dashboard', { timeout: 10000 });
      } else {
        await page.goto('/dashboard');
      }
    }

    await page.waitForLoadState('networkidle');
    await use(page);
  },

  // Data fixtures
  testCSV: async ({}, use) => {
    const csvPath = join(__dirname, '../test-data/sample.csv');
    let csvBuffer: Buffer;

    try {
      csvBuffer = readFileSync(csvPath);
    } catch (error) {
      const defaultCSV = `age,income,purchased
25,50000,yes
35,75000,yes
45,60000,no
55,90000,yes
30,55000,no`;
      csvBuffer = Buffer.from(defaultCSV);
    }

    await use(csvBuffer);
  },

  uploadTestDataset: async ({ page }, use) => {
    const upload = async (): Promise<string> => {
      await page.goto('/datasets/upload');

      const fileInput = page.locator('input[type="file"]');
      const csvPath = join(__dirname, '../test-data/sample.csv');
      let fileBuffer: Buffer;

      try {
        fileBuffer = readFileSync(csvPath);
      } catch (error) {
        const defaultCSV = `age,income,purchased
25,50000,yes
35,75000,yes
45,60000,no
55,90000,yes
30,55000,no`;
        fileBuffer = Buffer.from(defaultCSV);
      }

      await fileInput.setInputFiles({
        name: 'test-data.csv',
        mimeType: 'text/csv',
        buffer: fileBuffer,
      });

      await page.waitForSelector('text=/Upload (complete|successful)/i', { timeout: 30000 });
      await page.waitForTimeout(1000);

      const url = page.url();
      const match = url.match(/\/datasets\/([a-zA-Z0-9-]+)/);
      const datasetId = match ? match[1] : '';

      if (!datasetId) {
        throw new Error('Could not extract dataset ID from URL: ' + url);
      }

      return datasetId;
    };

    await use(upload);
  },

  cleanupDataset: async ({ request }, use) => {
    const cleanup = async (datasetId: string) => {
      try {
        await request.delete(`/api/v1/datasets/${datasetId}`);
      } catch (error) {
        console.warn(`Failed to cleanup dataset ${datasetId}:`, error);
      }
    };

    await use(cleanup);
  },
});

// Re-export expect from Playwright
export { expect } from '@playwright/test';
