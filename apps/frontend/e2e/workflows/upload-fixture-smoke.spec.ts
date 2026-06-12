/**
 * Upload Fixture Smoke Tests (issue #191)
 *
 * Validates the shared `uploadTestDataset` fixture in isolation so that UI
 * drift in the upload flow is caught here first — with a precise error —
 * instead of as opaque beforeEach failures across every workflow spec.
 *
 * If these tests fail, fix the fixture (or the upload flow) before chasing
 * failures in other specs: they all funnel through this fixture.
 */

import { test, expect } from '../fixtures';
import { join } from 'path';

test.describe('Upload fixture smoke', () => {
  let datasetId: string | undefined;

  test.afterEach(async ({ cleanupDataset }) => {
    if (datasetId) {
      await cleanupDataset(datasetId);
      datasetId = undefined;
    }
  });

  test('uploadTestDataset uploads and lands on the explore page @smoke', async ({
    page,
    uploadTestDataset,
  }) => {
    datasetId = await uploadTestDataset();

    // A real stored ID (Mongo ObjectId / UUID shape), not a placeholder
    expect(datasetId).toMatch(/^[a-zA-Z0-9-]{8,}$/);

    expect(page.url()).toContain(`/explore/${datasetId}`);

    // Explore page actually rendered (no stage-gate redirect back to /upload)
    await expect(page.locator('h1', { hasText: 'sample.csv' })).toBeVisible();
  });

  test('upload error state is detectable via upload-error testid @smoke', async ({
    page,
  }) => {
    await page.goto('/upload');

    const fileInput = page.getByTestId('file-input');
    await fileInput.waitFor({ state: 'attached', timeout: 10000 });
    await fileInput.setInputFiles(join(__dirname, '../test-data/invalid.json'));

    const uploadButton = page.getByTestId('upload-button');
    await uploadButton.waitFor({ state: 'visible', timeout: 5000 });
    await uploadButton.click();

    // Backend rejects the unsupported format; the inline error panel renders
    await expect(page.getByTestId('upload-error')).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId('upload-error-message')).toBeVisible();

    // No success affordances, and we never left the upload page
    expect(page.url()).toContain('/upload');
    await expect(page.getByTestId('next-step-button')).not.toBeVisible();
  });
});
