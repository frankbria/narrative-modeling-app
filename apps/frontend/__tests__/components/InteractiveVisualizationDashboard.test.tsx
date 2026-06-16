import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'

import { InteractiveVisualizationDashboard } from '@/components/InteractiveVisualizationDashboard'
import {
  getBoxPlot,
  getScatterPlot,
  getLineChart,
} from '@/lib/services/visualization'

// Real backend services are mocked so we can assert the dashboard wires charts
// to fetched data instead of generating it with Math.random() (issue #170).
jest.mock('@/lib/services/visualization', () => ({
  getBoxPlot: jest.fn(),
  getScatterPlot: jest.fn(),
  getLineChart: jest.fn(),
  getHistogram: jest.fn(),
}))

// Stub the chart leaf components so we can assert on the data props the
// dashboard passes them, without recharts/SVG noise in jsdom.
jest.mock('@/components/HistogramChart', () => ({
  HistogramChart: ({
    datasetId,
    column,
    bins,
  }: {
    datasetId?: string
    column?: string
    bins?: number
  }) => (
    <div data-testid="histogram-chart">
      hist:{datasetId}:{column}:{bins}
    </div>
  ),
}))
jest.mock('@/components/BoxplotChart', () => ({
  BoxplotChart: ({ data }: { data: { median: number } }) => (
    <div data-testid="boxplot-chart">box-median:{data?.median}</div>
  ),
}))
jest.mock('@/components/ScatterPlotChart', () => ({
  ScatterPlotChart: ({ data }: { data: { data: unknown[] } }) => (
    <div data-testid="scatter-chart">scatter-points:{data?.data?.length}</div>
  ),
  ScatterPlotData: {},
}))
jest.mock('@/components/LineChart', () => ({
  LineChart: ({ data }: { data: { lines: unknown[] } }) => (
    <div data-testid="line-chart">line-series:{data?.lines?.length}</div>
  ),
  LineChartData: {},
}))
jest.mock('@/components/CorrelationHeatmap', () => ({
  CorrelationHeatmap: ({
    correlationMatrix,
  }: {
    correlationMatrix?: Record<string, Record<string, number>> | null
  }) => <div data-testid="correlation-heatmap">corr:{JSON.stringify(correlationMatrix)}</div>,
}))

// Minimal ChartControls stub exposing chart-type switching + export/refresh so
// tests can drive the dashboard without the real Radix selects.
jest.mock('@/components/ChartControls', () => ({
  ChartControls: ({
    onChartTypeChange,
    onExport,
    onRefresh,
  }: {
    onChartTypeChange: (t: string) => void
    onExport: () => void
    onRefresh: () => void
  }) => (
    <div>
      <button onClick={() => onChartTypeChange('histogram')}>set-histogram</button>
      <button onClick={() => onChartTypeChange('boxplot')}>set-boxplot</button>
      <button onClick={() => onChartTypeChange('scatter')}>set-scatter</button>
      <button onClick={() => onChartTypeChange('line')}>set-line</button>
      <button onClick={() => onChartTypeChange('correlation')}>set-correlation</button>
      <button onClick={onExport}>do-export</button>
      <button onClick={onRefresh}>do-refresh</button>
    </div>
  ),
}))

const mockGetBoxPlot = getBoxPlot as jest.Mock
const mockGetScatterPlot = getScatterPlot as jest.Mock
const mockGetLineChart = getLineChart as jest.Mock

const columns = [
  { name: 'age', type: 'numeric' as const },
  { name: 'income', type: 'numeric' as const },
  { name: 'city', type: 'categorical' as const },
  { name: 'signup_date', type: 'datetime' as const },
]

const statistics = {
  row_count: 10,
  column_count: 3,
  memory_usage_mb: 1,
  correlation_matrix: { age: { age: 1, income: 0.5 }, income: { age: 0.5, income: 1 } },
  column_statistics: [],
  missing_value_summary: {
    total_missing_values: 0,
    columns_with_missing: 0,
    complete_columns: 3,
  },
}

function renderDashboard() {
  return render(
    <InteractiveVisualizationDashboard
      datasetId="ds-1"
      columns={columns}
      statistics={statistics}
    />
  )
}

async function goToVisualizeTab(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: /visualize/i }))
}

