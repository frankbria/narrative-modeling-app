import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { LineChart, LineChartData } from '@/components/LineChart'

// Surface the recharts chart `onClick` prop as a real DOM click handler so we
// can exercise the onClick -> onPointClick adapter (LineChart.tsx lines 39-40).
jest.mock('recharts', () => {
  const passthrough = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
  const LineChart = ({ onClick, children }: { onClick?: (state: unknown) => void; children?: React.ReactNode }) => (
    <div data-testid="recharts-linechart" onClick={() => onClick?.({ activeLabel: '2024' })}>
      {children}
    </div>
  )
  return {
    LineChart,
    Line: passthrough,
    XAxis: passthrough,
    YAxis: passthrough,
    CartesianGrid: passthrough,
    Tooltip: passthrough,
    ResponsiveContainer: passthrough,
    Legend: passthrough,
    Brush: passthrough,
  }
})

const data: LineChartData = {
  data: [
    { x: '2023', sales: 100 },
    { x: '2024', sales: 150 },
  ],
  lines: [{ dataKey: 'sales', label: 'Sales' }],
  xLabel: 'Year',
  yLabel: 'Sales',
  title: 'Sales over time',
}

describe('LineChart', () => {
  it('renders the chart title', () => {
    render(<LineChart data={data} />)
    expect(screen.getByText('Sales over time')).toBeInTheDocument()
  })

  it('forwards a Record-shaped payload to onPointClick when the chart is clicked', () => {
    const onPointClick = jest.fn()
    render(<LineChart data={data} onPointClick={onPointClick} />)

    fireEvent.click(screen.getByTestId('recharts-linechart'))

    expect(onPointClick).toHaveBeenCalledTimes(1)
    expect(onPointClick).toHaveBeenCalledWith({ activeLabel: '2024' })
  })

  it('does not pass an onClick handler when onPointClick is omitted', () => {
    render(<LineChart data={data} />)
    expect(() => fireEvent.click(screen.getByTestId('recharts-linechart'))).not.toThrow()
  })
})
