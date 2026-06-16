import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { HistogramChart } from '@/components/HistogramChart'
import { getHistogram, HistogramData } from '@/lib/services/visualization'

// Mock the visualization service so we can drive the fetch-mode branch
jest.mock('@/lib/services/visualization', () => ({
  getHistogram: jest.fn(),
}))

// The histogram endpoint requires auth (get_current_user_id dependency on the
// backend route); the component must resolve and forward the bearer token.
jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('tok-123'),
}))

// recharts ResponsiveContainer needs a measurable parent in jsdom; stub the
// chart primitives so we can assert on the rendered bin labels instead.
jest.mock('recharts', () => {
  const Bar = ({ children }: { children?: React.ReactNode }) => <div data-testid="bar">{children}</div>
  const BarChart = ({ data, children }: { data: Array<{ bin: string; count: number }>; children?: React.ReactNode }) => (
    <div data-testid="bar-chart">
      {data.map((d) => (
        <div key={d.bin} data-testid="bin">
          {d.bin}:{d.count}
        </div>
      ))}
      {children}
    </div>
  )
  const passthrough = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
  return {
    BarChart,
    Bar,
    XAxis: passthrough,
    YAxis: passthrough,
    CartesianGrid: passthrough,
    Tooltip: passthrough,
    ResponsiveContainer: passthrough,
  }
})

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
    render(<HistogramChart data={sampleData} />)

    expect(mockGetHistogram).not.toHaveBeenCalled()
    expect(screen.getByText('0.00 - 10.00:3')).toBeInTheDocument()
    expect(screen.getByText('10.00 - 20.00:5')).toBeInTheDocument()
  })

  it('fetches histogram data via datasetId+column when no `data` prop is given', async () => {
    mockGetHistogram.mockResolvedValue(sampleData)

    render(<HistogramChart datasetId="ds-1" column="age" />)

    // Before resolution the empty-state placeholder is shown.
    expect(screen.getByText('No histogram data available')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('0.00 - 10.00:3')).toBeInTheDocument()
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
    expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument()
  })

  it('renders the empty-state when neither data nor datasetId/column are provided', () => {
    render(<HistogramChart />)

    expect(mockGetHistogram).not.toHaveBeenCalled()
    expect(screen.getByText('No histogram data available')).toBeInTheDocument()
  })
})
