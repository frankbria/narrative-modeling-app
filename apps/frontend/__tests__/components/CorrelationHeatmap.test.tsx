import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { CorrelationHeatmap } from '@/components/CorrelationHeatmap'
import { StatItem } from '@/lib/utils'

const numericStat = (name: string): StatItem => ({
  field_name: name,
  field_type: 'numeric',
  count: 100,
  missing_values: 0,
  unique_values: 50,
  numeric_stats: { min: 0, max: 10, mean: 5, median: 5, mode: 0, std_dev: 1 },
})

// Regression (issue #166 review): the heatmap previously FABRICATED
// coefficients with Math.random() whenever 2+ numeric columns were present.
// It must render the backend-computed correlation_matrix, and render the
// empty state — never fake values — when no real matrix is available.
describe('CorrelationHeatmap', () => {
  it('renders the real coefficients from correlationMatrix', () => {
    render(
      <CorrelationHeatmap
        stats={[numericStat('age'), numericStat('income')]}
        correlationMatrix={{
          age: { age: 1.0, income: 0.75 },
          income: { age: 0.75, income: 1.0 },
        }}
      />
    )

    // 0.75 appears for both symmetric cells; 1.00 on the diagonal.
    expect(screen.getAllByText('0.75')).toHaveLength(2)
    expect(screen.getAllByText('1.00')).toHaveLength(2)
    expect(screen.getAllByText('age').length).toBeGreaterThanOrEqual(2) // row + column header
  })

  it('renders the empty state instead of fabricated values when no matrix is provided', () => {
    render(<CorrelationHeatmap stats={[numericStat('age'), numericStat('income')]} />)

    expect(
      screen.getByText(/no correlation data|not enough numeric columns/i)
    ).toBeInTheDocument()
    // No correlation cells: nothing that looks like a rendered coefficient.
    expect(document.querySelector('svg rect')).toBeNull()
  })
})
