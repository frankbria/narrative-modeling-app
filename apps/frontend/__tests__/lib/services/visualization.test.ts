import { getHistogram, getBoxPlot, getScatterPlot, getLineChart } from '@/lib/services/visualization'

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
    expect(url).toContain('/visualizations/histogram/ds-1/age?num_bins=50')
    expect(init.headers['Authorization']).toBe('Bearer tok-123')
  })

  it('URL-encodes dataset and column path segments', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue({ bins: [], counts: [], bin_edges: [] }),
    })

    await getHistogram('ds 1', 'price/unit #2')

    const [url] = (global.fetch as jest.Mock).mock.calls[0]
    expect(url).toContain('/visualizations/histogram/ds%201/price%2Funit%20%232?num_bins=50')
  })

  it('throws on a non-ok response', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 401 })

    await expect(getHistogram('ds-1', 'age')).rejects.toThrow('Failed to fetch histogram data')
  })
})

// Issue #170: column names come from user CSV headers and may contain reserved
// URL characters (spaces, `#`, `&`, `?`, `%`, …). Path-based chart services must
// percent-encode each segment so it survives as a single path param.
// NOTE: a literal `/` in a column name is *not* supported — encodeURIComponent
// turns it into `%2F`, but Starlette percent-decodes the path before route
// matching, so the slash becomes a segment separator and the route 404s. (This
// predates this change; the old code interpolated the raw `/` and 404'd too.)
// These tests therefore use single-segment-safe special characters.
describe('chart services encode path segments', () => {
  beforeEach(() => {
    ;(global.fetch as jest.Mock).mockReset()
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({}),
    })
  })

  it('encodes dataset and column in getBoxPlot', async () => {
    await getBoxPlot('ds 1', 'unit price')
    const [url] = (global.fetch as jest.Mock).mock.calls[0]
    expect(url).toContain('/visualizations/boxplot/ds%201/unit%20price')
  })

  it('encodes both columns in getScatterPlot', async () => {
    await getScatterPlot('ds-1', 'col#1', 'c d')
    const [url] = (global.fetch as jest.Mock).mock.calls[0]
    expect(url).toContain('/visualizations/scatter/ds-1/col%231/c%20d')
  })

  it('encodes the x column in getLineChart', async () => {
    await getLineChart('ds-1', 'col & x', ['y1'])
    const [url] = (global.fetch as jest.Mock).mock.calls[0]
    expect(url).toContain('/visualizations/line/ds-1/col%20%26%20x')
  })
})
