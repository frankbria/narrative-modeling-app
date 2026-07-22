import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ROCCurveChart } from '@/components/ROCCurveChart'
import type { ROCCurveData } from '@/lib/types/evaluation'

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
    ReferenceLine: ({
      segment,
      y,
    }: {
      segment?: Array<{ x: number; y: number }>
      y?: number
    }) => (
      <div
        data-testid="reference-line"
        data-segment={segment ? JSON.stringify(segment) : undefined}
        data-y={y}
      />
    ),
  }
})

const data: ROCCurveData = {
  curves: {
    yes: [
      { x: 0, y: 0, threshold: 1 },
      { x: 0.1, y: 0.8, threshold: 0.5 },
      { x: 1, y: 1, threshold: 0 },
    ],
    no: [
      { x: 0, y: 0, threshold: 1 },
      { x: 0.2, y: 0.7, threshold: 0.5 },
      { x: 1, y: 1, threshold: 0 },
    ],
  },
  auc_per_class: { yes: 0.93, no: 0.88 },
  macro_auc: 0.905,
}

describe('ROCCurveChart', () => {
  it('renders one line per class with the AUC in the legend name', () => {
    render(<ROCCurveChart data={data} />)

    const lines = screen.getAllByTestId('curve-line')
    expect(lines).toHaveLength(2)
    expect(screen.getByText('yes (AUC 0.93)')).toBeInTheDocument()
    expect(screen.getByText('no (AUC 0.88)')).toBeInTheDocument()
  })

  it('renders a diagonal random-classifier reference line', () => {
    render(<ROCCurveChart data={data} />)

    const ref = screen.getByTestId('reference-line')
    expect(ref).toHaveAttribute(
      'data-segment',
      JSON.stringify([
        { x: 0, y: 0 },
        { x: 1, y: 1 },
      ])
    )
  })

  it('renders a friendly placeholder when there are no curves', () => {
    render(
      <ROCCurveChart data={{ curves: {}, auc_per_class: {}, macro_auc: null }} />
    )

    expect(screen.getByText(/no roc curve data/i)).toBeInTheDocument()
    expect(screen.queryAllByTestId('curve-line')).toHaveLength(0)
  })

  it('omits the AUC suffix when no AUC is available for a class', () => {
    render(
      <ROCCurveChart
        data={{
          curves: { yes: [{ x: 0, y: 0 }, { x: 1, y: 1 }] },
          auc_per_class: {},
          macro_auc: null,
        }}
      />
    )

    expect(screen.getByText('yes')).toBeInTheDocument()
  })

  it('exposes a role=img wrapper naming the classes and the dash channel (issue #282)', () => {
    render(
      <ROCCurveChart
        data={{
          curves: {
            yes: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
            no: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
          },
          auc_per_class: { yes: 0.9, no: 0.8 },
          macro_auc: null,
        }}
      />
    )

    const img = screen.getByRole('img')
    const label = img.getAttribute('aria-label') || ''
    expect(label).toContain('yes')
    expect(label).toContain('no')
    expect(label).toMatch(/dash pattern/i)
  })
})
