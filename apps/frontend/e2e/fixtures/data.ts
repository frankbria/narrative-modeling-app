import { test as base } from '@playwright/test';
import { readFileSync } from 'fs';
import { join } from 'path';

export type DataFixtures = {
  testCSV: Buffer;
  uploadTestDataset: () => Promise<string>;
  cleanupDataset: (datasetId: string) => Promise<void>;
};

/**
 * Extended test with data management fixtures
 * Provides utilities for test data creation and cleanup
 */
export const test = base.extend<DataFixtures>({
  /**
   * Test CSV data fixture - provides sample CSV buffer
   */
  testCSV: async ({}, use) => {
    const csvPath = join(__dirname, '../test-data/sample.csv');
    let csvBuffer: Buffer;

    try {
      csvBuffer = readFileSync(csvPath);
    } catch (error) {
      // If file doesn't exist, create a default CSV
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

  /**
   * Upload test dataset fixture - handles file upload and returns dataset ID
   */
  uploadTestDataset: async ({ page }, use) => {
    const upload = async (): Promise<string> => {
      await page.goto('/datasets/upload');

      // Get the file input element
      const fileInput = page.locator('input[type="file"]');

      // Upload file
      const csvPath = join(__dirname, '../test-data/sample.csv');
      let fileBuffer: Buffer;

      try {
        fileBuffer = readFileSync(csvPath);
      } catch (error) {
        // Create default test data if file doesn't exist
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

      // Wait for upload to complete
      await page.waitForSelector('text=/Upload (complete|successful)/i', {
        timeout: 30000,
      });

      // Extract dataset ID from URL
      await page.waitForTimeout(1000); // Give time for navigation
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

  /**
   * Cleanup dataset fixture - removes test dataset via API
   */
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

export { expect } from '@playwright/test';
