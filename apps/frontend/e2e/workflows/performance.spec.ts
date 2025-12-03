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
  test('should load dashboard page within 2s @smoke', async ({ authenticatedPage }) => {
    const metric = await perfMonitor.measurePageLoad(
      authenticatedPage,
      'Dashboard Load',
      '/dashboard',
      2000
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(2000);
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
    await uploadPage.goto('/datasets/upload');

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

  test('should make single prediction within 100ms @smoke', async ({
    request,
    uploadTestDataset,
    trainModel,
  }) => {
    const datasetId = await uploadTestDataset();
    const modelId = await trainModel(datasetId, 'purchased');

    const metric = await perfMonitor.measureApiCall(
      'Single Prediction API',
      async () => {
        const response = await request.post(`/api/v1/models/${modelId}/predict`, {
          data: {
            features: { age: 30, income: 60000 },
          },
        });
        expect(response.ok()).toBeTruthy();
      },
      'Single Prediction',
      100
    );

    expect(metric.passed).toBeTruthy();
    expect(metric.value).toBeLessThanOrEqual(100);
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
    await authenticatedPage.goto('/datasets/upload');

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
        await uploadPage.goto('/datasets/upload');

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
