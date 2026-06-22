import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ErrorAnalysisDashboard } from '@/components/ErrorAnalysisDashboard'
import { modelService } from '@/lib/services/model'
import type { ErrorAnalysisResponse } from '@/lib/types/evaluation'

jest.mock('@/lib/services/model', () => ({
  modelService: {
    getErrorAnalysis: jest.fn(),
  },
}))

const mockGet = modelService.getErrorAnalysis as jest.Mock

function fullAnalysis(): ErrorAnalysisResponse {
  return {
    model_id: 'm1',
    model_name: 'Churn',
    algorithm: 'Random Forest',
    problem_type: 'binary_classification',
    partial: false,
    distribution: {
      total_samples: 100,
      total_errors: 20,
      overall_error_rate: 0.2,
      per_class_error_rate: { A: 0.1, B: 0.35 },
    },
    confusion_pairs: [
      { actual: 'B', predicted: 'A', count: 12, rate: 0.3 },
      { actual: 'A', predicted: 'B', count: 8, rate: 0.1 },
    ],
    segments: [
      {
        feature: 'age',
        range_label: 'age in [18.00, 25.00)',
        lower: 18,
        upper: 25,
        error_rate: 0.6,
        error_count: 9,
        sample_count: 15,
      },
    ],
    clusters: [
      { cluster_id: 0, size: 12, characteristics: ['low age'], dominant_confusion: 'B→A' },
    ],
    patterns: [
      { rule: 'age <= 25.00', error_rate: 0.6, error_count: 9, sample_count: 15 },
    ],
    cases: [
      { index: 3, actual: 'B', predicted: 'A', confidence: 0.9, top_features: { age: 20 } },
      { index: 7, actual: 'A', predicted: 'B', confidence: 0.7, top_features: { age: 40 } },
    ],
    suggestions: ['Add features to distinguish B from A.'],
    suggestions_generated_by: 'fallback',
    message: null,
    evaluated_at: '2026-06-21T00:00:00Z',
  }
}

describe('ErrorAnalysisDashboard', () => {
  beforeEach(() => jest.clearAllMocks())

  it('renders distribution, confusion pairs, segments, patterns and cases', async () => {
    mockGet.mockResolvedValue(fullAnalysis())
    render(<ErrorAnalysisDashboard modelId="m1" />)

    expect(await screen.findByTestId('error-analysis-dashboard')).toBeInTheDocument()
    expect(mockGet).toHaveBeenCalledWith('m1')
    // Overview: total errors + rate
    expect(screen.getByText('20')).toBeInTheDocument()
    expect(screen.getByText('20.0%')).toBeInTheDocument()
    // Sections
    expect(screen.getByText('Commonly Confused Classes')).toBeInTheDocument()
    expect(screen.getByText('High-Error Feature Segments')).toBeInTheDocument()
    expect(screen.getByText('Error Patterns')).toBeInTheDocument()
    expect(screen.getByText('age <= 25.00')).toBeInTheDocument()
    expect(screen.getByText('Add features to distinguish B from A.')).toBeInTheDocument()
  })

  it('filters error cases when a confusion pair is clicked', async () => {
    mockGet.mockResolvedValue(fullAnalysis())
    render(<ErrorAnalysisDashboard modelId="m1" />)

    await screen.findByTestId('error-analysis-dashboard')
    expect(screen.getByText('2 cases shown')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /B → A/ }))
    await waitFor(() =>
      expect(screen.getByText('1 cases shown')).toBeInTheDocument()
    )
  })

  it('shows the partial message and omits feature-matrix sections', async () => {
    const partial = fullAnalysis()
    partial.partial = true
    partial.segments = []
    partial.clusters = []
    partial.patterns = []
    partial.message = 'No stored feature matrix.'
    mockGet.mockResolvedValue(partial)

    render(<ErrorAnalysisDashboard modelId="m1" />)
    await screen.findByTestId('error-analysis-dashboard')

    expect(screen.getByText('No stored feature matrix.')).toBeInTheDocument()
    expect(screen.queryByText('High-Error Feature Segments')).not.toBeInTheDocument()
    expect(screen.queryByText('Error Patterns')).not.toBeInTheDocument()
    // Confusion pairs + cases still render.
    expect(screen.getByText('Commonly Confused Classes')).toBeInTheDocument()
  })

  it('renders an error state on fetch failure', async () => {
    mockGet.mockRejectedValue(new Error('boom'))
    render(<ErrorAnalysisDashboard modelId="m1" />)
    expect(await screen.findByTestId('error-analysis-error')).toHaveTextContent('boom')
  })
})
