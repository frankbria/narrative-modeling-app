/**
 * Seamless stage transitions (issue #88).
 *
 * Verifies the two halves of the feature:
 *  1. The whole 8-stage journey (upload → predict) can be driven using only the
 *     "Continue to next stage" CTAs, with state carried forward.
 *  2. Opening a gated stage directly (no prerequisites) redirects the user with
 *     a helpful guard message instead of rendering an empty shell.
 *
 * Per the issue's decision, the ML backend is MOCKED here (training, evaluation,
 * prediction, etc.) so the journey is deterministic and fast and does not depend
 * on a trainable dataset or the full ML stack — this test exercises the
 * frontend transition behaviour, which is what #88 delivers. The real
 * end-to-end ML pipeline is covered by complete-ai-workflow.spec.ts.
 */

import { test, expect } from '../fixtures';
import type { Page, Route } from '@playwright/test';

const DATASET_ID = 'e2e-nav-ds';
const MODEL_ID = 'e2e-nav-model';

const completedTrainingStatus = {
  model_id: MODEL_ID,
  status: 'completed',
  progress: 1,
  current_algorithm: null,
  completed_algorithms: 3,
  total_algorithms: 3,
  metrics: { accuracy: 0.91 },
  model_comparison: [],
  algorithm_recommendations: [],
  best_model_id: MODEL_ID,
  best_algorithm: 'random_forest',
  explanation: 'Random forest performed best on held-out data.',
  error: null,
  current_stage: 'completed',
  elapsed_seconds: 1,
  estimated_remaining_seconds: 0,
  cancellation_requested: false,
};

const evaluationResponse = {
  model_id: MODEL_ID,
  model_name: 'E2E Model',
  algorithm: 'random_forest',
  problem_type: 'binary_classification',
  partial: false,
  metrics: {
    accuracy: 0.91,
    precision_macro: 0.9,
    precision_weighted: 0.905,
    recall_macro: 0.89,
    recall_weighted: 0.912,
    f1_macro: 0.9,
    f1_weighted: 0.9075,
    roc_auc: 0.95,
    log_loss: 0.31,
    per_class_metrics: {
      yes: { precision: 0.9, recall: 0.88, f1: 0.89, support: 50 },
      no: { precision: 0.92, recall: 0.93, f1: 0.92, support: 70 },
    },
  },
  stored_metrics: { cv_score: 0.9, test_score: 0.91 },
  confusion_matrix: { labels: ['yes', 'no'], matrix: [[44, 6], [5, 65]] },
  roc_curve: {
    curves: { yes: [{ x: 0, y: 0 }, { x: 1, y: 1 }] },
    auc_per_class: { yes: 0.95 },
    macro_auc: 0.95,
  },
  pr_curve: {
    curves: { yes: [{ x: 0, y: 1 }, { x: 1, y: 0.42 }] },
    baseline_per_class: { yes: 0.42 },
  },
  feature_importance: { feature_a: 0.6, feature_b: 0.4 },
  ai_explanation: {
    overall_assessment: 'Strong performance on held-out data.',
    metric_explanations: { accuracy: '91% of predictions correct.' },
    strengths: ['High accuracy'],
    concerns: [],
    recommendations: [],
    generated_by: 'fallback',
  },
  evaluated_at: '2026-06-11T00:00:00Z',
};

const modelFeaturesResponse = {
  features: [
    { name: 'feature_a', type: 'number' },
    { name: 'feature_b', type: 'number' },
  ],
  class_labels: ['yes', 'no'],
  problem_type: 'binary_classification',
  target_column: 'target',
};

const predictResponse = {
  predictions: ['yes'],
  probabilities: [[0.9, 0.1]],
  confidence: [0.9],
  class_labels: ['yes', 'no'],
  feature_names: ['feature_a', 'feature_b'],
  model_info: {
    model_id: MODEL_ID,
    algorithm: 'random_forest',
    problem_type: 'binary_classification',
    target_column: 'target',
  },
  low_confidence: [false],
  is_calibrated: true,
  confidence_threshold: 0.7,
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

/**
 * Mock every backend call the journey touches. Workflow persistence GETs return
 * 404 so the in-browser WorkflowContext (with its localStorage cache) is the
 * source of truth; writes succeed.
 */
async function mockBackend(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    // Workflow persistence
    if (url.includes('/workflows/')) {
      if (method === 'GET') return json(route, { detail: 'not found' }, 404);
      return json(route, { ok: true });
    }

    // Upload
    if (url.includes('/upload/secure')) {
      return json(route, {
        status: 'success',
        file_id: DATASET_ID,
        filename: 'binary-classification.csv',
        preview: [{ feature_a: 1, feature_b: 2, target: 'yes' }],
      });
    }

    // Dataset record (explore profiling page + model column list)
    if (url.includes('/user_data/')) {
      return json(route, {
        id: DATASET_ID,
        _id: DATASET_ID,
        filename: 'binary-classification.csv',
        is_processed: true,
        num_rows: 100,
        num_columns: 3,
        data_schema: [
          { field_name: 'feature_a' },
          { field_name: 'feature_b' },
          { field_name: 'target' },
        ],
      });
    }

    // Feature engineering (order: most specific first)
    if (url.includes('/features/suggestions')) {
      return json(route, { summary: 'Looks good.', recommendations: [] });
    }
    if (url.includes('/features/generate')) {
      return json(route, { newFeatures: [] });
    }
    if (url.match(/\/datasets\/[^/]+\/features/)) {
      return json(route, {
        features: [
          { name: 'feature_a', type: 'numeric' },
          { name: 'feature_b', type: 'numeric' },
        ],
      });
    }

    // ML pipeline (mocked training)
    if (url.includes('/ml/train')) {
      return json(route, { model_id: MODEL_ID, status: 'queued', message: 'ok' });
    }
    if (url.match(/\/ml\/[^/]+\/status/)) {
      return json(route, completedTrainingStatus);
    }
    if (url.match(/\/ml\/[^/]+\/evaluation/)) {
      return json(route, evaluationResponse);
    }
    if (url.match(/\/ml\/[^/]+\/shap/)) {
      return json(route, { detail: 'no shap' }, 404);
    }
    if (url.match(/\/ml\/[^/]+\/features/)) {
      return json(route, modelFeaturesResponse);
    }
    if (url.match(/\/ml\/[^/]+\/predict/)) {
      return json(route, predictResponse);
    }
    if (url.match(/\/ml\/[^/]+\/logs/)) {
      return json(route, { logs: [], total_count: 0 });
    }

    // Deployment status check
    if (url.match(/\/models\/[^/]+\/deployment/)) {
      return json(route, { deployment: null });
    }

    // Anything else the pages poll for — return an empty success.
    return json(route, {});
  });
}

