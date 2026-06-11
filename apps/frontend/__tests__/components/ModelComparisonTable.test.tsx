import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ModelComparisonTable } from '@/components/ModelComparisonTable'
import type { ModelEvaluationSummary } from '@/lib/types/evaluation'

const models: ModelEvaluationSummary[] = [
  {
    model_id: 'm1',
    name: 'Random Forest v1',
    algorithm: 'random_forest',
    problem_type: 'regression',
    cv_score: 0.82,
    test_score: 0.84,
    metrics: { r2: 0.84, mae: 3.2, rmse: 4.1 },
    created_at: '2026-06-10T00:00:00Z',
  },
  {
    model_id: 'm2',
    name: 'Linear v2',
    algorithm: 'linear_regression',
    problem_type: 'regression',
    cv_score: 0.79,
    test_score: 0.8,
    metrics: { r2: 0.8, mae: 2.9, rmse: 4.5 },
    created_at: '2026-06-09T00:00:00Z',
  },
]

describe('ModelComparisonTable', () => {
  it('renders a column per model with name and algorithm', () => {
    render(<ModelComparisonTable models={models} />)

    expect(screen.getByText('Random Forest v1')).toBeInTheDocument()
    expect(screen.getByText('Linear v2')).toBeInTheDocument()
    expect(screen.getByText('random_forest')).toBeInTheDocument()
    expect(screen.getByText('linear_regression')).toBeInTheDocument()
  })

  it('highlights the highest value for higher-is-better metrics', () => {
    render(<ModelComparisonTable models={models} />)

    // r2: m1 (0.84) beats m2 (0.80)
    expect(screen.getByTestId('cell-r2-m1')).toHaveAttribute('data-best', 'true')
    expect(screen.getByTestId('cell-r2-m2')).toHaveAttribute('data-best', 'false')
    // cv_score: m1 (0.82) beats m2 (0.79)
    expect(screen.getByTestId('cell-cv_score-m1')).toHaveAttribute('data-best', 'true')
    expect(screen.getByTestId('cell-cv_score-m2')).toHaveAttribute('data-best', 'false')
  })

  it('highlights the lowest value for lower-is-better metrics', () => {
    render(<ModelComparisonTable models={models} />)

    // mae: m2 (2.9) beats m1 (3.2)
    expect(screen.getByTestId('cell-mae-m2')).toHaveAttribute('data-best', 'true')
    expect(screen.getByTestId('cell-mae-m1')).toHaveAttribute('data-best', 'false')
    // rmse: m1 (4.1) beats m2 (4.5)
    expect(screen.getByTestId('cell-rmse-m1')).toHaveAttribute('data-best', 'true')
    expect(screen.getByTestId('cell-rmse-m2')).toHaveAttribute('data-best', 'false')
  })

  it('defaults unknown metrics to higher-is-better', () => {
    const withCustomMetric = models.map((m, idx) => ({
      ...m,
      metrics: { ...m.metrics, custom_metric: idx === 0 ? 0.5 : 0.9 },
    }))
    render(<ModelComparisonTable models={withCustomMetric} />)

    expect(screen.getByTestId('cell-custom_metric-m2')).toHaveAttribute(
      'data-best',
      'true'
    )
    expect(screen.getByTestId('cell-custom_metric-m1')).toHaveAttribute(
      'data-best',
      'false'
    )
  })

  it('renders a dash for metrics a model does not report', () => {
    const uneven = [
      models[0],
      { ...models[1], metrics: { r2: 0.8 } },
    ]
    render(<ModelComparisonTable models={uneven} />)

    expect(screen.getByTestId('cell-mae-m2')).toHaveTextContent('—')
    // The only reporting model is best by default.
    expect(screen.getByTestId('cell-mae-m1')).toHaveAttribute('data-best', 'true')
  })

  it('renders a placeholder when no models are provided', () => {
    render(<ModelComparisonTable models={[]} />)

    expect(screen.getByText(/no models to compare/i)).toBeInTheDocument()
  })
})
