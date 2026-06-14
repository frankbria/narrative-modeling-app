/**
 * Prediction Workflow E2E Tests (issue #82)
 *
 * Drives the real, wired prediction page end to end through the live stack:
 *   upload trainable dataset -> train model -> seed workflow to PREDICTION ->
 *   auto-generated single-prediction form -> batch CSV -> downloadable results.
 *
 * These tests FAIL LOUDLY. The previous version wrapped every assertion in
 * try/catch + console.log + return, so it passed even when nothing worked
 * (the masking anti-pattern fixed for the train fixture in #156). If the
 * prediction feature regresses, this spec must go red.
 */

import { readFileSync } from 'fs';
import { join } from 'path';
import { test, expect } from '../fixtures';
import type { Page, APIRequestContext } from '@playwright/test';
import { PredictPage } from '../pages/PredictPage';

const TRAINABLE_DATASET = 'ai-test-datasets/binary-classification-small.csv';
const TARGET_COLUMN = 'churned';

/**
 * Seed the backend workflow (source of truth since #87) up to a completed
 * MODEL_EVALUATION with the trained model id, so the MODEL_EVALUATION-gated
 * /predict page is reachable instead of redirecting to /upload. Mirrors the
 * seed helper proven for the prepare page (data-preparation.spec.ts).
 */
async function seedPredictionWorkflow(
  page: Page,
  request: APIRequestContext,
  datasetId: string,
  modelId: string
): Promise<void> {
  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  const headers = {
    Authorization: 'Bearer dev-user-default',
    'Content-Type': 'application/json',
  };
  const completed = [
    'data_loading',
    'data_profiling',
    'data_preparation',
    'feature_engineering',
    'model_training',
    'model_evaluation',
  ];
  const workflow = {
    current_stage: 'prediction',
    completed_stages: completed,
    stage_data: {},
    model_id: modelId,
  };

  const put = await request.put(`${apiBase}/workflows/${datasetId}`, {
    headers,
    data: workflow,
  });
  if (put.status() === 404) {
    const post = await request.post(`${apiBase}/workflows/${datasetId}`, {
      headers,
      data: workflow,
    });
    if (!post.ok()) {
      throw new Error(
        `seedPredictionWorkflow POST failed (${post.status()}): ${await post.text()}`
      );
    }
  } else if (!put.ok()) {
    throw new Error(
      `seedPredictionWorkflow PUT failed (${put.status()}): ${await put.text()}`
    );
  }

  await page.addInitScript(
    ({ id, model }) => {
      localStorage.setItem(
        'workflowState',
        JSON.stringify({
          currentStage: 'prediction',
          completedStages: [
            'data_loading',
            'data_profiling',
            'data_preparation',
            'feature_engineering',
            'model_training',
            'model_evaluation',
          ],
          stageData: {},
          datasetId: id,
          modelId: model,
          lastUpdated: new Date().toISOString(),
        })
      );
    },
    { id: datasetId, model: modelId }
  );
}

/** Build a batch CSV (feature columns only — the target is dropped so the
 *  fitted pipeline gets exactly the columns it was trained on) from the first
 *  few rows of the training dataset, guaranteeing valid categorical values. */
function buildBatchCsv(rows = 3): { name: string; mimeType: string; buffer: Buffer } {
  const csvPath = join(__dirname, '../test-data', TRAINABLE_DATASET);
  const lines = readFileSync(csvPath, 'utf-8').trim().split(/\r?\n/);
  const header = lines[0].split(',');
  const targetIdx = header.indexOf(TARGET_COLUMN);
  const keep = (cols: string[]) => cols.filter((_, i) => i !== targetIdx).join(',');
  const out = [keep(header), ...lines.slice(1, 1 + rows).map((l) => keep(l.split(',')))];
  return {
    name: 'batch-input.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(out.join('\n')),
  };
}

test.describe('Prediction Workflow (#82)', () => {
  let datasetId: string;
  let modelId: string;

  test.beforeEach(async ({ page, request, uploadTestDataset, trainModel }) => {
    // Real AutoML training + artifact-save poll is slow on 2-core CI runners.
    test.setTimeout(180000);
    datasetId = await uploadTestDataset(TRAINABLE_DATASET);
    modelId = await trainModel(datasetId, TARGET_COLUMN);
    await seedPredictionWorkflow(page, request, datasetId, modelId);
  });

  test.afterEach(async ({ cleanupDataset }) => {
    if (datasetId) {
      await cleanupDataset(datasetId);
    }
  });

  test('single + batch prediction through the wired UI @smoke', async ({
    authenticatedPage,
  }) => {
    const predictPage = new PredictPage(authenticatedPage);
    await authenticatedPage.goto(`/predict/${datasetId}`);

    // The page must NOT redirect to /upload — that means workflow gating or the
    // model id was not satisfied, which is a real failure, not a skip.
    await expect(authenticatedPage).not.toHaveURL(/\/upload/, { timeout: 15000 });

    // The auto-generated form loads its fields from GET /ml/{id}/features.
    const featureInputs = authenticatedPage.locator('input[data-feature]');
    await expect(featureInputs.first()).toBeVisible({ timeout: 15000 });

    // ---- AC3: missing-feature handling -> predict is gated until filled. ----
    await featureInputs.first().fill('');
    await expect(authenticatedPage.getByTestId('make-prediction')).toBeDisabled();

    // ---- AC1: fill every numeric field, then make a single prediction. ----
    const count = await featureInputs.count();
    for (let i = 0; i < count; i++) {
      await featureInputs.nth(i).fill('1');
    }
    // Click the button by test id directly: the shared PredictPage.predict()
    // selector matches `button:has-text("Predict")`, which also matches the
    // "Single Prediction" mode toggle (substring) and would mis-click.
    await authenticatedPage.getByTestId('make-prediction').click();

    await predictPage.waitForPredictionResult(20000);
    const predictionValue = await predictPage.getPredictionValue();
    expect(predictionValue.trim().length).toBeGreaterThan(0);
    // Classification model -> a confidence score is rendered.
    await expect(authenticatedPage.getByTestId('confidence-score')).toBeVisible();

    // ---- AC4: batch prediction -> progress -> summary -> download. ----
    await authenticatedPage.getByTestId('batch-prediction-link').click();
    await authenticatedPage
      .getByTestId('batch-file-input')
      .setInputFiles(buildBatchCsv(3));
    await authenticatedPage.getByTestId('start-batch-prediction').click();

    // Job runs as a background task; the page polls progress to completion.
    await expect(authenticatedPage.getByTestId('batch-summary')).toBeVisible({
      timeout: 60000,
    });

    // The completed summary offers a downloadable results CSV.
    const downloadPromise = authenticatedPage.waitForEvent('download');
    await authenticatedPage.getByTestId('download-predictions').click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain('batch_results');
  });
});
