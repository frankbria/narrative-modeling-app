import React from 'react'
import { render, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { FeatureImportanceChart } from '@/components/FeatureImportanceChart'
import { ScatterPlotChart } from '@/components/ScatterPlotChart'
import type { FeatureScore } from '@/lib/services/featureSelection'

// The two components recharts 3 actually broke (#346). Neither had any test.
//
// Scope note, so these are not read as more than they are: the v3 breakage was
// **type-level only**. `Bar`/`Scatter` now type their onClick argument as
// BarRectangleItem / ScatterPointItem, which stopped compiling (TS2345) — but at
// runtime v3 spreads the datum's own fields onto that item, so reading the
// argument directly and reading `.payload` produce the same values. Verified:
// mutating the adapters back to the v2 shape leaves these tests green. **`tsc` is
// the only gate that catches that regression**, which is why the migration commit
// leans on it.
//
// What these do cover, and nothing did before: the bars/points render and are
// clickable under v3, each adapter fires exactly once with the datum's fields,
// and omitting the callback is a safe no-op.
jest.mock('recharts', () =>
  jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts()
)

const FEATURES: FeatureScore[] = [
  { feature_name: 'age', score: 0.9, rank: 1, selected: true },
  { feature_name: 'tenure', score: 0.4, rank: 2, selected: false },
]

describe('FeatureImportanceChart', () => {
  it('hands onFeatureClick the datum, not the recharts event object', () => {
    const onFeatureClick = jest.fn()
    const { container } = render(
      <FeatureImportanceChart features={FEATURES} onFeatureClick={onFeatureClick} />
    )

    const bars = container.querySelectorAll('.recharts-bar-rectangle')
    expect(bars).toHaveLength(2)

    fireEvent.click(bars[0])

    expect(onFeatureClick).toHaveBeenCalledTimes(1)
    expect(onFeatureClick.mock.calls[0][0]).toMatchObject({
      feature_name: expect.any(String),
      score: expect.any(Number),
    })
  })

  it('does nothing when no onFeatureClick is supplied', () => {
    const { container } = render(<FeatureImportanceChart features={FEATURES} />)
    const bar = container.querySelector('.recharts-bar-rectangle')!
    expect(() => fireEvent.click(bar)).not.toThrow()
  })
})

describe('ScatterPlotChart', () => {
  const data = {
    data: [
      { x: 1, y: 2, label: 'a' },
      { x: 3, y: 4, label: 'b' },
    ],
    xLabel: 'x',
    yLabel: 'y',
  }

  it('hands onPointClick the datum, not the recharts event object', () => {
    const onPointClick = jest.fn()
    const { container } = render(
      <ScatterPlotChart data={data} onPointClick={onPointClick} />
    )

    const points = container.querySelectorAll('.recharts-scatter-symbol')
    expect(points.length).toBeGreaterThan(0)

    fireEvent.click(points[0])

    expect(onPointClick).toHaveBeenCalledTimes(1)
    expect(onPointClick.mock.calls[0][0]).toMatchObject({
      x: expect.any(Number),
      y: expect.any(Number),
    })
  })

  it('does nothing when no onPointClick is supplied', () => {
    const { container } = render(<ScatterPlotChart data={data} />)
    const point = container.querySelector('.recharts-scatter-symbol')!
    expect(() => fireEvent.click(point)).not.toThrow()
  })
})
