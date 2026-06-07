import { renderHook, act } from '@testing-library/react';
import useChunkedUpload from '@/lib/hooks/useChunkedUpload';

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'user-123' } }, status: 'authenticated' }),
}));

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('test-auth-token'),
}));

describe('useChunkedUpload', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock) = jest.fn();
    // jsdom does not provide SubtleCrypto; stub digest used for file hashing.
    Object.defineProperty(globalThis, 'crypto', {
      configurable: true,
      value: {
        subtle: {
          digest: jest.fn().mockResolvedValue(new ArrayBuffer(32)),
        },
      },
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  const makeJsonResponse = (body: Record<string, unknown>) => ({
    ok: true,
    statusText: 'OK',
    json: jest.fn().mockResolvedValue(body),
  });

  // Regression: the chunk/complete requests previously called the non-existent
  // `session.getToken()`, which crashes at runtime. They must instead resolve
  // the token via getAuthToken() and send it as a Bearer header.
  it('authorizes chunk uploads using getAuthToken (not session.getToken)', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(makeJsonResponse({ session_id: 'session-abc' })) // init
      .mockResolvedValueOnce(makeJsonResponse({ complete: true })) // chunk
      .mockResolvedValueOnce(makeJsonResponse({ file_id: 'file-xyz' })); // complete

    const { result } = renderHook(() => useChunkedUpload({ chunkSize: 1024 }));

    const file = new File(['hello world'], 'data.csv', { type: 'text/csv' });
    // jsdom's File does not implement arrayBuffer(); provide a minimal stub.
    if (typeof file.arrayBuffer !== 'function') {
      Object.defineProperty(file, 'arrayBuffer', {
        value: async () => new ArrayBuffer(8),
      });
    }

    let returned: unknown;
    await act(async () => {
      returned = await result.current.uploadFile(file);
    });

    expect(returned).toEqual({ file_id: 'file-xyz' });

    // Every request must carry the token resolved from getAuthToken.
    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls.length).toBeGreaterThanOrEqual(2);
    for (const [, init] of calls) {
      const headers = (init?.headers ?? {}) as Record<string, string>;
      expect(headers.Authorization).toBe('Bearer test-auth-token');
    }
  });
});
