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

  it('getErrorAnalysis() resolves the token and requests the errors endpoint', async () => {
    const analysis = { model_id: 'm9', partial: false, confusion_pairs: [] };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(analysis),
    });

    const result = await modelService.getErrorAnalysis('m9');

    expect(result).toEqual(analysis);
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/ml/m9/errors');
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer svc-token');
  });

  it('getErrorAnalysis() throws the backend detail on a non-OK response', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      json: jest.fn().mockResolvedValue({ detail: 'nope' }),
    });

    await expect(modelService.getErrorAnalysis('m9')).rejects.toThrow('nope');
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

  describe('prediction interfaces (#82)', () => {
    it('getModelFeatures() GETs the features endpoint and returns the schema', async () => {
      const schema = {
        features: [
          { name: 'age', type: 'number' },
          { name: 'gender', type: 'categorical', options: ['m', 'f'] },
        ],
        class_labels: ['no', 'yes'],
        problem_type: 'binary_classification',
        target_column: 'churned',
      };
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(schema),
      });

      const result = await modelService.getModelFeatures('m1');

      expect(result).toEqual(schema);
      const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/ml/m1/features');
      expect(init?.method).toBe('GET');
    });

    it('predict() returns confidence and class_labels for classification', async () => {
      const response = {
        predictions: [1],
        probabilities: [[0.1, 0.9]],
        confidence: [0.9],
        class_labels: ['0', '1'],
        feature_names: ['age'],
        model_info: {
          model_id: 'm1',
          algorithm: 'rf',
          problem_type: 'binary_classification',
          target_column: 'y',
        },
      };
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(response),
      });

      const result = await modelService.predict('m1', {
        data: [{ age: 30 }],
        include_probabilities: true,
      });

      expect(result.confidence).toEqual([0.9]);
      expect(result.class_labels).toEqual(['0', '1']);
      const [url] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/ml/m1/predict');
    });

    it('predict() forwards include_explanations and parses #83 enrichment', async () => {
      const response = {
        predictions: [1],
        confidence: [0.55],
        low_confidence: [true],
        is_calibrated: true,
        calibration_method: 'sigmoid',
        confidence_threshold: 0.7,
        explanations: [
          {
            method: 'linear_coefficients',
            explanation_text: 'driven by age',
            top_features: [
              { feature_name: 'age', contribution: 0.42, feature_value: 1.2 },
            ],
          },
        ],
        feature_names: ['age'],
        model_info: {
          model_id: 'm1',
          algorithm: 'lr',
          problem_type: 'binary_classification',
          target_column: 'y',
        },
      };
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(response),
      });

      const result = await modelService.predict('m1', {
        data: [{ age: 30 }],
        include_probabilities: true,
        include_explanations: true,
      });

      const [, init] = (global.fetch as jest.Mock).mock.calls[0];
      expect(JSON.parse(init.body).include_explanations).toBe(true);
      expect(result.low_confidence).toEqual([true]);
      expect(result.is_calibrated).toBe(true);
      expect(result.explanations?.[0]?.method).toBe('linear_coefficients');
      expect(result.explanations?.[0]?.top_features[0].feature_name).toBe('age');
    });

    it('createBatchJob() POSTs multipart form data to the batch endpoint', async () => {
      const job = { job_id: 'batch_1', status: 'pending' };
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(job),
      });

      // Node 18 (CI): build the file as a Blob + filename, not new File().
      const blob = new Blob(['age\n30\n'], { type: 'text/csv' });
      const file = Object.assign(blob, { name: 'data.csv' }) as unknown as File;

      const result = await modelService.createBatchJob('m1', file, {
        include_probabilities: true,
      });

      expect(result).toEqual(job);
      const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/batch/jobs');
      expect(init?.method).toBe('POST');
      expect(init?.body).toBeInstanceOf(FormData);
      const form = init?.body as FormData;
      expect(form.get('model_id')).toBe('m1');
      expect(form.get('include_probabilities')).toBe('true');
      // No explicit Content-Type — the browser sets the multipart boundary.
      const headers = (init?.headers ?? {}) as Record<string, string>;
      expect(headers['Content-Type']).toBeUndefined();
      expect(headers.Authorization).toBe('Bearer svc-token');
    });

    it('getBatchJobProgress() GETs the progress endpoint', async () => {
      const progress = {
        job_id: 'batch_1',
        status: 'running',
        percentage_complete: 50,
        processed_records: 5,
        total_records: 10,
        success_count: 5,
        error_count: 0,
        success_rate: 100,
        current_chunk: 1,
        total_chunks: 1,
      };
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue(progress),
      });

      const result = await modelService.getBatchJobProgress('batch_1');

      expect(result.percentage_complete).toBe(50);
      const [url] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/batch/jobs/batch_1/progress');
    });

    it('downloadBatchResults() returns the response Blob', async () => {
      const blob = new Blob(['age,prediction\n30,1\n'], { type: 'text/csv' });
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        blob: jest.fn().mockResolvedValue(blob),
      });

      const result = await modelService.downloadBatchResults('batch_1');

      expect(result).toBe(blob);
      const [url] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/batch/jobs/batch_1/download');
    });

    it('cancelBatchJob() POSTs to the cancel endpoint', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ message: 'Job cancelled successfully' }),
      });

      await modelService.cancelBatchJob('batch_1');

      const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/batch/jobs/batch_1/cancel');
      expect(init?.method).toBe('POST');
    });

    it('createBatchJob() throws the backend detail on failure', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 400,
        json: jest.fn().mockResolvedValue({ detail: 'Only CSV files are supported' }),
      });

      const blob = new Blob(['x'], { type: 'text/plain' });
      const file = Object.assign(blob, { name: 'data.txt' }) as unknown as File;

      await expect(
        modelService.createBatchJob('m1', file, {})
      ).rejects.toThrow('Only CSV files are supported');
    });
  });

  describe('SDK methods (#86)', () => {
    it('getSdkInfo() hits /ml/{id}/sdk and returns languages', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ languages: ['python', 'curl'] }),
      });

      const info = await modelService.getSdkInfo('m1');

      expect(info.languages).toEqual(['python', 'curl']);
      const [url] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/ml/m1/sdk');
    });

    it('getSdk() returns the SDK source text for a language', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        text: jest.fn().mockResolvedValue('# python client'),
      });

      const src = await modelService.getSdk('m1', 'python');

      expect(src).toBe('# python client');
      const [url] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/ml/m1/sdk/python');
    });

    it('getSdk() throws the backend detail on an unknown language', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: jest.fn().mockResolvedValue({ detail: "Language 'ruby' not supported." }),
      });

      await expect(modelService.getSdk('m1', 'ruby')).rejects.toThrow(
        "Language 'ruby' not supported."
      );
    });

    it('getSdkPostman() hits the postman route and returns JSON', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: jest.fn().mockResolvedValue({ info: { name: 'API' } }),
      });

      const collection = await modelService.getSdkPostman('m1');

      expect(collection).toEqual({ info: { name: 'API' } });
      const [url] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toBe('http://localhost:8000/api/v1/ml/m1/sdk/postman');
    });
  });
});
