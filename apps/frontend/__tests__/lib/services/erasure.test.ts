import { erasureApi, ErasureApiError } from '@/lib/services/erasure';

jest.mock('@/lib/auth-helpers', () => ({ getAuthToken: jest.fn().mockResolvedValue('tok') }));

const OK = {
  ok: true,
  json: async () => ({ erasure_id: 'e1', status: 'completed', manifest: {} }),
};

describe('erasureApi (#482)', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock) = jest.fn().mockResolvedValue(OK);
  });

  it('POSTs the account-erase endpoint with the auth token and version-prefixed URL', async () => {
    await erasureApi.eraseCurrentUser();
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/users\/me\/erase$/);
    expect(init.method).toBe('POST');
    expect(init.headers.Authorization).toBe('Bearer tok');
  });

  it('encodes the dataset id in the per-dataset erase URL', async () => {
    await erasureApi.eraseDataset('a b/c');
    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain('/datasets/a%20b%2Fc/erase');
  });

  it('throws ErasureApiError on a non-2xx response', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({ ok: false, status: 500 });
    await expect(erasureApi.eraseCurrentUser()).rejects.toBeInstanceOf(ErasureApiError);
  });
});
