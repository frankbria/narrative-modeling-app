import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ShapSummaryChart } from '@/components/ShapSummaryChart'
import type { RankedFeature } from '@/lib/types/evaluation'

// Recharts renders SVG that jsdom can't lay out; mock as passthrough divs and
// expose the data so we can assert what the chart was given (matches the
// pattern used by the other chart component tests).
jest.mock('recharts', () => {
  const passthrough = ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  )
  const BarChart = ({
    data,
    children,
  }: {
    data?: Array<{ feature_name: string }>
    children?: React.ReactNode
  }) => (
    <div data-testid="recharts-barchart" data-order={(data || []).map((d) => d.feature_name).join(',')}>
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
    render(<ShapSummaryChart features={FEATURES} />)
    expect(screen.getByTestId('recharts-barchart')).toHaveAttribute(
      'data-order',
      'income,score,age'
    )
  })

  it('caps the number of bars when maxFeatures is set', () => {
    render(<ShapSummaryChart features={FEATURES} maxFeatures={2} />)
    expect(screen.getByTestId('recharts-barchart')).toHaveAttribute(
      'data-order',
      'income,score'
    )
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
