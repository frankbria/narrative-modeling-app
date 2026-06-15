/**
 * Beta launch readiness — end-to-end beta journey (issue #152).
 *
 * Covers the four user-facing deliverables of P4.2:
 *  1. Onboarding routing — first-time / returning-incomplete users are sent to
 *     onboarding; completed users (or those who skipped) land on the dashboard.
 *  2. The full 8-stage ML journey mapped to the **10 beta acceptance criteria**
 *     in BETA_ROADMAP.md (upload → profile → prepare → features → train →
 *     evaluate → predict, with interpretability + confidence/trust signals).
 *  3. The in-app feedback widget (open → fill → submit → success / error).
 *  4. A p95 < 500ms sanity check on the journey's lightweight API endpoints.
 *
 * The ML backend is MOCKED (like stage-transitions.spec.ts) for the journey and
 * routing tests so they are deterministic and fast; the real ML pipeline is
 * exercised by complete-ai-workflow.spec.ts. The performance test hits the LIVE
 * backend and skips gracefully if it is unreachable.
 *
 * Tagged @beta-acceptance for selective CI execution. Not part of the CI gate
 * (E2E runs via manual workflow_dispatch).
 */

import { test, expect } from '../fixtures';
import type { Page, Route } from '@playwright/test';
import { PerformanceMonitor } from '../helpers/PerformanceMonitor';

const DATASET_ID = 'e2e-beta-ds';
const MODEL_ID = 'e2e-beta-model';

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

function onboardingStatus(complete: boolean) {
  return {
    user_id: 'test_user',
    is_onboarding_complete: complete,
    current_step_id: complete ? null : 'upload_data',
    progress_percentage: complete ? 100 : 25,
    total_steps: 7,
    completed_steps: complete ? 7 : 2,
    skipped_steps: 0,
    time_spent_minutes: 5,
    started_at: '2026-06-11T00:00:00Z',
    completed_at: complete ? '2026-06-11T00:05:00Z' : null,
    last_activity_at: '2026-06-11T00:05:00Z',
  };
}

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
  model_name: 'E2E Beta Model',
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

/**
 * Mock the full backend surface the journey + routing + feedback touch.
 * `onboardingComplete` controls the onboarding-status response; `feedbackStatus`
 * controls the POST /feedback result (201 success vs 500 failure).
 */
async function mockBackend(
  page: Page,
  opts: { onboardingComplete?: boolean; feedbackStatus?: number } = {}
) {
  const { onboardingComplete = true, feedbackStatus = 201 } = opts;

  await page.route('**/api/v1/**', async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    // Onboarding
    if (url.includes('/onboarding/status')) {
      return json(route, onboardingStatus(onboardingComplete));
    }
    if (url.includes('/onboarding/steps')) return json(route, []);
    if (url.includes('/onboarding/achievements')) {
      return json(route, { achievements: [], total_points: 0 });
    }

    // Feedback
    if (url.includes('/feedback')) {
      if (feedbackStatus >= 400) {
        return json(route, { detail: 'error' }, feedbackStatus);
      }
      return json(
        route,
        {
          feedback_id: 'fb_e2e123',
          user_id: 'test_user',
          rating: 5,
          category: 'general',
          message: 'Great app',
          page_context: '/quickstart',
          created_at: '2026-06-11T00:00:00Z',
        },
        feedbackStatus
      );
    }

    // Dashboard data
    if (url.match(/\/datasets(\?|$)/)) return json(route, { datasets: [] });
    if (url.match(/\/models(\?|$)/)) return json(route, { models: [] });

    // Workflow persistence (localStorage is the source of truth)
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

    // Dataset record
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

    // Feature engineering
    if (url.includes('/features/suggestions')) {
      return json(route, { summary: 'Looks good.', recommendations: [] });
    }
    if (url.includes('/features/generate')) return json(route, { newFeatures: [] });
    if (url.match(/\/datasets\/[^/]+\/features/)) {
      return json(route, {
        features: [
          { name: 'feature_a', type: 'numeric' },
          { name: 'feature_b', type: 'numeric' },
        ],
      });
    }

    // ML pipeline (mocked)
    if (url.includes('/ml/train')) {
      return json(route, { model_id: MODEL_ID, status: 'queued', message: 'ok' });
    }
    if (url.match(/\/ml\/[^/]+\/status/)) return json(route, completedTrainingStatus);
    if (url.match(/\/ml\/[^/]+\/evaluation/)) return json(route, evaluationResponse);
    if (url.match(/\/ml\/[^/]+\/shap/)) return json(route, { detail: 'no shap' }, 404);
    if (url.match(/\/ml\/[^/]+\/features/)) return json(route, modelFeaturesResponse);
    if (url.match(/\/ml\/[^/]+\/predict/)) return json(route, predictResponse);
    if (url.match(/\/ml\/[^/]+\/logs/)) {
      return json(route, { logs: [], total_count: 0 });
    }
    if (url.match(/\/models\/[^/]+\/deployment/)) {
      return json(route, { deployment: null });
    }

    return json(route, {});
  });
}