describe('InteractiveVisualizationDashboard (real data — issue #170)', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders the boxplot from getBoxPlot, not a static placeholder', async () => {
    const user = userEvent.setup()
    mockGetBoxPlot.mockResolvedValue({
      min: 1,
      q1: 10,
      median: 42,
      q3: 70,
      max: 99,
      outliers: [],
    })

    renderDashboard()
    await user.click(screen.getByText('set-boxplot'))
    await goToVisualizeTab(user)

    await waitFor(() => {
      expect(screen.getByTestId('boxplot-chart')).toHaveTextContent('box-median:42')
    })
    // 42 proves real fetched data drives the chart (the old placeholder median was 50).
    expect(mockGetBoxPlot).toHaveBeenCalledWith('ds-1', 'age', 'mock-token')
  })

  it('renders the scatter plot from getScatterPlot once two numeric columns are selected', async () => {
    const user = userEvent.setup()
    mockGetScatterPlot.mockResolvedValue({
      data: [
        { x: 1, y: 2 },
        { x: 3, y: 4 },
        { x: 5, y: 6 },
      ],
      xLabel: 'age',
      yLabel: 'income',
    })

    renderDashboard()
    await user.click(screen.getByText('set-scatter'))
    // age is auto-selected; add income as the second numeric column.
    await user.click(screen.getByRole('button', { name: /^income/ }))
    await goToVisualizeTab(user)

    await waitFor(() => {
      expect(screen.getByTestId('scatter-chart')).toHaveTextContent('scatter-points:3')
    })
    expect(mockGetScatterPlot).toHaveBeenCalledWith('ds-1', 'age', 'income', [], 'mock-token')
  })

  it('renders the line chart from getLineChart with x + y series', async () => {
    const user = userEvent.setup()
    mockGetLineChart.mockResolvedValue({
      data: [{ x: 0, income: 5 }],
      lines: [{ dataKey: 'income', label: 'income' }],
      xLabel: 'age',
      yLabel: 'income',
    })

    renderDashboard()
    await user.click(screen.getByText('set-line'))
    await user.click(screen.getByRole('button', { name: /^income/ }))
    await goToVisualizeTab(user)

    await waitFor(() => {
      expect(screen.getByTestId('line-chart')).toHaveTextContent('line-series:1')
    })
    expect(mockGetLineChart).toHaveBeenCalledWith('ds-1', 'age', ['income'], [], 'mock-token')
  })

  it('supports a non-numeric (datetime) X axis for line charts', async () => {
    const user = userEvent.setup()
    mockGetLineChart.mockResolvedValue({
      data: [{ x: '2026-01-01', income: 5 }],
      lines: [{ dataKey: 'income', label: 'income' }],
      xLabel: 'signup_date',
      yLabel: 'income',
    })

    renderDashboard()
    await user.click(screen.getByText('set-line'))
    // age is auto-selected. Add signup_date, then deselect age so the datetime
    // column becomes the first (X) selection, then add income as the numeric Y.
    await user.click(screen.getByRole('button', { name: /^signup_date/ }))
    await user.click(screen.getByRole('button', { name: /^age/ }))
    await user.click(screen.getByRole('button', { name: /^income/ }))
    await goToVisualizeTab(user)

    await waitFor(() => {
      expect(screen.getByTestId('line-chart')).toHaveTextContent('line-series:1')
    })
    // X is the datetime column; only income is sent as the numeric Y series.
    expect(mockGetLineChart).toHaveBeenCalledWith('ds-1', 'signup_date', ['income'], [], 'mock-token')
  })

  it('renders the histogram in fetch-by-column mode (datasetId + column)', async () => {
    const user = userEvent.setup()
    renderDashboard()
    // histogram is the default chart; age is auto-selected. The default bin
    // count (50) is threaded through to the fetch.
    await goToVisualizeTab(user)

    // The default numeric column is selected via an effect, so wait for it.
    await waitFor(() => {
      expect(screen.getByTestId('histogram-chart')).toHaveTextContent('hist:ds-1:age:50')
    })
  })

  it('passes the real correlation_matrix to the heatmap', async () => {
    const user = userEvent.setup()
    renderDashboard()
    await user.click(screen.getByText('set-correlation'))
    await goToVisualizeTab(user)

    expect(screen.getByTestId('correlation-heatmap')).toHaveTextContent('"income":0.5')
  })

  it('shows a guidance state (no fabricated data) when scatter has fewer than two numeric columns', async () => {
    const user = userEvent.setup()
    renderDashboard()
    await user.click(screen.getByText('set-scatter'))
    await goToVisualizeTab(user)

    // Only the auto-selected single column → no scatter is fetched or fabricated.
    expect(mockGetScatterPlot).not.toHaveBeenCalled()
    expect(screen.queryByTestId('scatter-chart')).not.toBeInTheDocument()
    expect(screen.getByText(/two numeric columns/i)).toBeInTheDocument()
  })

  it('clears fetched scatter data when the selection drops below two numeric columns', async () => {
    const user = userEvent.setup()
    const createObjectURL = jest.fn(() => 'blob:mock')
    global.URL.createObjectURL = createObjectURL
    mockGetScatterPlot.mockResolvedValue({
      data: [{ x: 1, y: 2 }],
      xLabel: 'age',
      yLabel: 'income',
    })

    renderDashboard()
    await user.click(screen.getByText('set-scatter'))
    await user.click(screen.getByRole('button', { name: /^income/ }))
    await waitFor(() => expect(mockGetScatterPlot).toHaveBeenCalled())

    // Deselect income → back to a single numeric column. The cached scatter data
    // must be cleared so it can't be exported for a no-longer-valid selection.
    await user.click(screen.getByRole('button', { name: /^income/ }))
    await user.click(screen.getByText('do-export'))
    await goToVisualizeTab(user)

    await waitFor(() => {
      expect(screen.getByText(/no .*data .*export/i)).toBeInTheDocument()
    })
    expect(createObjectURL).not.toHaveBeenCalled()
  })

  it('does not export stale data after a failed refetch', async () => {
    const user = userEvent.setup()
    const createObjectURL = jest.fn(() => 'blob:mock')
    global.URL.createObjectURL = createObjectURL
    // First fetch succeeds, a later refetch (filter/refresh) fails.
    mockGetBoxPlot
      .mockResolvedValueOnce({ min: 1, q1: 10, median: 42, q3: 70, max: 99, outliers: [] })
      .mockRejectedValueOnce(new Error('boom'))

    renderDashboard()
    await user.click(screen.getByText('set-boxplot'))
    await waitFor(() => expect(mockGetBoxPlot).toHaveBeenCalledTimes(1))

    // Trigger a refetch that fails; the cached boxplot data must be cleared.
    await user.click(screen.getByText('do-refresh'))
    await waitFor(() => expect(mockGetBoxPlot).toHaveBeenCalledTimes(2))

    await user.click(screen.getByText('do-export'))
    expect(createObjectURL).not.toHaveBeenCalled()
  })

  it('exports the real fetched chart data', async () => {
    const user = userEvent.setup()
    const createObjectURL = jest.fn(() => 'blob:mock')
    const revokeObjectURL = jest.fn()
    global.URL.createObjectURL = createObjectURL
    global.URL.revokeObjectURL = revokeObjectURL

    mockGetBoxPlot.mockResolvedValue({
      min: 1,
      q1: 10,
      median: 42,
      q3: 70,
      max: 99,
      outliers: [],
    })

    renderDashboard()
    await user.click(screen.getByText('set-boxplot'))
    await waitFor(() => expect(mockGetBoxPlot).toHaveBeenCalled())

    await user.click(screen.getByText('do-export'))
    await waitFor(() => expect(createObjectURL).toHaveBeenCalled())
  })

  it('surfaces a friendly message instead of exporting when there is no data', async () => {
    const user = userEvent.setup()
    const createObjectURL = jest.fn(() => 'blob:mock')
    global.URL.createObjectURL = createObjectURL

    renderDashboard()
    // scatter with a single column never fetches → nothing to export.
    await user.click(screen.getByText('set-scatter'))
    await user.click(screen.getByText('do-export'))
    // The export error surfaces in the chart panel (Visualize tab).
    await goToVisualizeTab(user)

    await waitFor(() => {
      expect(screen.getByText(/no .*data .*export/i)).toBeInTheDocument()
    })
    expect(createObjectURL).not.toHaveBeenCalled()
  })
})
