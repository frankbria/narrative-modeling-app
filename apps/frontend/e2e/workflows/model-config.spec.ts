/**
 * A training run on the real stack, after it starts (#991).
 *
 * train-form.spec.ts proves the form starts a run; training-errors.spec.ts covers the
 * runs that do not start or do not finish. This spec follows a run to its end (or to a
 * cancel) and reads what it stored. Every dataset is erased afterwards, and its models
 * go with it (#943).
 */

import { test, expect } from '../fixtures';
import {
  BINARY_CLASS_DATASET,
  BINARY_CLASS_TARGET,
} from '../helpers/binaryClassificationData';
import { chooseTarget, seedTrainingWorkflow } from '../helpers/seedWorkflow';
import { API_BASE, mlAuth } from '../helpers/mlApi';

test.describe('Model training run', () => {
  test('shows progress and the result of a run', async ({
    authenticatedPage: page,
    request,
    uploadTestDataset,
    cleanupDataset,
  }) => {
    test.setTimeout(240000);
    const datasetId = await uploadTestDataset(BINARY_CLASS_DATASET);
    try {
      await seedTrainingWorkflow(page, request, datasetId);
      await page.goto('/model');
      await chooseTarget(page, BINARY_CLASS_TARGET);
      await page.getByRole('button', { name: /Start Training/ }).click();

      await expect(page.getByRole('progressbar')).toBeVisible({ timeout: 30000 });
      await expect(page.getByText('Training complete')).toBeVisible({ timeout: 180000 });
      await expect(page.getByRole('heading', { name: 'Why these algorithms?' })).toBeVisible();
    } finally {
      await cleanupDataset(datasetId);
    }
  });

  test('cancels a run in progress', async ({
    authenticatedPage: page,
    request,
    uploadTestDataset,
    cleanupDataset,
  }) => {
    test.setTimeout(240000);
    const datasetId = await uploadTestDataset(BINARY_CLASS_DATASET);
    try {
      await seedTrainingWorkflow(page, request, datasetId);
      await page.goto('/model');
      await chooseTarget(page, BINARY_CLASS_TARGET);
      // The slowest mode, so the run is still going when the cancel lands.
      await page.getByTestId('mode-option-comprehensive').click();
      await page.getByRole('button', { name: /Start Training/ }).click();

      await page.getByRole('button', { name: 'Cancel Training' }).click();
      await page.getByRole('button', { name: 'Yes, cancel training' }).click();
      await expect(page.getByText(/Cancellation requested/)).toBeVisible();
      await expect(page.getByText('Training cancelled').first()).toBeVisible({ timeout: 180000 });
    } finally {
      await cleanupDataset(datasetId);
    }
  });

  test('stores the metrics of a trained model', async ({
    request,
    uploadTestDataset,
    trainModel,
    cleanupDataset,
  }) => {
    test.setTimeout(180000);
    const datasetId = await uploadTestDataset(BINARY_CLASS_DATASET);
    try {
      const modelId = await trainModel(datasetId, BINARY_CLASS_TARGET);
      const response = await request.get(`${API_BASE}/ml/${modelId}`, {
        headers: await mlAuth(request),
      });
      expect(response.ok()).toBeTruthy();

      const { metrics } = await response.json();
      expect(typeof metrics).toBe('object');
      const values = Object.values(metrics ?? {});
      expect(values.length).toBeGreaterThan(0);
      for (const value of values.filter((v) => typeof v === 'number')) {
        expect(value).toBeGreaterThanOrEqual(0);
      }
    } finally {
      await cleanupDataset(datasetId);
    }
  });
});

test.describe('Legacy training surface', () => {
  test('/models/train answers 410 and points at /ml/train', async ({ request }) => {
    // #274: the legacy ModelConfig train endpoint reported status="training" but never trained.
    const response = await request.post(`${API_BASE}/models/train`, {
      headers: await mlAuth(request),
      data: { dataset_id: 'any', target_column: 'purchased' },
    });

    expect(response.status()).toBe(410);
    const body = await response.json();
    expect(body.detail).toContain('ml/train');
  });
});
