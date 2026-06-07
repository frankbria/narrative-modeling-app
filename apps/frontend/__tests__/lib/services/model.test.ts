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
});
