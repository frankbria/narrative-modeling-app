import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { MethodComparisonView } from '@/components/MethodComparisonView'
import type { MethodComparisonResponse } from '@/lib/services/featureSelection'

const mockComparison: MethodComparisonResponse = {
  dataset_id: 'ds-1',
  results: [
    {
      method: 'correlation',
      selected_features: ['alpha', 'beta'],
      top_features: [
        { feature_name: 'alpha', score: 0.9, rank: 1, selected: true },
        { feature_name: 'beta', score: 0.5, rank: 2, selected: true }
      ],
      execution_time_ms: 120
    },
    {
      method: 'random_forest',
      selected_features: ['alpha', 'gamma'],
      top_features: [
        { feature_name: 'alpha', score: 0.8, rank: 1, selected: true },
        { feature_name: 'gamma', score: 0.4, rank: 2, selected: true }
      ],
      execution_time_ms: 340
    }
  ],
  consensus_features: ['alpha'],
  overlap_matrix: {
    correlation: { correlation: 2, random_forest: 1 },
    random_forest: { correlation: 1, random_forest: 2 }
  },
  recommendations: 'Use correlation for a fast first pass.'
}

describe('MethodComparisonView', () => {
  it('renders each compared method side-by-side', () => {
    render(<MethodComparisonView comparison={mockComparison} />)

    expect(screen.getByTestId('method-card-correlation')).toBeInTheDocument()
    expect(screen.getByTestId('method-card-random_forest')).toBeInTheDocument()

    const correlationCard = screen.getByTestId('method-card-correlation')
    expect(correlationCard).toHaveTextContent('Correlation')
    expect(correlationCard).toHaveTextContent('alpha')
    expect(correlationCard).toHaveTextContent('beta')
    expect(correlationCard).toHaveTextContent('2 features selected')
  })

  it('shows consensus features prominently', () => {
    render(<MethodComparisonView comparison={mockComparison} />)

    expect(screen.getByText('Consensus Features (1)')).toBeInTheDocument()
  })

  it('handles an empty consensus feature set', () => {
    render(
      <MethodComparisonView
        comparison={{ ...mockComparison, consensus_features: [] }}
      />
    )

    expect(screen.getByText('Consensus Features (0)')).toBeInTheDocument()
    expect(
      screen.getByText(/No features were selected by all methods/i)
    ).toBeInTheDocument()
  })

  it('renders the overlap matrix with numeric values', () => {
    render(<MethodComparisonView comparison={mockComparison} />)

    expect(screen.getByText('Feature Overlap Matrix')).toBeInTheDocument()
    // Diagonal values (2) and off-diagonal overlap (1) are present.
    expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('1').length).toBeGreaterThanOrEqual(2)
  })

  it('renders the recommendations text', () => {
    render(<MethodComparisonView comparison={mockComparison} />)

    expect(
      screen.getByText('Use correlation for a fast first pass.')
    ).toBeInTheDocument()
  })

  describe('CSV export', () => {
    let createObjectURLSpy: jest.Mock
    let revokeObjectURLSpy: jest.Mock
    let clickSpy: jest.SpyInstance
    let originalCreateObjectURL: typeof URL.createObjectURL
    let originalRevokeObjectURL: typeof URL.revokeObjectURL

    beforeEach(() => {
      originalCreateObjectURL = URL.createObjectURL
      originalRevokeObjectURL = URL.revokeObjectURL
      createObjectURLSpy = jest.fn(() => 'blob:mock-url')
      revokeObjectURLSpy = jest.fn()
      URL.createObjectURL = createObjectURLSpy as unknown as typeof URL.createObjectURL
      URL.revokeObjectURL = revokeObjectURLSpy as unknown as typeof URL.revokeObjectURL
      clickSpy = jest
        .spyOn(HTMLAnchorElement.prototype, 'click')
        .mockImplementation(() => {})
    })

    afterEach(() => {
      URL.createObjectURL = originalCreateObjectURL
      URL.revokeObjectURL = originalRevokeObjectURL
      clickSpy.mockRestore()
    })

    it('downloads a CSV and fires onExportCSV when export is clicked', () => {
      const onExportCSV = jest.fn()
      render(
        <MethodComparisonView comparison={mockComparison} onExportCSV={onExportCSV} />
      )

      fireEvent.click(screen.getByText('Export CSV').closest('button')!)

      expect(createObjectURLSpy).toHaveBeenCalledTimes(1)
      const blobArg = createObjectURLSpy.mock.calls[0][0] as Blob
      expect(blobArg).toBeInstanceOf(Blob)
      expect(blobArg.type).toBe('text/csv')
      expect(clickSpy).toHaveBeenCalledTimes(1)
      expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:mock-url')
      expect(onExportCSV).toHaveBeenCalledTimes(1)
    })
  })
})
