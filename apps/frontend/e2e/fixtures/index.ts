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

  /**
   * Shared upload fixture: drives the full upload flow through the real UI
   * and returns the stored dataset's file ID.
   *
   * Provides `upload(fileName?: string): Promise<string>` — flow: navigate to
   * /upload → wait for dropzone → attach file (from e2e/test-data, falling
   * back to an inline CSV) → click upload → wait for the success panel or the
   * inline error → parse the file ID from the success panel → click Next Step
   * → verify landing on /explore/{fileId}.
   *
   * Failure mode: any step that fails throws via the internal `fail` helper,
   * which includes the failing step name, the current URL, and any visible
   * upload-error text — so UI drift or a broken backend is diagnosable from
   * the test output alone (issue #191).
   */
  uploadTestDataset: async ({ page }, use) => {
    const upload = async (fileName: string = 'sample.csv'): Promise<string> => {
      // Every step failure reports the current URL plus any visible upload
      // error so a drifted UI or a broken backend is diagnosable from the
      // test output alone (issue #191).
      const fail = async (step: string, cause?: unknown): Promise<never> => {
        const errorText = await page
          .getByTestId('upload-error')
          .textContent({ timeout: 1000 })
          .catch(() => null);
        throw new Error(
          `uploadTestDataset failed at "${step}". Current URL: ${page.url()}` +
            (errorText ? `. Upload error shown: ${errorText.trim()}` : '') +
            (cause instanceof Error ? `. Cause: ${cause.message}` : '')
        );
      };

      // Navigate to upload page
      await page.goto('/upload');

      // Wait for dropzone container to be visible (react-dropzone needs this)
      const dropzone = page.getByTestId('upload-dropzone');
      await dropzone
        .waitFor({ state: 'visible', timeout: 10000 })
        .catch((e) => fail('waiting for upload dropzone', e));

      // Locate hidden file input using data-testid
      const fileInput = page.getByTestId('file-input');
      await fileInput
        .waitFor({ state: 'attached', timeout: 10000 })
        .catch((e) => fail('waiting for file input', e));

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
      await uploadButton
        .waitFor({ state: 'visible', timeout: 5000 })
        .catch((e) => fail('waiting for upload button', e));
      await uploadButton
        .and(page.locator(':not([disabled])'))
        .waitFor({ state: 'visible', timeout: 5000 })
        .catch((e) => fail('waiting for upload button to be enabled', e));

      // Click upload button
      await uploadButton.click();

      // The upload page does not auto-navigate: it shows a success panel
      // (with the new file's ID) or an inline error. Wait for whichever
      // appears first so backend failures surface immediately with their
      // message instead of as an opaque 30s timeout.
      const successPanel = page.getByTestId('upload-status');
      const errorPanel = page.getByTestId('upload-error');
      await successPanel
        .or(errorPanel)
        .waitFor({ state: 'visible', timeout: 30000 })
        .catch((e) => fail('waiting for upload success or error panel', e));
      if (await errorPanel.isVisible()) {
        await fail('upload (backend rejected or request failed)');
      }

      // The success panel must carry the stored file ID — this is what the
      // explore page is keyed on.
      const fileIdLabel = page.getByTestId('file-id');
      await fileIdLabel
        .waitFor({ state: 'visible', timeout: 10000 })
        .catch((e) => fail('waiting for file ID in success panel', e));
      const fileIdText = (await fileIdLabel.textContent()) ?? '';
      const fileId = fileIdText.match(/File ID:\s*([a-zA-Z0-9-]+)/)?.[1];
      if (!fileId) {
        // return (not await): TS only narrows fileId to string when this
        // branch provably exits the function
        return fail(`parsing file ID from success panel ("${fileIdText.trim()}")`);
      }

      const nextStepButton = page.getByTestId('next-step-button');
      await nextStepButton
        .waitFor({ state: 'visible', timeout: 10000 })
        .catch((e) => fail('waiting for next-step button', e));
      await nextStepButton.click();
      await page
        .waitForURL(new RegExp(`/explore/${fileId}`), { timeout: 30000 })
        .catch((e) => fail('navigating to explore page', e));

      // Stability check: the explore page stage-gates on workflow state and
      // redirects back to /upload when DATA_LOADING isn't marked complete.
      // Waiting for the dataset heading proves we actually landed.
      const exploreHeading = page.locator('h1', { hasText: fileName });
      try {
        await exploreHeading.waitFor({ state: 'visible', timeout: 15000 });
      } catch (e) {
        if (page.url().includes('/upload')) {
          await fail('explore page redirected back to /upload (workflow state not persisted)');
        }
        await fail('waiting for explore page content', e);
      }

      return fileId;
    };

    await use(upload);
  },

  cleanupDataset: async ({ request }, use) => {
    const cleanup = async (datasetId: string) => {
      try {
        // Target the backend directly (Next.js does not proxy /api/v1);
        // a relative URL hits the dev server and burns a 15s timeout per test
        const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        await request.delete(`${apiBase}/datasets/${datasetId}`, {
          headers: { Authorization: 'Bearer e2e-test-token' },
          timeout: 5000,
        });
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
