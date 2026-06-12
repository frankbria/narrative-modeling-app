import { modelService, ModelService } from '@/lib/services/model';
import type {
  ModelEvaluationResponse,
  ModelComparisonResponse,
} from '@/lib/types/evaluation';

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('svc-token'),
}));

const evaluationFixture: ModelEvaluationResponse = {
  model_id: 'm1',
  model_name: 'Churn Model',
  algorithm: 'random_forest',
  problem_type: 'binary_classification',
  partial: false,
  metrics: {
    accuracy: 0.91,
    precision_macro: 0.9,
    precision_weighted: 0.91,
    recall_macro: 0.89,
    recall_weighted: 0.91,
    f1_macro: 0.9,
    f1_weighted: 0.91,
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
    curves: { yes: [{ x: 0, y: 1 }, { x: 1, y: 0.4 }] },
    baseline_per_class: { yes: 0.42 },
  },
  feature_importance: { age: 0.6, income: 0.4 },
  ai_explanation: {
    overall_assessment: 'Strong model.',
    metric_explanations: { accuracy: '91% of predictions correct.' },
    strengths: ['High accuracy'],
    concerns: ['Some class imbalance'],
    recommendations: ['Collect more data'],
    generated_by: 'openai',
  },
  evaluated_at: '2026-06-11T00:00:00Z',
};

const comparisonFixture: ModelComparisonResponse = {
  problem_type: 'binary_classification',
  dataset_id: 'ds-1',
  models: [
    {
      model_id: 'm1',
      name: 'Model 1',
      algorithm: 'random_forest',
      problem_type: 'binary_classification',
      cv_score: 0.9,
      test_score: 0.91,
      metrics: { accuracy: 0.91, f1: 0.9 },
      created_at: '2026-06-10T00:00:00Z',
    },
    {
      model_id: 'm2',
      name: 'Model 2',
      algorithm: 'logistic_regression',
      problem_type: 'binary_classification',
      cv_score: 0.85,
      test_score: 0.86,
      metrics: { accuracy: 0.86, f1: 0.84 },
      created_at: '2026-06-09T00:00:00Z',
    },
  ],
};

describe('ModelService.getEvaluation', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock) = jest.fn();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('GETs the evaluation endpoint with the bearer token and returns the payload', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(evaluationFixture),
    });

    const result = await ModelService.getEvaluation('m1', 'tok-123');

    expect(result).toEqual(evaluationFixture);
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/ml/m1/evaluation');
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer tok-123');
  });

  it('throws the backend detail message on a non-OK response', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      json: jest.fn().mockResolvedValue({ detail: 'Model not found' }),
    });

    await expect(ModelService.getEvaluation('missing', 'tok')).rejects.toThrow(
      'Model not found'
    );
  });

  it('falls back to a generic message when the error body is not JSON', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      json: jest.fn().mockRejectedValue(new Error('not json')),
    });

    await expect(ModelService.getEvaluation('m1', 'tok')).rejects.toThrow(
      'Failed to fetch model evaluation'
    );
  });

  it('propagates network errors', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('network down'));

    await expect(ModelService.getEvaluation('m1', 'tok')).rejects.toThrow(
      'network down'
    );
  });
});

describe('ModelService.compareModels', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock) = jest.fn();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('POSTs the model ids and returns the comparison payload', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(comparisonFixture),
    });

    const result = await ModelService.compareModels(['m1', 'm2'], 'tok-123');

    expect(result).toEqual(comparisonFixture);
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/ml/compare');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual({ model_ids: ['m1', 'm2'] });
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer tok-123');
  });

  it('throws the backend detail message on a non-OK response', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      json: jest.fn().mockResolvedValue({ detail: 'Models span multiple datasets' }),
    });

    await expect(ModelService.compareModels(['m1', 'm2'], 'tok')).rejects.toThrow(
      'Models span multiple datasets'
    );
  });

  it('falls back to a generic message when the error body is not JSON', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      json: jest.fn().mockRejectedValue(new Error('not json')),
    });

    await expect(ModelService.compareModels(['m1'], 'tok')).rejects.toThrow(
      'Failed to compare models'
    );
  });

  it('propagates network errors', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('network down'));

    await expect(ModelService.compareModels(['m1'], 'tok')).rejects.toThrow(
      'network down'
    );
  });
});

describe('modelService instance wrappers', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock) = jest.fn();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('getEvaluation() resolves the auth token automatically', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(evaluationFixture),
    });

    const result = await modelService.getEvaluation('m1');

    expect(result).toEqual(evaluationFixture);
    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer svc-token');
  });

  it('compareModels() resolves the auth token automatically', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(comparisonFixture),
    });

    const result = await modelService.compareModels(['m1', 'm2']);

    expect(result).toEqual(comparisonFixture);
    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer svc-token');
  });
});