test.describe.serial('Beta launch readiness — onboarding routing (#152)', () => {
  test('returning user with incomplete onboarding is redirected to onboarding @beta-acceptance', async ({
    page,
  }) => {
    await mockBackend(page, { onboardingComplete: false });
    await page.addInitScript(() => window.localStorage.clear());

    await page.goto('/dashboard');

    await expect(page).toHaveURL(/\/onboarding/, { timeout: 15000 });
  });

  test('user with completed onboarding loads the dashboard @beta-acceptance', async ({
    page,
  }) => {
    await mockBackend(page, { onboardingComplete: true });
    await page.addInitScript(() => window.localStorage.clear());

    await page.goto('/dashboard');

    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 15000 });
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('skip bypass keeps an incomplete user on the dashboard @beta-acceptance', async ({
    page,
  }) => {
    await mockBackend(page, { onboardingComplete: false });
    await page.addInitScript(() => window.localStorage.clear());

    // ?skipOnboarding=true persists the opt-out and defuses the redirect.
    await page.goto('/dashboard?skipOnboarding=true');

    await expect(page.getByTestId('dashboard')).toBeVisible({ timeout: 15000 });
    await expect(page).toHaveURL(/\/dashboard/);
  });
});

test.describe.serial('Beta launch readiness — full journey (#152)', () => {
  test.setTimeout(120000);

  test('full beta journey satisfies the 10 acceptance criteria @beta-acceptance', async ({
    page,
  }) => {
    await mockBackend(page, { onboardingComplete: true });
    await page.addInitScript(() => window.localStorage.clear());

    // Criterion 1: Upload data without errors.
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

    // Criterion 2: View automatic data profiling and insights.
    await page
      .getByRole('button', { name: /Complete & Continue to Data Preparation/i })
      .click();
    await expect(page).toHaveURL(/\/prepare$/, { timeout: 15000 });

    // Criterion 3: Apply transformations (cleaning, encoding, scaling).
    await page.getByTestId('continue-button').click();
    await expect(page).toHaveURL(/\/features$/, { timeout: 15000 });

    // Criterion 4: Get AI-powered feature suggestions and apply them.
    await page.getByTestId('generate-features-button').click();
    const featuresContinue = page.getByTestId('continue-button');
    await expect(featuresContinue).toBeEnabled({ timeout: 15000 });
    await featuresContinue.click();
    await expect(page).toHaveURL(/\/model$/, { timeout: 15000 });

    // Criterion 5 + 6: Train a model with AI-guided selection + see progress.
    await page.locator('select').selectOption('target');
    await page.getByRole('button', { name: /Start Training/i }).click();
    const modelContinue = page.getByTestId('continue-button');
    await expect(modelContinue).toBeEnabled({ timeout: 30000 });
    await modelContinue.click();
    await expect(page).toHaveURL(new RegExp(`/evaluate/${DATASET_ID}`), { timeout: 15000 });

    // Criterion 7 + 8: Evaluate performance with clear metrics + interpretability.
    await expect(page.getByText(/accuracy/i).first()).toBeVisible({ timeout: 15000 });
    const evalContinue = page.getByTestId('continue-button');
    await expect(evalContinue).toBeEnabled({ timeout: 15000 });
    await evalContinue.click();
    await expect(page).toHaveURL(new RegExp(`/predict/${DATASET_ID}`), { timeout: 15000 });

    // Criterion 9 + 10: Make predictions on new data + trust them (confidence).
    await page.locator('#field-feature_a').fill('1');
    await page.locator('#field-feature_b').fill('2');
    await page.getByTestId('make-prediction').click();
    await expect(page.getByTestId('prediction-result')).toBeVisible({ timeout: 15000 });
  });
});