test.describe.serial('Seamless stage transitions (#88)', () => {
  test.setTimeout(120000);

  test('redirects a directly-opened gated stage with a helpful message @smoke', async ({ page }) => {
    await mockBackend(page);
    // Start clean so no prerequisites are marked complete.
    await page.addInitScript(() => window.localStorage.clear());

    await page.goto(`/predict/${DATASET_ID}`);

    // The guard redirects away from the gated prediction stage...
    await expect(page).not.toHaveURL(new RegExp(`/predict/${DATASET_ID}`), { timeout: 15000 });
    // ...and surfaces a helpful, dismissible message instead of an empty page.
    const banner = page.getByTestId('stage-guard-banner');
    await expect(banner).toBeVisible({ timeout: 10000 });
    await expect(banner).toContainText(/before you can access/i);
  });

  test('drives the whole journey upload → predict using only Continue CTAs', async ({ page }) => {
    await mockBackend(page);
    await page.addInitScript(() => window.localStorage.clear());

    // --- Stage 1: Data loading (upload) ---
    await page.goto('/upload');
    await page.getByTestId('file-input').setInputFiles({
      name: 'binary-classification.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('feature_a,feature_b,target\n1,2,yes\n3,4,no\n'),
    });
    await page.getByTestId('upload-button').click();
    await expect(page.getByTestId('upload-status')).toBeVisible({ timeout: 15000 });
    await page.getByTestId('next-step-button').click();
    await expect(page).toHaveURL(new RegExp(`/explore/${DATASET_ID}`), { timeout: 15000 });

    // --- Stage 2: Data profiling (one-click "Complete & Continue") ---
    await page.getByRole('button', { name: /Complete & Continue to Data Preparation/i }).click();
    await expect(page).toHaveURL(/\/prepare$/, { timeout: 15000 });

    // --- Stage 3: Data preparation (optional → Continue advances) ---
    await page.getByTestId('continue-button').click();
    await expect(page).toHaveURL(/\/features$/, { timeout: 15000 });

    // --- Stage 4: Feature engineering ---
    await page.getByTestId('generate-features-button').click();
    const featuresContinue = page.getByTestId('continue-button');
    await expect(featuresContinue).toBeEnabled({ timeout: 15000 });
    await featuresContinue.click();
    await expect(page).toHaveURL(/\/model$/, { timeout: 15000 });

    // --- Stage 5: Model training (mocked) ---
    await page.locator('select').selectOption('target');
    await page.getByRole('button', { name: /Start Training/i }).click();
    const modelContinue = page.getByTestId('continue-button');
    await expect(modelContinue).toBeEnabled({ timeout: 30000 });
    await modelContinue.click();
    await expect(page).toHaveURL(new RegExp(`/evaluate/${DATASET_ID}`), { timeout: 15000 });

    // --- Stage 6: Model evaluation ---
    const evalContinue = page.getByTestId('continue-button');
    await expect(evalContinue).toBeEnabled({ timeout: 15000 });
    await evalContinue.click();
    await expect(page).toHaveURL(new RegExp(`/predict/${DATASET_ID}`), { timeout: 15000 });

    // --- Stage 7: Prediction ---
    await page.locator('#field-feature_a').fill('1');
    await page.locator('#field-feature_b').fill('2');
    await page.getByTestId('make-prediction').click();
    await expect(page.getByTestId('prediction-result')).toBeVisible({ timeout: 15000 });
    const predictContinue = page.getByTestId('continue-button');
    await expect(predictContinue).toBeEnabled({ timeout: 15000 });
    await predictContinue.click();

    // --- Stage 8: Deployment reached ---
    await expect(page).toHaveURL(/\/deploy$/, { timeout: 15000 });
  });
});
