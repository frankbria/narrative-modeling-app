import React from 'react'
import { render, screen } from '@testing-library/react'
import { QualityReportCard } from '@/components/QualityReportCard'

const mockQualityReport = {
  overall_quality_score: 0.85,
  dimension_scores: {
    completeness: 0.90,
    consistency: 0.88,
    accuracy: 0.82,
    validity: 0.87,
    uniqueness: 0.95,
    timeliness: 0.78
  },
  critical_issues: [
    {
      dimension: 'completeness',
      column: 'email',
      severity: 'medium' as const,
      description: 'Column "email" has 5% missing values',
      affected_rows: 50,
      affected_percentage: 5.0
    },
    {
      dimension: 'accuracy',
      column: 'age',
      severity: 'high' as const,
      description: 'Out-of-range values in "age" column',
      affected_rows: 25,
      affected_percentage: 2.5
    }
  ],
  warnings: [
    {
      dimension: 'consistency',
      column: 'created_at',
      severity: 'low' as const,
      description: 'Date format inconsistencies in "created_at" column',
      affected_rows: 100,
      affected_percentage: 10.0
    }
  ],
  recommendations: [
    'Consider implementing email validation',
    'Standardize date formats across all columns',
    'Review data entry processes for accuracy',
    'Set up automated data quality monitoring'
  ]
}

describe('QualityReportCard', () => {
  it('shows no score of its own: the dashboard owns the one score (#1172)', () => {
    render(<QualityReportCard report={mockQualityReport} />)

    expect(screen.queryByText('Data Quality Score')).not.toBeInTheDocument()
    expect(screen.queryByText('Quality Dimensions')).not.toBeInTheDocument()
    expect(screen.queryByText('85.0%')).not.toBeInTheDocument()
    expect(screen.queryAllByRole('progressbar')).toHaveLength(0)
  })

  it('displays quality issues when present', () => {
    render(<QualityReportCard report={mockQualityReport} />)

    expect(screen.getByText(/Column "email" has 5% missing values/)).toBeInTheDocument()
    expect(screen.getByText(/Out-of-range values in "age" column/)).toBeInTheDocument()
    expect(screen.getByText(/Date format inconsistencies/)).toBeInTheDocument()
    expect(screen.getByText('Critical Issues (2)')).toBeInTheDocument()
    expect(screen.getByText('Warnings (1)')).toBeInTheDocument()
  })

  it('displays recommendations section', () => {
    render(<QualityReportCard report={mockQualityReport} />)

    expect(screen.getByText('Recommendations')).toBeInTheDocument()
    expect(screen.getByText(/Consider implementing email validation/)).toBeInTheDocument()
    expect(screen.getByText(/Set up automated data quality monitoring/)).toBeInTheDocument()
  })

  it('renders nothing when there are no issues or recommendations', () => {
    const { container } = render(
      <QualityReportCard
        report={{ ...mockQualityReport, critical_issues: [], warnings: [], recommendations: [] }}
      />,
    )

    expect(container.textContent).toBe('')
  })
})
