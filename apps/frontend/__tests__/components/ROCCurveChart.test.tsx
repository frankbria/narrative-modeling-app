import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ROCCurveChart } from '@/components/ROCCurveChart'
import type { ROCCurveData } from '@/lib/types/evaluation'

// Real recharts, with only ResponsiveContainer sized so jsdom's 0x0 layout
// doesn't blank the chart (#346). Everything asserted below is drawn by the
// real library, so a v3 prop/signature change fails here instead of passing
// through a passthrough mock.
jest.mock('recharts', () =>
  jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts()
)

/** One <Line> per class, as recharts actually drew it. */
const curves = (c: HTMLElement) => c.querySelectorAll('.recharts-line')

/**
 * The `d` of each drawn curve. A `dataKey` that stops resolving leaves the
 * <Line> element in place but drops its path entirely, so this is what makes
 * the suite sensitive to the data actually reaching recharts.
 */
const curvePaths = (c: HTMLElement) =>
  Array.from(c.querySelectorAll('.recharts-line-curve')).map((el) =>
    el.getAttribute('d')
  )

const referenceLine = (c: HTMLElement) =>
  c.querySelector('.recharts-reference-line line') as SVGLineElement | null

const coords = (line: SVGLineElement) =>
  (['x1', 'y1', 'x2', 'y2'] as const).map((a) => Number(line.getAttribute(a)))

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
    const { container } = render(<ROCCurveChart data={data} />)

    expect(curves(container)).toHaveLength(2)
    expect(screen.getByText('yes (AUC 0.93)')).toBeInTheDocument()
    expect(screen.getByText('no (AUC 0.88)')).toBeInTheDocument()
  })

  it('plots each curve from the x/y data keys', () => {
    const { container } = render(<ROCCurveChart data={data} />)

    const paths = curvePaths(container)
    expect(paths).toHaveLength(2)
    for (const d of paths) {
      expect(d).toMatch(/^M[\d.]+,[\d.]+[CL]/)
    }
    // The two classes have different curves, so they must not draw identically.
    expect(paths[0]).not.toEqual(paths[1])
  })

  it('renders a diagonal random-classifier reference line', () => {
    const { container } = render(<ROCCurveChart data={data} />)

    const ref = referenceLine(container)
    expect(ref).not.toBeNull()
    // segment [{x:0,y:0} -> {x:1,y:1}] in chart space: left-to-right and, since
    // SVG y grows downward, bottom-to-top.
    const [x1, y1, x2, y2] = coords(ref!)
    expect(x2).toBeGreaterThan(x1)
    expect(y2).toBeLessThan(y1)
  })

  it('renders a friendly placeholder when there are no curves', () => {
    const { container } = render(
      <ROCCurveChart data={{ curves: {}, auc_per_class: {}, macro_auc: null }} />
    )

    expect(screen.getByText(/no roc curve data/i)).toBeInTheDocument()
    expect(curves(container)).toHaveLength(0)
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