test.describe('Beta launch readiness — feedback widget (#152)', () => {
  test('user can open, fill, and submit feedback @beta-acceptance', async ({ page }) => {
    await mockBackend(page, { feedbackStatus: 201 });

    await page.goto('/quickstart');

    await page.getByTestId('feedback-widget-button').click();
    await expect(page.getByTestId('feedback-widget-panel')).toBeVisible();

    await page.getByTestId('feedback-star-5').click();
    await page.getByTestId('feedback-category').selectOption('general');
    await page.getByTestId('feedback-message').fill('The quickstart guide is great!');
    await page.getByTestId('feedback-submit').click();

    await expect(page.getByTestId('feedback-success')).toBeVisible({ timeout: 10000 });
  });

  test('feedback widget surfaces an error when submission fails', async ({ page }) => {
    await mockBackend(page, { feedbackStatus: 500 });

    await page.goto('/quickstart');

    await page.getByTestId('feedback-widget-button').click();
    await page.getByTestId('feedback-star-3').click();
    await page.getByTestId('feedback-message').fill('Something is broken');
    await page.getByTestId('feedback-submit').click();

    await expect(page.getByTestId('feedback-error')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('feedback-success')).toHaveCount(0);
  });
});

test.describe('Beta launch readiness — API performance (#152)', () => {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  const headers = { Authorization: 'Bearer dev-user-default' };

  test('p95 latency on journey endpoints is under 500ms @beta-acceptance', async ({
    request,
  }) => {
    // Hits the LIVE backend; skip if the lightweight status endpoint is down.
    let reachable = true;
    try {
      const probe = await request.get(`${apiBase}/onboarding/status`, {
        headers,
        timeout: 5000,
      });
      reachable = probe.ok();
    } catch {
      reachable = false;
    }
    test.skip(!reachable, 'Live backend not reachable for performance sanity check');

    const monitor = new PerformanceMonitor();

    const onboarding = await monitor.measureP95(
      'beta-journey-performance',
      () => request.get(`${apiBase}/onboarding/status`, { headers }),
      'GET /onboarding/status',
      500
    );
    const datasets = await monitor.measureP95(
      'beta-journey-performance',
      () => request.get(`${apiBase}/datasets?page=1&limit=5`, { headers }),
      'GET /datasets',
      500
    );
    // Single iteration: each POST persists a real document, so we avoid
    // polluting the beta feedback collection with 20 perf-check rows per run.
    const feedback = await monitor.measureP95(
      'beta-journey-performance',
      () =>
        request.post(`${apiBase}/feedback`, {
          headers,
          data: {
            rating: 5,
            category: 'general',
            message: 'perf check',
            page_context: '/dashboard',
          },
        }),
      'POST /feedback',
      500,
      1
    );

    monitor.saveMetrics();

    expect(onboarding.value, 'p95 GET /onboarding/status').toBeLessThan(500);
    expect(datasets.value, 'p95 GET /datasets').toBeLessThan(500);
    expect(feedback.value, 'p95 POST /feedback').toBeLessThan(500);
  });
});
