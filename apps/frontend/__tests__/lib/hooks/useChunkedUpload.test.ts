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
    // Guarantee real timers are restored even if a test throws mid-way while
    // fake timers are active — otherwise the leak contaminates later tests.
    jest.useRealTimers();
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

  // Build a File whose arrayBuffer() is stubbed (jsdom omits it) so hashing works.
  const makeFile = (bytes: number) => {
    const file = new File(['x'.repeat(bytes)], 'big.csv', { type: 'text/csv' });
    Object.defineProperty(file, 'arrayBuffer', { value: async () => new ArrayBuffer(bytes) });
    return file;
  };

  const urls = () => (global.fetch as jest.Mock).mock.calls.map(([url]) => String(url));

  // Regression: the prior suite only exercised a single 8-byte chunk, so
  // multi-chunk slicing, per-chunk progress, and the chunk-count math were
  // untested. A 25-byte file at 10-byte chunks must upload in exactly 3 chunks.
  it('splits a large file into multiple chunks and reports progress per chunk', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(makeJsonResponse({ session_id: 'sess-1' })) // init
      .mockResolvedValueOnce(makeJsonResponse({ complete: false })) // chunk 0
      .mockResolvedValueOnce(makeJsonResponse({ complete: false })) // chunk 1
      .mockResolvedValueOnce(makeJsonResponse({ complete: false })) // chunk 2 (last)
      .mockResolvedValueOnce(makeJsonResponse({ file_id: 'file-1' })); // complete

    const onProgress = jest.fn();
    const { result } = renderHook(() => useChunkedUpload({ chunkSize: 10, onProgress }));

    let returned: unknown;
    await act(async () => {
      returned = await result.current.uploadFile(makeFile(25)); // ceil(25/10) = 3 chunks
    });

    expect(returned).toEqual({ file_id: 'file-1' });

    // Exactly one chunk request per chunk, addressed by index, plus init + complete.
    const chunkUrls = urls().filter((u) => u.includes('/chunk/'));
    expect(chunkUrls).toHaveLength(3);
    expect(chunkUrls[0]).toContain('/upload/chunked/sess-1/chunk/0');
    expect(chunkUrls[1]).toContain('/upload/chunked/sess-1/chunk/1');
    expect(chunkUrls[2]).toContain('/upload/chunked/sess-1/chunk/2');
    expect(urls().some((u) => u.includes('/upload/chunked/sess-1/complete'))).toBe(true);

    // Progress reported once per chunk, ending at 100%.
    expect(onProgress).toHaveBeenCalledTimes(3);
    const last = onProgress.mock.calls.at(-1)![0];
    expect(last.uploadedChunks).toBe(3);
    expect(last.totalChunks).toBe(3);
    expect(last.progress).toBe(100);
    expect(result.current.uploadState?.status).toBe('completed');
  });

  // A transient chunk failure must be retried (exponential backoff) and recover,
  // not abort the whole upload.
  it('retries a transient chunk failure and completes', async () => {
    jest.useFakeTimers();
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(makeJsonResponse({ session_id: 'sess-2' })) // init
      .mockRejectedValueOnce(new Error('network blip')) // chunk 0, attempt 1 fails
      .mockResolvedValueOnce(makeJsonResponse({ complete: false })) // chunk 0, retry succeeds
      .mockResolvedValueOnce(makeJsonResponse({ file_id: 'file-2' })); // complete

    const onError = jest.fn();
    const { result } = renderHook(() => useChunkedUpload({ chunkSize: 100, onError }));

    let returned: unknown;
    await act(async () => {
      const p = result.current.uploadFile(makeFile(20)); // 1 chunk
      await jest.advanceTimersByTimeAsync(1500); // drive the backoff timer
      returned = await p;
    });

    expect(returned).toEqual({ file_id: 'file-2' });
    // Two chunk attempts for the single chunk (initial + one retry).
    expect(urls().filter((u) => u.includes('/chunk/0'))).toHaveLength(2);
    // The transient error was recovered, so onError never fired.
    expect(onError).not.toHaveBeenCalled();
  });

  // When retries are exhausted the upload fails loudly via onError.
  it('surfaces an error after exhausting retries', async () => {
    jest.useFakeTimers();
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(makeJsonResponse({ session_id: 'sess-3' })) // init
      .mockRejectedValue(new Error('persistent failure')); // every chunk attempt fails

    const onError = jest.fn();
    const { result } = renderHook(() => useChunkedUpload({ chunkSize: 100, maxRetries: 2, onError }));

    await act(async () => {
      const p = result.current.uploadFile(makeFile(20)).catch(() => undefined);
      await jest.advanceTimersByTimeAsync(10_000); // drive all backoff timers
      await p;
    });

    // 1 initial + 2 retries = 3 chunk attempts, then it gives up.
    expect(urls().filter((u) => u.includes('/chunk/0'))).toHaveLength(3);
    expect(onError).toHaveBeenCalledWith('persistent failure');
    expect(result.current.uploadState?.status).toBe('error');
  });
});
