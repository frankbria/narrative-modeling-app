import { modelService, ModelService } from '@/lib/services/model';

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('svc-token'),
}));

describe('modelService instance export', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock) = jest.fn();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // Regression: app/experiments/new imports { modelService } but the module
  // previously only exported the ModelService class. Verify the instance exists
  // and exposes the methods the pages call without an explicit token argument.
  it('exposes a modelService instance distinct from the class', () => {
    expect(modelService).toBeDefined();
    expect(typeof modelService.listModels).toBe('function');
    expect(modelService).not.toBe(ModelService);
  });

  it('listModels() resolves the auth token automatically and returns data', async () => {
    const models = [{ model_id: 'm1', name: 'Model 1', is_active: true }];
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(models),
    });

    const result = await modelService.listModels();

    expect(result).toEqual(models);
    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer svc-token');
  });

  it('listModels(datasetId) forwards the dataset_id filter', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue([]),
    });

    await modelService.listModels('ds-99');

    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain('/ml/?');
    expect(url).toContain('dataset_id=ds-99');
  });

  it('getModel() resolves the token and requests the model detail endpoint', async () => {
    const model = { model_id: 'm7', name: 'Detail', is_active: true };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(model),
    });

    const result = await modelService.getModel('m7');

    expect(result).toEqual(model);
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/ml/m7');
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer svc-token');
  });

  it('trainModel() POSTs the request body with the resolved token', async () => {
    const response = { model_id: 'm1', status: 'started', message: 'ok' };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(response),
    });

    const request = { dataset_id: 'ds-1', target_column: 'y' };
    const result = await modelService.trainModel(request);

    expect(result).toEqual(response);
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/ml/train');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual(request);
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer svc-token');
  });

  it('predict() POSTs to the model predict endpoint and returns predictions', async () => {
    const response = {
      predictions: [1, 0],
      feature_names: ['a'],
      model_info: { model_id: 'm3', algorithm: 'rf', problem_type: 'classification', target_column: 'y' },
    };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(response),
    });

    const request = { data: [{ a: 1 }] };
    const result = await modelService.predict('m3', request);

    expect(result).toEqual(response);
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/ml/m3/predict');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual(request);
  });

  it('deleteModel() issues a DELETE with the resolved token', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

    await modelService.deleteModel('m4');

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/ml/m4');
    expect(init?.method).toBe('DELETE');
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer svc-token');
  });

  it('deactivateModel() issues a PUT to the deactivate endpoint', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

    await modelService.deactivateModel('m5');

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/ml/m5/deactivate');
    expect(init?.method).toBe('PUT');
  });

  it('predict() throws the backend detail message when the response is not ok', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      json: jest.fn().mockResolvedValue({ detail: 'bad input' }),
    });

    await expect(modelService.predict('m6', { data: [] })).rejects.toThrow('bad input');
  });

  it('getTrainingStatus() requests the status endpoint and returns the job state', async () => {
    const status = {
      model_id: 'm8',
      status: 'running',
      progress: 0.5,
      current_algorithm: 'XGBoost',
      completed_algorithms: 1,
      total_algorithms: 2,
      metrics: {},
      model_comparison: [],
      algorithm_recommendations: [],
    };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(status),
    });

    const result = await modelService.getTrainingStatus('m8');

    expect(result).toEqual(status);
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/ml/m8/status');
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer svc-token');
  });

  it('getTrainingStatus() throws the backend detail message on error', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      json: jest.fn().mockResolvedValue({ detail: 'Training job not found' }),
    });

    await expect(modelService.getTrainingStatus('missing')).rejects.toThrow(
      'Training job not found'
    );
  });

  describe('listTrainingJobs()', () => {
    const jobList = {
      jobs: [
        {
          model_id: 'm1',
          dataset_id: 'ds-1',
          target_column: 'y',
          status: 'running',
          progress_percentage: 42.5,
          current_stage: 'training',
          created_at: '2026-06-10T10:00:00Z',
          started_at: '2026-06-10T10:00:05Z',
          completed_at: null,
          best_algorithm: null,
          best_score: null,
          elapsed_seconds: 95.2,
        },
      ],
      total_count: 1,
      limit: 20,
      skip: 0,
    };

    it('requests the jobs endpoint with the resolved token and returns the list', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(jobList),
      });

      const result = await modelService.listTrainingJobs();

      expect(result).toEqual(jobList);
      const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/ml/jobs');
      const headers = (init?.headers ?? {}) as Record<string, string>;
      expect(headers.Authorization).toBe('Bearer svc-token');
    });

    it('forwards status, limit and skip as query parameters', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ ...jobList, jobs: [] }),
      });

      await modelService.listTrainingJobs({ status: 'running', limit: 5, skip: 10 });

      const [url] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toContain('/ml/jobs?');
      expect(url).toContain('status=running');
      expect(url).toContain('limit=5');
      expect(url).toContain('skip=10');
    });

    it('throws the backend detail message on error', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: jest.fn().mockResolvedValue({ detail: 'boom' }),
      });

      await expect(modelService.listTrainingJobs()).rejects.toThrow('boom');
    });
  });

  describe('getTrainingLogs()', () => {
    const logsResponse = {
      model_id: 'm9',
      logs: [
        {
          timestamp: '2026-06-10T10:00:00Z',
          level: 'info',
          message: 'Training started',
          stage: 'preprocessing',
        },
      ],
      total_count: 1,
      has_more: false,
    };

    it('requests the logs endpoint with the resolved token and returns the logs', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(logsResponse),
      });

      const result = await modelService.getTrainingLogs('m9');

      expect(result).toEqual(logsResponse);
      const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/ml/m9/logs');
      const headers = (init?.headers ?? {}) as Record<string, string>;
      expect(headers.Authorization).toBe('Bearer svc-token');
    });

    it('forwards level, limit and skip as query parameters', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(logsResponse),
      });

      await modelService.getTrainingLogs('m9', { level: 'error', limit: 50, skip: 100 });

      const [url] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toContain('/ml/m9/logs?');
      expect(url).toContain('level=error');
      expect(url).toContain('limit=50');
      expect(url).toContain('skip=100');
    });

    it('throws the backend detail message when the job is not found', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: jest.fn().mockResolvedValue({ detail: 'Training job not found' }),
      });

      await expect(modelService.getTrainingLogs('missing')).rejects.toThrow(
        'Training job not found'
      );
    });
  });

  describe('cancelTraining()', () => {
    it('POSTs to the cancel endpoint and returns the cancellation response', async () => {
      const response = {
        model_id: 'm10',
        status: 'running',
        cancellation_requested: true,
        message: 'Cancellation requested',
      };
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(response),
      });

      const result = await modelService.cancelTraining('m10');

      expect(result).toEqual(response);
      const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/ml/m10/cancel');
      expect(init?.method).toBe('POST');
      const headers = (init?.headers ?? {}) as Record<string, string>;
      expect(headers.Authorization).toBe('Bearer svc-token');
    });

    it('throws the backend detail message on a 409 terminal-job conflict', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 409,
        json: jest.fn().mockResolvedValue({
          detail: 'Training job already completed',
        }),
      });

      await expect(modelService.cancelTraining('m10')).rejects.toThrow(
        'Training job already completed'
      );
    });
  });
});
