import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ShapSummaryChart } from '@/components/ShapSummaryChart'
import type { RankedFeature } from '@/lib/types/evaluation'
import { axisTicks } from '@/__tests__/utils/sizedRecharts'

// Real recharts, with only ResponsiveContainer sized so jsdom's 0x0 layout
// doesn't blank the chart (#346). The bar order below is read off the real
// y-axis ticks, so it only holds if `dataKey="feature_name"` still resolves.
jest.mock('recharts', () =>
  jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts()
)

const FEATURES: RankedFeature[] = [
  { feature_name: 'age', importance: 0.1 },
  { feature_name: 'income', importance: 0.6 },
  { feature_name: 'score', importance: 0.3 },
]

describe('ShapSummaryChart', () => {
  it('renders the chart with the title and plain-language summary', () => {
    render(
      <ShapSummaryChart
        features={FEATURES}
        plainLanguage="income and score account for most of this model's decisions."
        explainerType="tree"
      />
    )
    expect(screen.getByTestId('shap-summary-chart')).toBeInTheDocument()
    expect(screen.getByText('SHAP Feature Impact')).toBeInTheDocument()
    expect(screen.getByTestId('shap-plain-language')).toHaveTextContent(
      'income and score'
    )
    expect(screen.getByText('tree explainer')).toBeInTheDocument()
  })

  it('sorts features by descending importance', () => {
    const { container } = render(<ShapSummaryChart features={FEATURES} />)
    expect(axisTicks(container, 'y')).toEqual(['income', 'score', 'age'])
    expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(3)
  })

  it('caps the number of bars when maxFeatures is set', () => {
    const { container } = render(
      <ShapSummaryChart features={FEATURES} maxFeatures={2} />
    )
    expect(axisTicks(container, 'y')).toEqual(['income', 'score'])
    expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(2)
  })

  it('shows an empty state when there are no features', () => {
    render(<ShapSummaryChart features={[]} />)
    expect(screen.getByTestId('shap-empty')).toBeInTheDocument()
  })

  it('omits the explainer badge when none is provided', () => {
    render(<ShapSummaryChart features={FEATURES} />)
    expect(screen.queryByText(/explainer$/)).not.toBeInTheDocument()
  })
})
