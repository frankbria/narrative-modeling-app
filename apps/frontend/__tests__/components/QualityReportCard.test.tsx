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
  it('renders overall quality score correctly', () => {
    render(<QualityReportCard report={mockQualityReport} />)
    
    expect(screen.getByText('Data Quality Score')).toBeInTheDocument()
    expect(screen.getByText('85.0%')).toBeInTheDocument() // Overall score
  })

  it('displays all quality dimensions with scores', () => {
    render(<QualityReportCard report={mockQualityReport} />)
    
    // Check that quality dimensions section exists
    expect(screen.getByText('Quality Dimensions')).toBeInTheDocument()
    
    // Check dimension scores without decimal (component uses toFixed(0))
    expect(screen.getByText('90%')).toBeInTheDocument() // Completeness
    expect(screen.getByText('88%')).toBeInTheDocument() // Consistency
    expect(screen.getByText('82%')).toBeInTheDocument() // Accuracy
    expect(screen.getByText('87%')).toBeInTheDocument() // Validity
    expect(screen.getByText('95%')).toBeInTheDocument() // Uniqueness
    expect(screen.getByText('78%')).toBeInTheDocument() // Timeliness
  })

  it('shows correct progress bar colors based on scores', () => {
    render(<QualityReportCard report={mockQualityReport} />)
    
    // Progress bars should be rendered for each dimension
    const progressBars = screen.getAllByRole('progressbar')
    expect(progressBars).toHaveLength(7) // 6 dimensions + 1 overall score progress bar
  })

  it('displays quality issues when present', () => {
    render(<QualityReportCard report={mockQualityReport} />)
    
    // Check for critical issues and warnings
    expect(screen.getByText(/Column "email" has 5% missing values/)).toBeInTheDocument()
    expect(screen.getByText(/Out-of-range values in "age" column/)).toBeInTheDocument()
    expect(screen.getByText(/Date format inconsistencies/)).toBeInTheDocument()
  })

  it('shows issues sections when present', () => {
    render(<QualityReportCard report={mockQualityReport} />)
    
    // Should show critical issues and warnings sections
    expect(screen.getByText('Critical Issues (2)')).toBeInTheDocument()
    expect(screen.getByText('Warnings (1)')).toBeInTheDocument()
  })

  it('displays recommendations section', () => {
    render(<QualityReportCard report={mockQualityReport} />)
    
    expect(screen.getByText('Recommendations')).toBeInTheDocument()
    expect(screen.getByText(/Consider implementing email validation/)).toBeInTheDocument()
    expect(screen.getByText(/Standardize date formats/)).toBeInTheDocument()
    expect(screen.getByText(/Review data entry processes/)).toBeInTheDocument()
    expect(screen.getByText(/Set up automated data quality monitoring/)).toBeInTheDocument()
  })

  it('handles missing issues gracefully', () => {
    const reportWithoutIssues = {
      overall_quality_score: 0.95,
      dimension_scores: {
        completeness: 0.95,
        consistency: 0.95
      },
      critical_issues: [],
      warnings: [],
      recommendations: []
    }
    
    render(<QualityReportCard report={reportWithoutIssues} />)
    
    expect(screen.getByText('95.0%')).toBeInTheDocument() // Overall score with 1 decimal
  })

  it('handles empty recommendations', () => {
    const reportWithoutRecommendations = {
      ...mockQualityReport,
      recommendations: []
    }
    
    render(<QualityReportCard report={reportWithoutRecommendations} />)
    
    // When recommendations are empty, the section should not render at all
    expect(screen.queryByText('Recommendations')).not.toBeInTheDocument()
  })

  it('applies correct styling for score ranges', () => {
    // Test with different score ranges
    const lowScoreReport = {
      overall_quality_score: 0.45,
      dimension_scores: {
        completeness: 0.40
      },
      critical_issues: [],
      warnings: [],
      recommendations: ['Fix issues']
    }
    
    render(<QualityReportCard report={lowScoreReport} />)
    
    expect(screen.getByText('45.0%')).toBeInTheDocument() // Overall score uses toFixed(1)
    expect(screen.getByText('40%')).toBeInTheDocument() // Dimension score uses toFixed(0)
  })

  it('formats percentages correctly', () => {
    const preciseScoreReport = {
      overall_quality_score: 0.8567,
      dimension_scores: {
        completeness: 0.9123
      },
      critical_issues: [],
      warnings: [],
      recommendations: []
    }
    
    render(<QualityReportCard report={preciseScoreReport} />)
    
    // Overall score should round to 1 decimal place, dimension to 0
    expect(screen.getByText('85.7%')).toBeInTheDocument() // Overall score
    expect(screen.getByText('91%')).toBeInTheDocument() // Dimension score
  })
})