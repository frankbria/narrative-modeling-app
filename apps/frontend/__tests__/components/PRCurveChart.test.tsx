import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { PRCurveChart } from '@/components/PRCurveChart'
import type { PRCurveData } from '@/lib/types/evaluation'

// Recharts renders SVG that jsdom cannot lay out; mock it with passthrough
// divs that expose the props we assert on (BarChart.test.tsx pattern).
jest.mock('recharts', () => {
  const passthrough = ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  )
  return {
    ResponsiveContainer: passthrough,
    LineChart: passthrough,
    CartesianGrid: passthrough,
    XAxis: passthrough,
    YAxis: passthrough,
    Tooltip: passthrough,
    Legend: passthrough,
    Line: ({ name }: { name?: string }) => (
      <div data-testid="curve-line">{name}</div>
    ),
    ReferenceLine: ({ y }: { y?: number }) => (
      <div data-testid="reference-line" data-y={y} />
    ),
  }
})

const singleClassData: PRCurveData = {
  curves: {
    yes: [
      { x: 0, y: 1, threshold: 1 },
      { x: 0.8, y: 0.9, threshold: 0.5 },
      { x: 1, y: 0.42, threshold: 0 },
    ],
  },
  baseline_per_class: { yes: 0.42 },
}

const multiClassData: PRCurveData = {
  curves: {
    a: [{ x: 0, y: 1 }, { x: 1, y: 0.3 }],
    b: [{ x: 0, y: 1 }, { x: 1, y: 0.5 }],
  },
  baseline_per_class: { a: 0.3, b: 0.5 },
}

describe('PRCurveChart', () => {
  it('renders one line per class', () => {
    render(<PRCurveChart data={multiClassData} />)

    const lines = screen.getAllByTestId('curve-line')
    expect(lines).toHaveLength(2)
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('b')).toBeInTheDocument()
  })

  it('renders a horizontal baseline reference line for a single-class curve', () => {
    render(<PRCurveChart data={singleClassData} />)

    const ref = screen.getByTestId('reference-line')
    expect(ref).toHaveAttribute('data-y', '0.42')
  })

  it('omits baseline reference lines when there are multiple classes', () => {
    render(<PRCurveChart data={multiClassData} />)

    expect(screen.queryAllByTestId('reference-line')).toHaveLength(0)
  })

  it('renders a friendly placeholder when there are no curves', () => {
    render(<PRCurveChart data={{ curves: {}, baseline_per_class: {} }} />)

    expect(
      screen.getByText(/no precision-recall curve data/i)
    ).toBeInTheDocument()
    expect(screen.queryAllByTestId('curve-line')).toHaveLength(0)
  })

  it('exposes a role=img wrapper naming the classes and the dash channel (issue #282)', () => {
    render(<PRCurveChart data={multiClassData} />)

    const img = screen.getByRole('img')
    const label = img.getAttribute('aria-label') || ''
    expect(label).toContain('a')
    expect(label).toContain('b')
    expect(label).toMatch(/dash pattern/i)
  })
})
