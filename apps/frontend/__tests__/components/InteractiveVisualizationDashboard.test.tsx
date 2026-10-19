import React from 'react'
import { render, screen, waitFor, within, act } from '@testing-library/react'
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
    stats,
  }: {
    correlationMatrix?: Record<string, Record<string, number>> | null
    stats?: unknown[]
  }) => (
    <div data-testid="correlation-heatmap" data-stats={JSON.stringify(stats)}>
      corr:{JSON.stringify(correlationMatrix)}
    </div>
  ),
}))

// Minimal ChartControls stub exposing chart-type switching + export/refresh so
// tests can drive the dashboard without the real Radix selects.
jest.mock('@/components/ChartControls', () => ({
  ChartControls: ({
    onChartTypeChange,
    onFiltersChange,
    onExport,
    onRefresh,
  }: {
    onChartTypeChange: (t: string) => void
    onFiltersChange: (f: unknown[]) => void
    onExport: () => void
    onRefresh: () => void
  }) => (
    <div>
      <button onClick={() => onChartTypeChange('mystery')}>set-mystery</button>
      <button onClick={() => onFiltersChange([{ column: 'age', operator: 'gt', value: 1 }])}>add-filter</button>
      <button onClick={() => onFiltersChange([{ column: 'age', operator: 'gt', value: 1 }, { column: 'age', operator: 'lt', value: 9 }])}>add-two-filters</button>
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

    // The default numeric column is derived from `columns` during render.
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

describe('InteractiveVisualizationDashboard behaviour', () => {
  const box = { min: 1, q1: 10, median: 42, q3: 70, max: 99, outliers: [] }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  const selectedBadges = () =>
    screen
      .getAllByRole('button')
      .filter(b => /^(age|income|city|signup_date)\d$/.test(b.textContent ?? ''))
      .map(b => b.textContent)

  const description = () => screen.getByText(/columns for visualization/i).textContent

  describe('column groups', () => {
    it('lists each kind of column under its own heading with a count', () => {
      renderDashboard()
      expect(screen.getByText('Numeric (2)')).toBeInTheDocument()
      expect(screen.getByText('Categorical (1)')).toBeInTheDocument()
      expect(screen.getByText('DateTime (1)')).toBeInTheDocument()
    })

    it('leaves out the headings of kinds the dataset does not have', () => {
      render(<InteractiveVisualizationDashboard datasetId="ds-1" columns={[columns[0]]} />)
      expect(screen.getByText('Numeric (1)')).toBeInTheDocument()
      expect(screen.queryByText(/^Categorical/)).not.toBeInTheDocument()
      expect(screen.queryByText(/^DateTime/)).not.toBeInTheDocument()
    })

    it('numbers the selected numeric columns in selection order and counts the selection', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      expect(description()).toContain('(1 selected)')
      await user.click(screen.getByRole('button', { name: /^income/ }))
      expect(description()).toContain('(2 selected)')
      expect(selectedBadges()).toEqual(['age1', 'income2'])
    })
  })

  describe('toggling columns', () => {
    it('starts on the first numeric column', () => {
      renderDashboard()
      expect(description()).toContain('(1 selected)')
      expect(screen.getByRole('button', { name: /^age\s*1/ })).toBeInTheDocument()
    })

    it('replaces the selection when one more column would exceed a histogram or box plot limit of one', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByRole('button', { name: /^income/ }))
      expect(selectedBadges()).toEqual(['income1'])
      expect(description()).toContain('(1 selected)')
    })

    it('allows two for a scatter plot and starts over with the third', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      await user.click(screen.getByRole('button', { name: /^income/ }))
      await user.click(screen.getByRole('button', { name: /^signup_date/ }))
      expect(description()).toContain('(1 selected)')
      await user.click(screen.getByRole('button', { name: /^age/ }))
      expect(description()).toContain('(2 selected)')
    })

    it('allows four for a line chart and starts over with the fifth', async () => {
      const user = userEvent.setup()
      render(
        <InteractiveVisualizationDashboard
          datasetId="ds-1"
          columns={[
            ...columns,
            { name: 'a5', type: 'numeric' as const },
            { name: 'a6', type: 'numeric' as const },
          ]}
        />
      )
      await user.click(screen.getByText('set-line'))
      for (const name of ['income', 'city', 'signup_date']) {
        await user.click(screen.getByRole('button', { name: new RegExp(`^${name}`) }))
      }
      expect(description()).toContain('(4 selected)')
      await user.click(screen.getByRole('button', { name: /^a5/ }))
      expect(description()).toContain('(1 selected)')
    })

    it('deselects a selected column, and the first numeric column returns when nothing is left', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      await user.click(screen.getByRole('button', { name: /^income/ }))
      await user.click(screen.getByRole('button', { name: /^age/ }))
      expect(selectedBadges()).toEqual(['income1'])
      await user.click(screen.getByRole('button', { name: /^income/ }))
      // nothing chosen: the default (first numeric column) applies again
      expect(selectedBadges()).toEqual(['age1'])
    })
  })

  describe('chart recommendations', () => {
    const card = () => screen.getByText('Chart Recommendations').closest('.rounded-lg') as HTMLElement
    const recommendations = () => within(card())

    it('suggests histogram and box plot for one numeric column', () => {
      renderDashboard()
      expect(recommendations().getByText('Histogram, Box Plot')).toBeInTheDocument()
    })

    it('suggests a bar chart for one categorical column', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByRole('button', { name: /^city/ }))
      expect(recommendations().getByText('Bar Chart')).toBeInTheDocument()
    })

    it('suggests nothing for a single datetime column', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByRole('button', { name: /^signup_date/ }))
      expect(card().querySelectorAll('.rounded-full')).toHaveLength(0)
    })

    it('suggests scatter and line for two numeric columns', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      await user.click(screen.getByRole('button', { name: /^income/ }))
      expect(recommendations().getByText('Scatter Plot, Line Chart')).toBeInTheDocument()
    })

    it('suggests a grouped box plot for a numeric and a categorical column', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      await user.click(screen.getByRole('button', { name: /^city/ }))
      expect(recommendations().getByText('Box Plot (grouped), Bar Chart')).toBeInTheDocument()
    })

    it('suggests nothing for two columns that are neither both numeric nor numeric plus categorical', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      await user.click(screen.getByRole('button', { name: /^city/ }))
      await user.click(screen.getByRole('button', { name: /^age/ }))
      await user.click(screen.getByRole('button', { name: /^signup_date/ }))
      expect(card().querySelectorAll('.rounded-full')).toHaveLength(0)
    })

    it('suggests line chart and heatmap for three or more columns', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-line'))
      await user.click(screen.getByRole('button', { name: /^income/ }))
      await user.click(screen.getByRole('button', { name: /^city/ }))
      expect(recommendations().getByText('Line Chart, Correlation Heatmap')).toBeInTheDocument()
    })

    it('asks for a selection when the dataset has no numeric column to default to', () => {
      render(<InteractiveVisualizationDashboard datasetId="ds-1" columns={[columns[2]]} />)
      expect(recommendations().getByText('Select columns to see chart recommendations')).toBeInTheDocument()
    })
  })

  describe('visualize tab', () => {
    it('titles the panel with the capitalised chart name and lists the selection', async () => {
      const user = userEvent.setup()
      mockGetBoxPlot.mockResolvedValue(box)
      renderDashboard()
      await user.click(screen.getByText('set-boxplot'))
      await goToVisualizeTab(user)
      expect(screen.getByText(/Boxplot Chart/)).toBeInTheDocument()
      expect(screen.getByText('Visualizing: age')).toBeInTheDocument()
    })

    it('says what to do when nothing can be selected', async () => {
      const user = userEvent.setup()
      render(<InteractiveVisualizationDashboard datasetId="ds-1" columns={[columns[2]]} />)
      await goToVisualizeTab(user)
      expect(screen.getByText('Select columns to visualize')).toBeInTheDocument()
      expect(screen.queryByText(/^Visualizing:/)).not.toBeInTheDocument()
    })

    it('shows a loading line while the chart data is on its way', async () => {
      const user = userEvent.setup()
      let resolve: (v: unknown) => void = () => {}
      mockGetBoxPlot.mockReturnValue(new Promise(r => (resolve = r)))
      renderDashboard()
      await user.click(screen.getByText('set-boxplot'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('Loading visualization...')).toBeInTheDocument()
      await act(async () => resolve(box))
      expect(await screen.findByTestId('boxplot-chart')).toBeInTheDocument()
    })

    it('shows the failure when the chart data cannot be loaded', async () => {
      const user = userEvent.setup()
      mockGetBoxPlot.mockRejectedValue(new Error('nope'))
      renderDashboard()
      await user.click(screen.getByText('set-boxplot'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('Failed to load chart data')).toBeInTheDocument()
      expect(screen.queryByTestId('boxplot-chart')).not.toBeInTheDocument()
    })

    it('counts the filters in the panel header', async () => {
      const user = userEvent.setup()
      mockGetLineChart.mockResolvedValue({ data: [], lines: [{ dataKey: 'income' }], xLabel: 'a', yLabel: 'b' })
      renderDashboard()
      await goToVisualizeTab(user)
      expect(screen.queryByText(/^\d+ filters?$/)).not.toBeInTheDocument()
      await user.click(screen.getByRole('tab', { name: /configure/i }))
      await user.click(screen.getByText('add-filter'))
      await goToVisualizeTab(user)
      expect(screen.getByText('1 filter')).toBeInTheDocument()
      await user.click(screen.getByRole('tab', { name: /configure/i }))
      await user.click(screen.getByText('add-two-filters'))
      await goToVisualizeTab(user)
      expect(screen.getByText('2 filters')).toBeInTheDocument()
    })

    it('passes the filters to a scatter fetch', async () => {
      const user = userEvent.setup()
      mockGetScatterPlot.mockResolvedValue({ data: [{ x: 1, y: 2 }], xLabel: 'a', yLabel: 'b' })
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      await user.click(screen.getByRole('button', { name: /^income/ }))
      await user.click(screen.getByText('add-filter'))
      await waitFor(() =>
        expect(mockGetScatterPlot).toHaveBeenLastCalledWith(
          'ds-1',
          'age',
          'income',
          [{ column: 'age', operator: 'gt', value: 1 }],
          'mock-token'
        )
      )
    })

    it.each([
      ['set-histogram', 'Select a numeric column to view its histogram'],
      ['set-boxplot', 'Select a numeric column to view its box plot'],
      ['set-scatter', 'Select two numeric columns (X and Y) to plot a scatter chart'],
      ['set-line', 'Select an X column and at least one numeric Y column for a line chart'],
    ])('%s without a numeric column explains what is needed', async (button, message) => {
      const user = userEvent.setup()
      render(<InteractiveVisualizationDashboard datasetId="ds-1" columns={[columns[2], columns[3]]} />)
      await user.click(screen.getByRole('button', { name: /^city/ }))
      await user.click(screen.getByText(button))
      await goToVisualizeTab(user)
      expect(screen.getByText(message)).toBeInTheDocument()
    })

    it('says so when a chart fetch returns nothing', async () => {
      const user = userEvent.setup()
      mockGetBoxPlot.mockResolvedValue(null)
      renderDashboard()
      await user.click(screen.getByText('set-boxplot'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('No data available for the selected column')).toBeInTheDocument()
    })

    it('says so when a scatter or line fetch returns nothing', async () => {
      const user = userEvent.setup()
      mockGetScatterPlot.mockResolvedValue(null)
      mockGetLineChart.mockResolvedValue(null)
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      await user.click(screen.getByRole('button', { name: /^income/ }))
      await goToVisualizeTab(user)
      expect(await screen.findByText('No data available for the selected columns')).toBeInTheDocument()
      await user.click(screen.getByRole('tab', { name: /configure/i }))
      await user.click(screen.getByText('set-line'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('No data available for the selected columns')).toBeInTheDocument()
    })

    it('asks for an X and a numeric Y column when a line chart has only one column', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-line'))
      await goToVisualizeTab(user)
      expect(
        screen.getByText('Select an X column and at least one numeric Y column for a line chart')
      ).toBeInTheDocument()
      expect(mockGetLineChart).not.toHaveBeenCalled()
    })

    it('asks for a numeric Y column when a line chart has only non-numeric Y columns', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-line'))
      await user.click(screen.getByRole('button', { name: /^city/ }))
      await goToVisualizeTab(user)
      expect(
        screen.getByText('Select an X column and at least one numeric Y column for a line chart')
      ).toBeInTheDocument()
      expect(mockGetLineChart).not.toHaveBeenCalled()
    })

    it('does not fetch a box plot or scatter plot without enough numeric columns', async () => {
      const user = userEvent.setup()
      render(<InteractiveVisualizationDashboard datasetId="ds-1" columns={[columns[2], columns[3]]} />)
      await user.click(screen.getByRole('button', { name: /^city/ }))
      await user.click(screen.getByText('set-boxplot'))
      await user.click(screen.getByText('set-scatter'))
      expect(mockGetBoxPlot).not.toHaveBeenCalled()
      expect(mockGetScatterPlot).not.toHaveBeenCalled()
    })

    it('does not fetch without a dataset id', async () => {
      const user = userEvent.setup()
      render(<InteractiveVisualizationDashboard datasetId="" columns={columns} />)
      await user.click(screen.getByText('set-boxplot'))
      expect(mockGetBoxPlot).not.toHaveBeenCalled()
    })

    it('says a chart type it does not know is unsupported', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-mystery'))
      await goToVisualizeTab(user)
      expect(screen.getByText('This chart type is not supported yet')).toBeInTheDocument()
    })

    it('keeps showing the histogram after a refresh', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('do-refresh'))
      await goToVisualizeTab(user)
      expect(screen.getByTestId('histogram-chart')).toHaveTextContent('hist:ds-1:age:50')
    })

    it('hands the heatmap stats built from the payload, whatever its shape', async () => {
      const user = userEvent.setup()
      render(
        <InteractiveVisualizationDashboard
          datasetId="ds-1"
          columns={columns}
          statistics={{
            ...statistics,
            column_statistics: [
              { column_name: 'age', data_type: 'integer', total_count: 10, null_count: 1, unique_count: 4 },
              { column_name: 'city', data_type: 'object', total_count: 10, null_count: 0, unique_count: 3 },
              null,
              'junk',
              {},
            ] as never,
          }}
        />
      )
      await user.click(screen.getByText('set-correlation'))
      await goToVisualizeTab(user)
      const stats = JSON.parse(screen.getByTestId('correlation-heatmap').getAttribute('data-stats')!)
      expect(stats).toEqual([
        { field_name: 'age', field_type: 'numeric', count: 10, missing_values: 1, unique_values: 4 },
        { field_name: 'city', field_type: 'object', count: 10, missing_values: 0, unique_values: 3 },
        { field_name: '', field_type: '', count: 0, missing_values: 0, unique_values: 0 },
      ])
    })

    it('builds the heatmap stats from the columns when the payload has none', async () => {
      const user = userEvent.setup()
      render(
        <InteractiveVisualizationDashboard
          datasetId="ds-1"
          columns={[
            { name: 'age', type: 'numeric', null_count: 2, unique_count: 5 },
            { name: 'city', type: 'categorical' },
          ]}
        />
      )
      await user.click(screen.getByText('set-correlation'))
      await goToVisualizeTab(user)
      const heatmap = screen.getByTestId('correlation-heatmap')
      expect(JSON.parse(heatmap.getAttribute('data-stats')!)).toEqual([
        { field_name: 'age', field_type: 'numeric', count: 0, missing_values: 2, unique_values: 5 },
        { field_name: 'city', field_type: 'categorical', count: 0, missing_values: 0, unique_values: 0 },
      ])
      expect(heatmap).toHaveTextContent('corr:null')
    })
  })

  describe('exporting', () => {
    let blobs: Blob[]
    let downloads: string[]

    beforeEach(() => {
      blobs = []
      downloads = []
      global.URL.createObjectURL = jest.fn((blob: Blob | MediaSource) => {
        blobs.push(blob as Blob)
        return 'blob:mock'
      })
      global.URL.revokeObjectURL = jest.fn()
      jest
        .spyOn(HTMLAnchorElement.prototype, 'click')
        .mockImplementation(function (this: HTMLAnchorElement) {
          downloads.push(this.download)
        })
    })

    afterEach(() => {
      jest.restoreAllMocks()
    })

    const readBlob = (blob: Blob) =>
      new Promise<string>(resolve => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.readAsText(blob)
      })
    const exported = async () => JSON.parse(await readBlob(blobs[0]))

    it('downloads a box plot as <chart>_<dataset>.json and releases the object URL', async () => {
      const user = userEvent.setup()
      mockGetBoxPlot.mockResolvedValue(box)
      renderDashboard()
      await user.click(screen.getByText('set-boxplot'))
      await waitFor(() => expect(mockGetBoxPlot).toHaveBeenCalled())
      await waitFor(() => expect(screen.getByText('do-export')).toBeEnabled())
      await user.click(screen.getByText('do-export'))
      await waitFor(() => expect(downloads).toEqual(['boxplot_ds-1.json']))
      expect(await exported()).toEqual(box)
      expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock')
    })

    it('downloads scatter and line data', async () => {
      const user = userEvent.setup()
      const scatter = { data: [{ x: 1, y: 2 }], xLabel: 'a', yLabel: 'b' }
      const line = { data: [{ x: 1, income: 2 }], lines: [{ dataKey: 'income', label: 'income' }], xLabel: 'a', yLabel: 'b' }
      mockGetScatterPlot.mockResolvedValue(scatter)
      mockGetLineChart.mockResolvedValue(line)
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      await user.click(screen.getByRole('button', { name: /^income/ }))
      await waitFor(() => expect(mockGetScatterPlot).toHaveBeenCalled())
      await user.click(screen.getByText('do-export'))
      await waitFor(() => expect(blobs).toHaveLength(1))
      expect(await exported()).toEqual(scatter)
      await user.click(screen.getByText('set-line'))
      await waitFor(() => expect(mockGetLineChart).toHaveBeenCalled())
      await user.click(screen.getByText('do-export'))
      await waitFor(() => expect(blobs).toHaveLength(2))
      expect(JSON.parse(await readBlob(blobs[1]))).toEqual(line)
      expect(downloads).toEqual(['scatter_ds-1.json', 'line_ds-1.json'])
    })

    it('downloads the correlation matrix from the statistics', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-correlation'))
      await user.click(screen.getByText('do-export'))
      await waitFor(() => expect(blobs).toHaveLength(1))
      expect(await exported()).toEqual(statistics.correlation_matrix)
    })

    it('has nothing to export for a correlation chart without a matrix', async () => {
      const user = userEvent.setup()
      render(<InteractiveVisualizationDashboard datasetId="ds-1" columns={columns} />)
      await user.click(screen.getByText('set-correlation'))
      await user.click(screen.getByText('do-export'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('No chart data available to export yet')).toBeInTheDocument()
      expect(blobs).toHaveLength(0)
    })

    it('fetches the selected column afresh to export a histogram, with the bin count', async () => {
      const user = userEvent.setup()
      const { getHistogram } = jest.requireMock('@/lib/services/visualization')
      getHistogram.mockResolvedValue({ bins: [1, 2], counts: [3] })
      renderDashboard()
      await user.click(screen.getByText('do-export'))
      await waitFor(() => expect(blobs).toHaveLength(1))
      expect(getHistogram).toHaveBeenCalledWith('ds-1', 'age', 50, 'mock-token')
      expect(await exported()).toEqual({ bins: [1, 2], counts: [3] })
      expect(downloads).toEqual(['histogram_ds-1.json'])
    })

    it('has nothing to export for a histogram without a numeric column', async () => {
      const user = userEvent.setup()
      render(<InteractiveVisualizationDashboard datasetId="ds-1" columns={[columns[2]]} />)
      await user.click(screen.getByRole('button', { name: /^city/ }))
      await user.click(screen.getByText('do-export'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('No chart data available to export yet')).toBeInTheDocument()
    })

    it('has nothing to export for a chart type it does not know', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-mystery'))
      await user.click(screen.getByText('do-export'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('No chart data available to export yet')).toBeInTheDocument()
    })

    it('shows the reason when the export itself fails, and a generic one for a non-Error', async () => {
      const user = userEvent.setup()
      const errorLog = jest.spyOn(console, 'error').mockImplementation(() => {})
      const { getHistogram } = jest.requireMock('@/lib/services/visualization')
      getHistogram.mockRejectedValueOnce(new Error('histogram down'))
      renderDashboard()
      await user.click(screen.getByText('do-export'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('histogram down')).toBeInTheDocument()
      expect(errorLog).toHaveBeenCalledWith('Export failed:', expect.any(Error))
      await user.click(screen.getByRole('tab', { name: /configure/i }))
      getHistogram.mockRejectedValueOnce('plain')
      await user.click(screen.getByText('do-export'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('Export failed')).toBeInTheDocument()
    })

    it('clears an export message when the chart is refreshed', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-correlation'))
      await user.click(screen.getByText('set-mystery'))
      await user.click(screen.getByText('do-export'))
      await goToVisualizeTab(user)
      expect(await screen.findByText('No chart data available to export yet')).toBeInTheDocument()
      await user.click(screen.getByRole('tab', { name: /configure/i }))
      await user.click(screen.getByText('do-refresh'))
      await goToVisualizeTab(user)
      expect(screen.queryByText('No chart data available to export yet')).not.toBeInTheDocument()
    })

    it('exports from the panel header buttons too', async () => {
      const user = userEvent.setup()
      mockGetBoxPlot.mockResolvedValue(box)
      renderDashboard()
      await user.click(screen.getByText('set-boxplot'))
      await goToVisualizeTab(user)
      await screen.findByTestId('boxplot-chart')
      const header = screen.getByText(/Boxplot Chart/).closest('div.flex.flex-col') as HTMLElement
      const [refresh, download] = within(header).getAllByRole('button')
      await user.click(download)
      await waitFor(() => expect(blobs).toHaveLength(1))
      await user.click(refresh)
      await waitFor(() => expect(mockGetBoxPlot).toHaveBeenCalledTimes(2))
    })
  })

  describe('insights tab', () => {
    it('describes the chart and the selection, and recommends another view', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByRole('tab', { name: /insights/i }))
      expect(screen.getByText(/shows interesting patterns in age/)).toBeInTheDocument()
      expect(screen.getByText(/Consider exploring box plots/)).toBeInTheDocument()
      expect(screen.queryByText(/Correlation Analysis/)).not.toBeInTheDocument()
    })

    it('adds the correlation note for several columns and points a non-histogram at histograms', async () => {
      const user = userEvent.setup()
      renderDashboard()
      await user.click(screen.getByText('set-scatter'))
      await user.click(screen.getByRole('button', { name: /^income/ }))
      await user.click(screen.getByRole('tab', { name: /insights/i }))
      expect(screen.getByText(/shows interesting patterns in age, income/)).toBeInTheDocument()
      expect(screen.getByText(/Correlation Analysis/)).toBeInTheDocument()
      expect(screen.getByText(/Consider exploring histograms/)).toBeInTheDocument()
    })

    it('says no data is selected when nothing can be', async () => {
      const user = userEvent.setup()
      render(<InteractiveVisualizationDashboard datasetId="ds-1" columns={[columns[2]]} />)
      await user.click(screen.getByRole('tab', { name: /insights/i }))
      expect(screen.getByText(/shows no data selected/)).toBeInTheDocument()
    })
  })
})

