import { getHistogram } from '@/lib/services/visualization'

// Regression (issue #166 review): the backend histogram endpoint returns
// snake_case fields with `bins` as bin CENTERS and `counts` as the counts
// ({ bins, counts, bin_edges } from visualization_cache.py), while consumers
// of HistogramData expect camelCase with `bins` carrying the counts.
// getHistogram must normalize the payload, not pass it through.
describe('getHistogram', () => {
  beforeEach(() => {
    ;(global.fetch as jest.Mock).mockReset()
  })

  it('normalizes the snake_case backend payload to HistogramData', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue({
        bins: [5, 15], // bin centers (backend semantics)
        counts: [3, 7],
        bin_edges: [0, 10, 20],
      }),
    })

    const result = await getHistogram('ds-1', 'age', 50, 'tok-123')

    expect(result).toEqual({
      bins: [3, 7], // counts (frontend HistogramData semantics)
      counts: [3, 7],
      binEdges: [0, 10, 20],
      min: 0,
      max: 20,
    })
  })

  it('sends the bearer token when provided', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue({ bins: [], counts: [], bin_edges: [] }),
    })

    await getHistogram('ds-1', 'age', 50, 'tok-123')

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0]
    expect(url).toContain('/visualizations/histogram/ds-1/age?bins=50')
    expect(init.headers['Authorization']).toBe('Bearer tok-123')
  })

  it('URL-encodes dataset and column path segments', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue({ bins: [], counts: [], bin_edges: [] }),
    })

    await getHistogram('ds 1', 'price/unit #2')

    const [url] = (global.fetch as jest.Mock).mock.calls[0]
    expect(url).toContain('/visualizations/histogram/ds%201/price%2Funit%20%232?bins=50')
  })

  it('throws on a non-ok response', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 401 })

    await expect(getHistogram('ds-1', 'age')).rejects.toThrow('Failed to fetch histogram data')
  })
})
