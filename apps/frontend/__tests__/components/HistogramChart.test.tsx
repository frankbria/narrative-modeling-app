import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { HistogramChart } from '@/components/HistogramChart'
import { getHistogram, HistogramData } from '@/lib/services/visualization'
import { axisTicks } from '@/__tests__/utils/sizedRecharts'

// Mock the visualization service so we can drive the fetch-mode branch
jest.mock('@/lib/services/visualization', () => ({
  getHistogram: jest.fn(),
}))

// The histogram endpoint requires auth (get_current_user_id dependency on the
// backend route); the component must resolve and forward the bearer token.
jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('tok-123'),
}))

// Real recharts, with only ResponsiveContainer sized so jsdom's 0x0 layout
// doesn't blank the chart (#346). Bin labels below are the real XAxis ticks,
// so they only appear if `dataKey="bin"` still resolves against the data.
jest.mock('recharts', () =>
  jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts()
)

/** Bin labels as recharts actually drew them on the x-axis. */
const binLabels = (container: HTMLElement) => axisTicks(container, 'x')

const mockGetHistogram = getHistogram as jest.Mock

const sampleData: HistogramData = {
  bins: [3, 5],
  binEdges: [0, 10, 20],
  counts: [3, 5],
  min: 0,
  max: 20,
}

describe('HistogramChart', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders bins directly from the `data` prop without fetching', () => {
    const { container } = render(<HistogramChart data={sampleData} />)

    expect(mockGetHistogram).not.toHaveBeenCalled()
    expect(binLabels(container)).toEqual(['0.00 - 10.00', '10.00 - 20.00'])
    // One bar per bin, drawn by real recharts from `dataKey="count"`.
    expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(2)
  })

  it('fetches histogram data via datasetId+column when no `data` prop is given', async () => {
    mockGetHistogram.mockResolvedValue(sampleData)

    const { container } = render(<HistogramChart datasetId="ds-1" column="age" />)

    // Before resolution the empty-state placeholder is shown.
    expect(screen.getByText('No histogram data available')).toBeInTheDocument()

    await waitFor(() => {
      expect(binLabels(container)).toContain('0.00 - 10.00')
    })

    expect(mockGetHistogram).toHaveBeenCalledWith('ds-1', 'age', 50, 'tok-123')
  })

  it('forwards a custom bin count to the fetch', async () => {
    mockGetHistogram.mockResolvedValue(sampleData)

    render(<HistogramChart datasetId="ds-1" column="age" bins={20} />)

    await waitFor(() => {
      expect(mockGetHistogram).toHaveBeenCalledWith('ds-1', 'age', 20, 'tok-123')
    })
  })

  it('shows a distinct error state when the fetch fails', async () => {
    mockGetHistogram.mockRejectedValue(new Error('boom'))

    render(<HistogramChart datasetId="ds-1" column="age" />)

    // A 401/500/network failure must be distinguishable from a column with
    // genuinely no data (issue #166 review).
    await waitFor(() => {
      expect(screen.getByText('Failed to load histogram data')).toBeInTheDocument()
    })
    expect(screen.queryByText('No histogram data available')).not.toBeInTheDocument()
    expect(document.querySelector('.recharts-wrapper')).not.toBeInTheDocument()
  })

  it('renders the empty-state when neither data nor datasetId/column are provided', () => {
    render(<HistogramChart />)

    expect(mockGetHistogram).not.toHaveBeenCalled()
    expect(screen.getByText('No histogram data available')).toBeInTheDocument()
  })
})
