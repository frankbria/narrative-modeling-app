/**
 * AI Recommendations E2E Tests
 *
 * Tests AI-powered recommendation features including:
 * - Problem type detection (binary, multiclass, regression, time series, clustering)
 * - Transformation recommendations (encoding, scaling, imputation, feature engineering)
 * - Algorithm recommendations with reasoning
 * - Recommendation validation and application
 *
 * Coverage Target: >85%
 * Test Count: 15 tests
 */

import { test, expect } from '../fixtures';
import { UploadPage } from '../pages/UploadPage';
import { join } from 'path';

test.describe('AI Recommendations - Problem Type Detection', () => {
  test('should detect binary classification problem type @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000); // 2 minute timeout for AI

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    // Upload binary classification dataset
    const csvPath = join(__dirname, '../test-data/binary-classification.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    // Call AI analysis endpoint
    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    expect(response.ok()).toBeTruthy();
    const analysis = await response.json();

    // Verify problem type detection
    expect(analysis.problem_type).toBe('binary_classification');
    expect(analysis.confidence).toBeGreaterThan(0.85);
    expect(analysis.reasoning).toBeTruthy();
  });

  test('should detect multiclass classification problem type @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/multiclass-classification.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    expect(response.ok()).toBeTruthy();
    const analysis = await response.json();

    expect(analysis.problem_type).toBe('multiclass_classification');
    expect(analysis.confidence).toBeGreaterThan(0.85);
  });

  test('should detect regression problem type @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/regression.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    expect(response.ok()).toBeTruthy();
    const analysis = await response.json();

    expect(analysis.problem_type).toBe('regression');
    expect(analysis.confidence).toBeGreaterThan(0.85);
  });

  test('should detect time series problem type @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/time-series.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    expect(response.ok()).toBeTruthy();
    const analysis = await response.json();

    expect(analysis.problem_type).toBe('time_series');
    expect(analysis.confidence).toBeGreaterThan(0.85);
  });

  test('should detect unsupervised clustering problem type @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/clustering.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    expect(response.ok()).toBeTruthy();
    const analysis = await response.json();

    expect(analysis.problem_type).toBe('unsupervised_clustering');
    expect(analysis.confidence).toBeGreaterThan(0.75);
  });
});

test.describe('AI Recommendations - Transformation Suggestions', () => {
  test('should recommend appropriate encoding methods @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/binary-classification.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await response.json();
    const encodingRecs = analysis.recommendations?.encoding || [];

    expect(encodingRecs.length).toBeGreaterThan(0);
    expect(encodingRecs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          method: expect.stringMatching(/one-hot|label|target/i),
          reasoning: expect.any(String),
        }),
      ])
    );
  });

  test('should recommend appropriate scaling methods @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/regression.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await response.json();
    const scalingRecs = analysis.recommendations?.scaling || [];

    expect(scalingRecs.length).toBeGreaterThan(0);
    expect(scalingRecs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          method: expect.stringMatching(/StandardScaler|MinMaxScaler|RobustScaler/i),
          reasoning: expect.any(String),
        }),
      ])
    );
  });

  test('should recommend appropriate imputation methods @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/binary-classification.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await response.json();
    const imputationRecs = analysis.recommendations?.imputation || [];

    // Imputation recommendations only if missing values detected
    if (analysis.missing_values_detected) {
      expect(imputationRecs.length).toBeGreaterThan(0);
      expect(imputationRecs).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: expect.stringMatching(/mean|median|mode|KNN/i),
            reasoning: expect.any(String),
          }),
        ])
      );
    }
  });

  test('should recommend feature engineering techniques @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/regression.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await response.json();
    const featureEngRecs = analysis.recommendations?.feature_engineering || [];

    expect(featureEngRecs.length).toBeGreaterThan(0);
    expect(featureEngRecs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          technique: expect.stringMatching(/polynomial|interaction|date|aggregation/i),
          reasoning: expect.any(String),
        }),
      ])
    );
  });

  test('should recommend outlier detection methods @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/regression.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await response.json();
    const outlierRecs = analysis.recommendations?.outlier_detection || [];

    if (analysis.outliers_detected) {
      expect(outlierRecs.length).toBeGreaterThan(0);
      expect(outlierRecs).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: expect.stringMatching(/IQR|z-score|isolation forest/i),
            reasoning: expect.any(String),
          }),
        ])
      );
    }
  });
});

