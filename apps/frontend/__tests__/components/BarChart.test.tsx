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
    Tooltip: passthrough,
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
})
