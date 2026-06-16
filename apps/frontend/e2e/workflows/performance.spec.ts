/**
 * Performance E2E Tests
 *
 * Tests performance benchmarks including:
 * - Page load performance (TTI)
 * - API response times
 * - Database query performance
 * - Frontend rendering performance
 * - Concurrent load handling
 *
 * Coverage Target: >85%
 * Test Count: 20 tests
 */

import { test, expect } from '../fixtures';
import { PerformanceMonitor } from '../helpers';
import { UploadPage } from '../pages/UploadPage';
import { join } from 'path';

let perfMonitor: PerformanceMonitor;

test.beforeEach(() => {
  perfMonitor = new PerformanceMonitor();
});

test.afterEach(() => {
  perfMonitor.saveMetrics();
});

test.describe('Performance - Page Load', () => {
  // #157: moved out of the blocking @smoke gate into the non-blocking @perf job.
  // Wall-clock TTI on shared 2-core CI runners flaked a 2s threshold across
  // identical runs; 5000ms is a realistic TTI ceiling for a contended 2-core
  // runner (a "did not hang" guardrail, not a tuned target). The @perf job runs
  // continue-on-error, so a breach records a number without failing the PR.
  test('should load dashboard page within 5s @perf', async ({ authenticatedPage }) => {
    const DASHBOARD_LOAD_CEILING_MS = 5000;
    const metric = await perfMonitor.measurePageLoad(
      authenticatedPage,
      'Dashboard Load',
      '/dashboard',
      DASHBOARD_LOAD_CEILING_MS
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(DASHBOARD_LOAD_CEILING_MS);
  });

  test('should load dataset list page (50 datasets) within 3s', async ({
    authenticatedPage,
  }) => {
    const metric = await perfMonitor.measurePageLoad(
      authenticatedPage,
      'Dataset List Load',
      '/datasets',
      3000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(3000);
  });

  test('should load dataset detail page (10k rows) within 4s', async ({
    authenticatedPage,
    uploadTestDataset,
  }) => {
    // Upload dataset first
    const datasetId = await uploadTestDataset();

    const metric = await perfMonitor.measurePageLoad(
      authenticatedPage,
      'Dataset Detail Load',
      `/datasets/${datasetId}`,
      4000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(4000);
  });

  test('should load model training page within 2s', async ({ authenticatedPage }) => {
    const metric = await perfMonitor.measurePageLoad(
      authenticatedPage,
      'Model Training Page Load',
      '/models/train',
      2000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(2000);
  });

  test('should load prediction page within 2s', async ({ authenticatedPage }) => {
    const metric = await perfMonitor.measurePageLoad(
      authenticatedPage,
      'Prediction Page Load',
      '/predictions',
      2000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(2000);
  });
});

test.describe('Performance - API Response Times', () => {
  test('should upload 5MB dataset within 5s', async ({ authenticatedPage }) => {
    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/upload');

    const csvPath = join(__dirname, '../test-data/sample.csv');

    const metric = await perfMonitor.measureApiCall(
      'Dataset Upload API',
      async () => {
        await uploadPage.uploadFile(csvPath);
        await uploadPage.waitForUploadComplete();
      },
      'Dataset Upload (5MB)',
      5000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(5000);
  });

  test('should preview transformation (1000 rows) within 3s', async ({
    authenticatedPage,
    request,
    uploadTestDataset,
  }) => {
    const datasetId = await uploadTestDataset();

    const metric = await perfMonitor.measureApiCall(
      'Transformation Preview API',
      async () => {
        const response = await request.post('/api/v1/transformations/preview', {
          data: {
            dataset_id: datasetId,
            transformation_type: 'scaling',
            method: 'StandardScaler',
          },
        });
        expect(response.ok()).toBeTruthy();
      },
      'Transformation Preview (1000 rows)',
      3000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(3000);
  });

  test('should complete model training (500 rows) within 30s', async ({
    request,
    uploadTestDataset,
  }) => {
    const datasetId = await uploadTestDataset();

    const metric = await perfMonitor.measureApiCall(
      'Model Training API',
      async () => {
        const response = await request.post('/api/v1/models/train', {
          data: {
            dataset_id: datasetId,
            target_column: 'purchased',
            algorithm: 'random_forest',
          },
          timeout: 30000,
        });
        expect(response.ok()).toBeTruthy();
      },
      'Model Training (500 rows)',
      30000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(30000);
  });

  // #157: this is a latency measurement, so it moved out of the blocking @smoke
  // gate into the non-blocking @perf job. Functional "train a real model and get
  // a prediction back" smoke coverage already lives in predict.spec.ts (@smoke),
  // so the blocking gate loses no coverage. The intended single-prediction SLO is
  // 1000ms: generous headroom over the ~180ms prediction call observed locally,
  // accounting for cold model load on a 2-core runner. The @perf job runs
  // continue-on-error, so a breach records a number without failing the PR.
  test('should make a single prediction @perf', async ({
    request,
    uploadTestDataset,
    trainModel,
  }) => {
    // Real AutoML training + a poll for the saved artifact can exceed the
    // default 30s test timeout; the prediction itself is the measured part.
    test.setTimeout(120000);

    // A genuinely trainable dataset (the 6-row sample.csv makes AutoML detect
    // problem type "unknown" and fail). Use the compact 200-row subset (both
    // `churned` classes present) so AutoML training stays light — the full
    // 999-row fit pegs a core long enough to starve the parallel worker and
    // flake other timing-sensitive smoke tests on 2-core CI (see #157).
    const datasetId = await uploadTestDataset('ai-test-datasets/binary-classification-small.csv');
    const modelId = await trainModel(datasetId, 'churned');

    // Direct backend call (Next.js does not proxy /api/v1); SKIP_AUTH backend
    // still requires an Authorization header for HTTPBearer.
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

    const SINGLE_PREDICTION_BUDGET_MS = 1000;
    const metric = await perfMonitor.measureApiCall(
      'Single Prediction API',
      async () => {
        // Real prediction endpoint lives under /api/v1/ml and takes a list of
        // records (PredictRequest.data); the record must carry the training
        // feature columns so the feature engineer can transform it. These keys
        // mirror the non-target columns of binary-classification-small.csv — if
        // that dataset's header changes, update this payload to match.
        const response = await request.post(`${apiBase}/ml/${modelId}/predict`, {
          headers: { Authorization: 'Bearer e2e-test-token' },
          data: {
            data: [
              {
                age: 35,
                tenure: 12,
                monthly_charges: 65.5,
                contract_type: 'Month-to-month',
                has_internet: true,
                has_phone: true,
                payment_method: 'Electronic Check',
                total_charges: 800.0,
                support_calls: 2,
              },
            ],
          },
        });
        expect(response.ok()).toBeTruthy();
        const body = await response.json();
        expect(Array.isArray(body.predictions)).toBeTruthy();
        expect(body.predictions.length).toBe(1);
      },
      'Single Prediction',
      SINGLE_PREDICTION_BUDGET_MS
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(SINGLE_PREDICTION_BUDGET_MS);
  });

  test('should complete batch prediction (100 rows) within 5s', async ({
    request,
    uploadTestDataset,
    trainModel,
  }) => {
    const datasetId = await uploadTestDataset();
    const modelId = await trainModel(datasetId, 'purchased');

    // Create 100 prediction rows
    const batchData = Array.from({ length: 100 }, (_, i) => ({
      age: 25 + i,
      income: 50000 + i * 1000,
    }));

    const metric = await perfMonitor.measureApiCall(
      'Batch Prediction API',
      async () => {
        const response = await request.post(`/api/v1/models/${modelId}/predict-batch`, {
          data: { features: batchData },
          timeout: 5000,
        });
        expect(response.ok()).toBeTruthy();
      },
      'Batch Prediction (100 rows)',
      5000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(5000);
  });

  test('should compare versions (10k rows) within 10s', async ({
    request,
    uploadTestDataset,
  }) => {
    const datasetId = await uploadTestDataset();

    const metric = await perfMonitor.measureApiCall(
      'Version Comparison API',
      async () => {
        const response = await request.post('/api/v1/datasets/compare-versions', {
          data: {
            dataset_id: datasetId,
            version_1: '1.0',
            version_2: '1.1',
          },
          timeout: 10000,
        });
        // May not exist, just measuring if endpoint exists
        if (response.ok()) {
          await response.json();
        }
      },
      'Version Comparison (10k rows)',
      10000
    );

    expect(metric.value).toBeLessThanOrEqual(10000);
  });

  test('should get AI recommendation within 60s @ai-integration', async ({
    request,
    uploadTestDataset,
  }) => {
    const datasetId = await uploadTestDataset();

    const metric = await perfMonitor.measureApiCall(
      'AI Recommendation API',
      async () => {
        const response = await request.post('/api/v1/ai/analyze-dataset', {
          data: { dataset_id: datasetId },
          timeout: 60000,
        });
        expect(response.ok()).toBeTruthy();
      },
      'AI Recommendation',
      60000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(60000);
  });
});

test.describe('Performance - Database Query Performance', () => {
  test('should query dataset list (100 datasets) within 1s', async ({ request }) => {
    const metric = await perfMonitor.measureApiCall(
      'Dataset List Query',
      async () => {
        const response = await request.get('/api/v1/datasets?limit=100');
        expect(response.ok()).toBeTruthy();
      },
      'Dataset List Query (100 datasets)',
      1000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(1000);
  });

  test('should retrieve model metrics within 500ms', async ({
    request,
    uploadTestDataset,
    trainModel,
  }) => {
    const datasetId = await uploadTestDataset();
    const modelId = await trainModel(datasetId, 'purchased');

    const metric = await perfMonitor.measureApiCall(
      'Model Metrics Query',
      async () => {
        const response = await request.get(`/api/v1/models/${modelId}/metrics`);
        expect(response.ok()).toBeTruthy();
      },
      'Model Metrics Retrieval',
      500
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(500);
  });

  test('should fetch version history (20 versions) within 2s', async ({
    request,
    uploadTestDataset,
  }) => {
    const datasetId = await uploadTestDataset();

    const metric = await perfMonitor.measureApiCall(
      'Version History Query',
      async () => {
        const response = await request.get(`/api/v1/datasets/${datasetId}/versions`);
        if (response.ok()) {
          await response.json();
        }
      },
      'Version History (20 versions)',
      2000
    );

    expect(metric.value).toBeLessThanOrEqual(2000);
  });
});

test.describe('Performance - Frontend Rendering', () => {
  test('should render data table (1000 rows × 10 cols) within 1s', async ({
    authenticatedPage,
    uploadTestDataset,
  }) => {
    const datasetId = await uploadTestDataset();
    await authenticatedPage.goto(`/datasets/${datasetId}`);

    const metric = await perfMonitor.measureRenderTime(
      authenticatedPage,
      'Data Table Rendering',
      'table tbody tr',
      'Data Table (1000 rows × 10 cols)',
      1000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(1000);
  });

  test('should render confusion matrix chart within 2s', async ({
    authenticatedPage,
    uploadTestDataset,
    trainModel,
  }) => {
    const datasetId = await uploadTestDataset();
    const modelId = await trainModel(datasetId, 'purchased');

    await authenticatedPage.goto(`/models/${modelId}`);

    const metric = await perfMonitor.measureRenderTime(
      authenticatedPage,
      'Confusion Matrix Chart',
      '[data-testid="confusion-matrix"], canvas, svg',
      'Confusion Matrix Chart',
      2000
    );

    expect(metric.value).toBeLessThanOrEqual(2000);
  });

  test('should render ROC curve chart within 2s', async ({
    authenticatedPage,
    uploadTestDataset,
    trainModel,
  }) => {
    const datasetId = await uploadTestDataset();
    const modelId = await trainModel(datasetId, 'purchased');

    await authenticatedPage.goto(`/models/${modelId}`);

    const metric = await perfMonitor.measureRenderTime(
      authenticatedPage,
      'ROC Curve Chart',
      '[data-testid="roc-curve"], canvas, svg',
      'ROC Curve Chart',
      2000
    );

    expect(metric.value).toBeLessThanOrEqual(2000);
  });

  test('should validate form (20 fields) within 100ms', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/upload');

    const startTime = Date.now();

    // Fill form fields to trigger validation
    const fileInput = authenticatedPage.locator('input[type="file"]');
    if (await fileInput.isVisible({ timeout: 2000 })) {
      await fileInput.evaluate((el) => {
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }

    await authenticatedPage.waitForTimeout(100);

    const validationTime = Date.now() - startTime;

    const metric = perfMonitor.recordMetric(
      'Form Validation',
      'Form Validation (20 fields)',
      validationTime,
      'ms',
      100
    );

    expect(metric.value).toBeLessThanOrEqual(100);
  });
});

test.describe('Performance - Concurrent Load @concurrency', () => {
  test('should handle 5 concurrent uploads within 10s each', async ({ context, request }) => {
    const uploadOperations = Array.from({ length: 5 }, () => async () => {
      const page = await context.newPage();
      const uploadPage = new UploadPage(page);

      try {
        await uploadPage.goto('/upload');

        const csvPath = join(__dirname, '../test-data/sample.csv');
        await uploadPage.uploadFile(csvPath);
        await uploadPage.waitForUploadComplete();
      } finally {
        await page.close();
      }
    });

    const metric = await perfMonitor.measureConcurrentOperations(
      'Concurrent Uploads',
      uploadOperations,
      '5 Concurrent Uploads',
      10000
    );

    // Each upload should be at most 2x slower than single upload (10s vs 5s)
    expect(metric.value).toBeLessThanOrEqual(10000);
  });

  test('should handle 10 concurrent predictions within 200ms average', async ({
    request,
    uploadTestDataset,
    trainModel,
  }) => {
    const datasetId = await uploadTestDataset();
    const modelId = await trainModel(datasetId, 'purchased');

    const predictionOperations = Array.from({ length: 10 }, () => async () => {
      const response = await request.post(`/api/v1/models/${modelId}/predict`, {
        data: {
          features: { age: 30, income: 60000 },
        },
      });
      expect(response.ok()).toBeTruthy();
    });

    const metric = await perfMonitor.measureConcurrentOperations(
      'Concurrent Predictions',
      predictionOperations,
      '10 Concurrent Predictions',
      200
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(200);
  });
});

test.afterAll(() => {
  const summary = perfMonitor.getSummary();
  console.log('\n=== Performance Test Summary ===');
  console.log(`Total Metrics: ${summary.total}`);
  console.log(`Passed: ${summary.passed}`);
  console.log(`Failed: ${summary.failed}`);
  console.log(`Average Value: ${summary.avgValue}ms`);
  console.log('================================\n');
});