test.describe('AI Recommendations - Algorithm Suggestions', () => {
  test('should recommend classification algorithms with ranking @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/binary-classification.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await response.json();
    const algorithmRecs = analysis.recommendations?.algorithms || [];

    expect(algorithmRecs.length).toBeGreaterThan(0);
    expect(algorithmRecs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: expect.stringMatching(/Random Forest|Gradient Boosting|Logistic Regression/i),
          rank: expect.any(Number),
          reasoning: expect.any(String),
        }),
      ])
    );

    // Verify ranking order (lower rank = better)
    const randomForest = algorithmRecs.find((a: any) => a.name.includes('Random Forest'));
    const logisticReg = algorithmRecs.find((a: any) => a.name.includes('Logistic'));

    if (randomForest && logisticReg) {
      expect(randomForest.rank).toBeLessThanOrEqual(logisticReg.rank);
    }
  });

  test('should recommend regression algorithms with ranking @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/regression.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await response.json();
    const algorithmRecs = analysis.recommendations?.algorithms || [];

    expect(algorithmRecs.length).toBeGreaterThan(0);
    expect(algorithmRecs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: expect.stringMatching(/Random Forest|Gradient Boosting|Linear Regression/i),
          rank: expect.any(Number),
          reasoning: expect.any(String),
        }),
      ])
    );
  });

  test('should warn about complex models for small datasets @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    // Use small dataset (sample.csv has only 5 rows)
    const csvPath = join(__dirname, '../test-data/sample.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    const response = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await response.json();
    const warnings = analysis.warnings || [];

    expect(warnings).toEqual(
      expect.arrayContaining([
        expect.stringMatching(/small dataset|limited data|sample size/i),
      ])
    );

    // Should recommend simpler models
    const algorithmRecs = analysis.recommendations?.algorithms || [];
    const simpleModels = algorithmRecs.filter((a: any) =>
      a.name.match(/Logistic Regression|Linear Regression|Decision Tree/i)
    );

    expect(simpleModels.length).toBeGreaterThan(0);
  });
});

test.describe('AI Recommendations - Validation and Application', () => {
  test('should apply recommended transformation and verify quality improvement @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/binary-classification.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    // Get AI recommendations
    const analysisResponse = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await analysisResponse.json();
    const scalingRec = analysis.recommendations?.scaling?.[0];

    if (scalingRec) {
      // Apply recommended scaling transformation
      const transformResponse = await request.post('/api/v1/transformations/apply', {
        data: {
          dataset_id: datasetId,
          transformation_type: 'scaling',
          method: scalingRec.method,
        },
      });

      expect(transformResponse.ok()).toBeTruthy();
      const transformResult = await transformResponse.json();

      // Verify transformation improved data quality
      expect(transformResult.quality_metrics).toBeDefined();
      expect(transformResult.quality_metrics.normalized).toBe(true);
    }
  });

  test('should train with recommended algorithm and verify performance @ai-integration', async ({
    authenticatedPage,
    request,
  }) => {
    test.setTimeout(120000);

    const uploadPage = new UploadPage(authenticatedPage);
    await uploadPage.goto('/datasets/upload');

    const csvPath = join(__dirname, '../test-data/binary-classification.csv');
    await uploadPage.uploadFile(csvPath);
    await uploadPage.waitForUploadComplete();

    const datasetId = await uploadPage.getDatasetId();

    // Get AI recommendations
    const analysisResponse = await request.post('/api/v1/ai/analyze-dataset', {
      data: { dataset_id: datasetId },
      timeout: 120000,
    });

    const analysis = await analysisResponse.json();
    const topAlgorithm = analysis.recommendations?.algorithms?.[0];

    if (topAlgorithm) {
      // Train model with recommended algorithm
      const trainResponse = await request.post('/api/v1/models/train', {
        data: {
          dataset_id: datasetId,
          target_column: 'purchased',
          algorithm: topAlgorithm.name.toLowerCase().replace(/\s+/g, '_'),
        },
        timeout: 60000,
      });

      expect(trainResponse.ok()).toBeTruthy();
      const trainResult = await trainResponse.json();

      // Verify model performance meets baseline
      expect(trainResult.metrics).toBeDefined();
      expect(trainResult.metrics.accuracy || trainResult.metrics.r2_score).toBeGreaterThan(0.5);
    }
  });
});
