import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { PRCurveChart } from '@/components/PRCurveChart'
import type { PRCurveData } from '@/lib/types/evaluation'

// Real recharts, with only ResponsiveContainer sized so jsdom's 0x0 layout
// doesn't blank the chart (#346). Everything asserted below is drawn by the
// real library, so a v3 prop/signature change fails here instead of passing
// through a passthrough mock.
jest.mock('recharts', () =>
  jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts()
)

/** One <Line> per class, as recharts actually drew it. */
const curves = (c: HTMLElement) => c.querySelectorAll('.recharts-line')

const referenceLines = (c: HTMLElement) =>
  Array.from(
    c.querySelectorAll('.recharts-reference-line line')
  ) as SVGLineElement[]

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
    const { container } = render(<PRCurveChart data={multiClassData} />)

    expect(curves(container)).toHaveLength(2)
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('b')).toBeInTheDocument()
  })

  it('renders a horizontal baseline reference line for a single-class curve', () => {
    const { container } = render(<PRCurveChart data={singleClassData} />)

    const [ref] = referenceLines(container)
    expect(ref).toBeDefined()
    // y=0.42 on the precision axis: a flat line, not a segment.
    expect(ref.getAttribute('y1')).toBe(ref.getAttribute('y2'))
  })

  it('places the baseline line according to its value', () => {
    // Guards the `y` prop actually reaching recharts: a higher baseline must
    // draw higher up the chart (smaller SVG y). A dropped/renamed prop pins
    // both renders to the same place.
    const at = (baseline: number) => {
      const { container, unmount } = render(
        <PRCurveChart
          data={{
            curves: { yes: [{ x: 0, y: 1 }, { x: 1, y: baseline }] },
            baseline_per_class: { yes: baseline },
          }}
        />
      )
      const y = Number(referenceLines(container)[0].getAttribute('y1'))
      unmount()
      return y
    }

    expect(at(0.9)).toBeLessThan(at(0.1))
  })

  it('omits baseline reference lines when there are multiple classes', () => {
    const { container } = render(<PRCurveChart data={multiClassData} />)

    expect(referenceLines(container)).toHaveLength(0)
  })

  it('renders a friendly placeholder when there are no curves', () => {
    const { container } = render(
      <PRCurveChart data={{ curves: {}, baseline_per_class: {} }} />
    )

    expect(
      screen.getByText(/no precision-recall curve data/i)
    ).toBeInTheDocument()
    expect(curves(container)).toHaveLength(0)
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
