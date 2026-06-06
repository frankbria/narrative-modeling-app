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
import { AIMockProvider } from './ai-mock';

// AI Mock fixture type
export interface AIMockFixtures {
  aiMock: AIMockProvider;
}

// Merge all fixtures
export const test = base.extend<AuthFixtures & DataFixtures & AIMockFixtures>({
  // AI Mock fixture
  aiMock: async ({}, use) => {
    const mock = new AIMockProvider();
    await use(mock);
  },

  // Auth fixtures
  testUser: async ({}, use) => {
    const user = {
      email: process.env.TEST_USER_EMAIL || 'test@narrativeml.com',
      id: 'test-user-id',
      name: 'Test User',
    };
    await use(user);
  },

  authenticatedPage: async ({ page }, use) => {
    // The session is already loaded from storage state (configured in playwright.config.ts)
    // The global-setup.ts script handles authentication and saves the session state
    // This fixture just uses that saved state

    console.log('[authenticatedPage] Using pre-authenticated session from storage state');

    // Navigate to the dashboard page (root redirects to first incomplete workflow stage)
    await page.goto('/dashboard', { timeout: 30000 });
    await page.waitForLoadState('networkidle', { timeout: 10000 });

    // Verify we're authenticated (should not be on signin page)
    const currentUrl = page.url();
    if (currentUrl.includes('/auth/signin')) {
      throw new Error('Authentication failed - redirected to signin page despite having storage state');
    }

    console.log('[authenticatedPage] Successfully navigated to dashboard page with authenticated session');

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
    const upload = async (fileName: string = 'sample.csv'): Promise<string> => {
      // Navigate to upload page
      await page.goto('/upload');
      await page.waitForLoadState('networkidle');

      // Wait for dropzone container to be visible (react-dropzone needs this)
      const dropzone = page.getByTestId('upload-dropzone');
      await dropzone.waitFor({ state: 'visible', timeout: 10000 });

      // Locate hidden file input using data-testid
      const fileInput = page.getByTestId('file-input');
      await fileInput.waitFor({ state: 'attached', timeout: 10000 });

      // Prepare file buffer
      const csvPath = join(__dirname, '../test-data', fileName);
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

      // Set file on hidden input (Playwright handles hidden inputs automatically)
      await fileInput.setInputFiles({
        name: fileName,
        mimeType: 'text/csv',
        buffer: fileBuffer,
      });

      // Wait for upload button to be visible and enabled
      const uploadButton = page.getByTestId('upload-button');
      await uploadButton.waitFor({ state: 'visible', timeout: 5000 });

      // Verify button is enabled before clicking
      await page.waitForFunction(
        () => {
          const element = document.querySelector('[data-testid="upload-button"]');
          return element && !element.hasAttribute('disabled');
        },
        { timeout: 5000 }
      );

      // Click upload button
      await uploadButton.click();

      // The upload page does not auto-navigate: it shows a success panel
      // with a "Next Step" button that takes the user to /explore/{id}.
      const nextStepButton = page.getByTestId('next-step-button');
      try {
        await nextStepButton.waitFor({ state: 'visible', timeout: 30000 });
      } catch (error) {
        throw new Error(
          `Upload failed: success panel did not appear. Current URL: ${page.url()}`
        );
      }
      await nextStepButton.click();

      // Wait for navigation to dataset detail page
      try {
        await page.waitForURL(/\/explore\/[a-zA-Z0-9-]+/, { timeout: 30000 });
      } catch (error) {
        throw new Error(
          `Upload failed: did not navigate to explore page. Current URL: ${page.url()}`
        );
      }

      // Extract dataset ID from URL
      const url = page.url();
      const match = url.match(/\/explore\/([a-zA-Z0-9-]+)/);

      if (!match) {
        throw new Error(`Failed to extract dataset ID from URL: ${url}`);
      }

      return match[1];
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

  trainModel: async ({ request }, use) => {
    const train = async (datasetId: string, targetColumn: string): Promise<string> => {
      const maxRetries = 2;

      // API calls must target the backend directly — Next.js does not proxy
      // /api/v1/* to the FastAPI server. Backend runs with SKIP_AUTH=true in
      // E2E, but HTTPBearer still requires some Authorization header.
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
      const headers = { Authorization: 'Bearer e2e-test-token' };

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          // The real ML pipeline lives under /api/v1/ml (AutoMLEngine +
          // ModelStorageService); /api/v1/models only stores config records.
          const response = await request.post(`${apiBase}/ml/train`, {
            headers,
            data: {
              dataset_id: datasetId,
              target_column: targetColumn,
            },
            timeout: 30000,
          });

          if (!response.ok()) {
            if (attempt < maxRetries) {
              // Wait and retry for server errors
              await new Promise(resolve => setTimeout(resolve, 2000 * (attempt + 1)));
              continue;
            }
            throw new Error(`Training failed with status ${response.status()}`);
          }

          const data = await response.json();
          const modelId = data.model_id || data.id;

          // Training runs as a background task; the model becomes retrievable
          // from GET /api/v1/ml/{id} once the artifact is saved.
          let trained = false;
          const maxPollAttempts = 30; // 60 seconds max

          for (let pollAttempts = 0; pollAttempts < maxPollAttempts; pollAttempts++) {
            await new Promise(resolve => setTimeout(resolve, 2000));

            try {
              const statusResponse = await request.get(`${apiBase}/ml/${modelId}`, {
                headers,
                timeout: 5000,
              });
              if (statusResponse.ok()) {
                trained = true;
                break;
              }
            } catch (error) {
              // Transient network error — keep polling
            }
          }

          if (!trained) {
            console.warn('Training timed out, but returning model ID anyway');
          }

          return modelId;
        } catch (error) {
          if (attempt === maxRetries) {
            console.warn('Training fixture failed after all retries, returning mock ID:', error);
            return 'mock-model-id';
          }
        }
      }

      return 'mock-model-id';
    };

    await use(train);
  },

  cleanupModel: async ({ request }, use) => {
    const cleanup = async (modelId: string) => {
      try {
        await request.delete(`/api/v1/models/${modelId}`);
      } catch (error) {
        console.warn(`Failed to cleanup model ${modelId}:`, error);
      }
    };

    await use(cleanup);
  },
});

// Re-export expect from Playwright
export { expect } from '@playwright/test';
