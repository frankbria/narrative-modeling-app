import { abTestingService } from '@/lib/services/abTesting';

// Issue #262: the service previously used a relative baseUrl (resolved against
// the frontend origin -> 404) and localStorage.getItem('authToken') (always
// null). These tests lock in the fix: absolute NEXT_PUBLIC_API_URL base and the
// backend-verifiable JWT from getAuthToken().
jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('jwt-abc'),
}));

const EXPERIMENT = {
  experiment_id: 'exp-1',
  name: 'Exp',
  status: 'draft',
  variants: [],
  primary_metric: 'accuracy',
  secondary_metrics: [],
  min_sample_size: 1000,
  confidence_level: 0.95,
  created_at: '2026-07-06T00:00:00Z',
};

describe('abTestingService (issue #262)', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock) = jest.fn().mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue([EXPERIMENT]),
    });
  });

  afterEach(() => jest.clearAllMocks());

  it('listExperiments hits the absolute backend URL with the JWT bearer token', async () => {
    await abTestingService.listExperiments();

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    // Absolute backend base, not a relative /api/v1 against the frontend origin.
    expect(String(url)).toBe('http://localhost:8000/api/v1/ab-testing/experiments');
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer jwt-abc');
    // Regression guard: no localStorage-based "Bearer null".
    expect(headers.Authorization).not.toContain('null');
  });

  it('listExperiments forwards the status filter as a query param', async () => {
    await abTestingService.listExperiments('running');
    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(String(url)).toBe(
      'http://localhost:8000/api/v1/ab-testing/experiments?status=running'
    );
  });

  it('createExperiment POSTs JSON with content-type and the JWT bearer token', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue(EXPERIMENT),
    });

    await abTestingService.createExperiment({
      name: 'Exp',
      model_ids: ['m1', 'm2'],
      primary_metric: 'accuracy',
    });

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(String(url)).toBe('http://localhost:8000/api/v1/ab-testing/experiments');
    expect(init?.method).toBe('POST');
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers.Authorization).toBe('Bearer jwt-abc');
  });

  it('throws when the backend responds non-ok (surfaces failures, not silent empty)', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 401 });
    await expect(abTestingService.listExperiments()).rejects.toThrow(
      'Failed to list experiments'
    );
  });
});
