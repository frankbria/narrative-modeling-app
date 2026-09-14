/**
 * Combined E2E test fixtures
 * Merges authentication and data fixtures into a single test object
 */

import { test as base } from '@playwright/test';
import type { AuthFixtures } from './auth';
import type { DataFixtures } from './data';

// Import fixture implementations
import { readFileSync } from 'fs';
import { join, basename } from 'path';
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
    // Land the pre-authenticated test user (storage state from global-setup) on the
    // dashboard, deterministically — and when that can't happen, fail with a message
    // that names the actual landing URL instead of a bare toMatch(/dashboard/) miss.
    //
    // #578 was a per-RUN flake (it reproduced across Playwright's in-run retries, then
    // passed next run), so something in the run's setup — not the individual test — put
    // the whole run into a state this fixture couldn't escape. The two states that do
    // that here:
    //   - Auth: global-setup's saved session (e2e/.auth/user.json) didn't take for the
    //     run, so every navigation bounces to /auth/signin.
    //   - Onboarding: the shared single e2e user is mid first-time — its server-side
    //     /onboarding/status is reset by a concurrent spec (#550) — and lands on
    //     /onboarding. (Note the dashboard's redirect effect short-circuits on
    //     ?skipOnboarding=true while that param is in the URL — app/dashboard/page.tsx —
    //     so a bounce means the param was dropped by a navigation before the effect ran,
    //     or the redirect came from that shared-state path; the exact trigger isn't
    //     pinned statically, which is why the diagnostic below reports the real URL.)
    // Both persist across the run, so a retry inside one test re-enters them — the fix
    // has to be at the fixture level, per the issue.
    //
    // Navigate; if it bounced to /onboarding, skip once more (a fresh ?skipOnboarding with
    // the session warm), then report the outcome by naming the landing URL.
    const gotoDashboard = async (): Promise<string> => {
      await page.goto('/dashboard?skipOnboarding=true', { timeout: 30000 });
      await page.waitForLoadState('networkidle', { timeout: 15000 });
      return page.url();
    };

    let url = await gotoDashboard();
    if (url.includes('/onboarding')) {
      console.log('[authenticatedPage] bounced to /onboarding; retrying the skip once');
      url = await gotoDashboard();
    }

    if (url.includes('/auth/signin')) {
      throw new Error(
        '[authenticatedPage] not authenticated — landed on the sign-in page. The stored ' +
        `session (e2e/.auth/user.json from global-setup) is missing or expired. url=${url}`,
      );
    }
    if (!url.includes('/dashboard')) {
      throw new Error(
        `[authenticatedPage] could not settle on /dashboard — landed on ${url} after a ` +
        'skip-onboarding retry. If that is /onboarding, the shared e2e user is mid ' +
        'first-time (a concurrent onboarding-state reset, #550), not a product regression; ' +
        'any other route is an unexpected redirect worth investigating from this URL. This ' +
        "is the per-run state #578 describes — check whether this run's own retries all " +
        'failed before dismissing it as flaky.',
      );
    }

    console.log('[authenticatedPage] settled on the dashboard with the authenticated session');
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

      // Prepare file buffer. `fileName` may be a path relative to test-data
      // (e.g. "ai-test-datasets/binary-classification.csv"); the uploaded name
      // and the explore heading use the basename only.
      const uploadName = basename(fileName);
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
        name: uploadName,
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
      const exploreHeading = page.locator('h1', { hasText: uploadName });
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
      // API calls must target the backend directly — Next.js does not proxy
      // /api/v1/* to the FastAPI server. Backend runs with SKIP_AUTH=true in
      // E2E, but HTTPBearer still requires some Authorization header.
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
      const headers = { Authorization: 'Bearer e2e-test-token' };
      const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
      const describe = (e: unknown) => (e instanceof Error ? e.message : String(e));

      // Fail loudly (issue #156): the old fixture swallowed every failure and
      // returned 'mock-model-id', so downstream tests broke at the predict step
      // with a misleading error instead of surfacing the train failure here.

      // 1. Submit training, retrying only transient server-side failures. The
      //    real ML pipeline lives under /api/v1/ml (AutoMLEngine +
      //    ModelStorageService); /api/v1/models only stores config records.
      const maxSubmitRetries = 2;
      let modelId: string | undefined;
      for (let attempt = 0; attempt <= maxSubmitRetries; attempt++) {
        try {
          const response = await request.post(`${apiBase}/ml/train`, {
            headers,
            data: { dataset_id: datasetId, target_column: targetColumn },
            timeout: 30000,
          });
          if (!response.ok()) {
            // Throw so the single catch below owns all retry/abort decisions.
            throw new Error(
              `POST /ml/train failed (${response.status()}): ${await response.text()}`
            );
          }
          const data = await response.json();
          modelId = data.model_id || data.id;
          if (!modelId) {
            throw new Error(`Training response carried no model id: ${JSON.stringify(data)}`);
          }
          break;
        } catch (error) {
          if (attempt < maxSubmitRetries) {
            await delay(2000 * (attempt + 1));
            continue;
          }
          throw new Error(
            `trainModel: submitting training failed after ${maxSubmitRetries + 1} attempts: ${describe(error)}`
          );
        }
      }
      // The loop only `break`s once modelId is set, and otherwise throws on the
      // final attempt — this guard makes that invariant explicit for the poll.
      if (!modelId) {
        throw new Error('trainModel: no model id after submit loop (unreachable)');
      }

      // 2. Training runs as a background task; poll until the model artifact is
      //    retrievable from GET /api/v1/ml/{id} (200 only once it is saved).
      const maxPollAttempts = 30; // ~60 seconds
      for (let pollAttempts = 0; pollAttempts < maxPollAttempts; pollAttempts++) {
        await delay(2000);
        try {
          const statusResponse = await request.get(`${apiBase}/ml/${modelId}`, {
            headers,
            timeout: 5000,
          });
          if (statusResponse.ok()) {
            return modelId;
          }
        } catch {
          // Transient network error — keep polling
        }
      }
      throw new Error(
        `trainModel: model ${modelId} did not become retrievable within ~60s`
      );
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
