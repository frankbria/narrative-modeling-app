import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { BarChart, BarChartData } from '@/components/BarChart'

// Surface the recharts chart `onClick` prop as a real DOM click handler so we
// can exercise the onClick -> onBarClick adapter (BarChart.tsx lines 78-79).
jest.mock('recharts', () => {
  const passthrough = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
  const BarChart = ({ onClick, children }: { onClick?: (state: unknown) => void; children?: React.ReactNode }) => (
    <div data-testid="recharts-barchart" onClick={() => onClick?.({ activeLabel: 'A' })}>
      {children}
    </div>
  )
  return {
    BarChart,
    Bar: passthrough,
    XAxis: passthrough,
    YAxis: passthrough,
    CartesianGrid: passthrough,
    // recharts clones the `content` element and injects active/payload/label.
    // Reproduce that so the tooltip's props are actually exercised — CustomTooltip
    // lives at module scope now (#373) and receives total/yLabel/showPercentages
    // as props rather than closing over them, which nothing else would catch.
    Tooltip: ({ content }: { content?: React.ReactElement }) =>
      content
        ? React.cloneElement(content, {
            active: true,
            payload: [{ value: 30, color: '#000' }],
            label: 'B',
          } as never)
        : null,
    ResponsiveContainer: passthrough,
  }
})

const data: BarChartData = {
  data: [
    { category: 'A', value: 10 },
    { category: 'B', value: 30 },
    { category: 'C', value: 20 },
  ],
  xLabel: 'Category',
  yLabel: 'Count',
  sortBy: 'value',
}

describe('BarChart', () => {
  it('renders the summary stats from the supplied data', () => {
    render(<BarChart data={data} />)

    expect(screen.getByText('Categories')).toBeInTheDocument()
    // total = 60, categories = 3, average = 20
    expect(screen.getByText('60')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('20.0')).toBeInTheDocument()
  })

  it('forwards a Record-shaped payload to onBarClick when the chart is clicked', () => {
    const onBarClick = jest.fn()
    render(<BarChart data={data} onBarClick={onBarClick} />)

    fireEvent.click(screen.getByTestId('recharts-barchart'))

    expect(onBarClick).toHaveBeenCalledTimes(1)
    expect(onBarClick).toHaveBeenCalledWith({ activeLabel: 'A' })
  })

  it('does not pass an onClick handler when onBarClick is omitted', () => {
    // No handler provided → adapter is undefined; clicking is a no-op (no throw).
    render(<BarChart data={data} />)
    expect(() => fireEvent.click(screen.getByTestId('recharts-barchart'))).not.toThrow()
  })

  // CustomTooltip moved to module scope in #373, so the values it used to close
  // over are threaded through as props. These assert that threading, and the
  // zero-total guard the move made necessary.
  describe('tooltip', () => {
    it('renders yLabel and the percentage of total from its props', () => {
      render(<BarChart data={{ ...data, showPercentages: true }} />)

      // total = 60, payload value = 30 → 50.0%
      expect(screen.getByText('Count: 30')).toBeInTheDocument()
      expect(screen.getByText('50.0% of total')).toBeInTheDocument()
    })

    it('omits the percentage line when showPercentages is not set', () => {
      render(<BarChart data={data} />)

      expect(screen.getByText('Count: 30')).toBeInTheDocument()
      expect(screen.queryByText(/% of total/)).not.toBeInTheDocument()
    })

    it('renders 0.0% rather than NaN% when every value is zero', () => {
      // total === 0 used to divide by zero and print "NaN% of total".
      const zeroData: BarChartData = {
        ...data,
        data: [
          { category: 'A', value: 0 },
          { category: 'B', value: 0 },
        ],
        showPercentages: true,
      }
      render(<BarChart data={zeroData} />)

      expect(screen.getByText('0.0% of total')).toBeInTheDocument()
      expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
    })
  })
})
