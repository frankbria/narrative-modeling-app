import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { FeatureSelection } from '@/components/FeatureSelection'
import { FeatureSelectionService } from '@/lib/services/featureSelection'
import type { MethodComparisonResponse } from '@/lib/services/featureSelection'

// --- Mocks -----------------------------------------------------------------

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { accessToken: 'mock-token' } })
}))

jest.mock('@/lib/services/featureSelection', () => {
  const actual = jest.requireActual('@/lib/services/featureSelection')
  return {
    ...actual,
    FeatureSelectionService: {
      getSelectedFeatures: jest.fn(),
      selectFeatures: jest.fn(),
      compareMethods: jest.fn()
    }
  }
})

// Mock radix Tabs as plain elements that always render their content so we can
// assert on the active tab (data-active) and on which panels are present.
jest.mock('@/components/ui/tabs', () => ({
  Tabs: ({ children, value }: any) => (
    <div data-testid="tabs" data-active={value}>
      {children}
    </div>
  ),
  TabsList: ({ children }: any) => <div>{children}</div>,
  TabsTrigger: ({ children, value, disabled }: any) => (
    <button data-testid={`tab-${value}`} disabled={disabled}>
      {children}
    </button>
  ),
  TabsContent: ({ children, value }: any) => (
    <div data-testid={`content-${value}`}>{children}</div>
  )
}))

jest.mock('@/components/SelectionControls', () => ({
  SelectionControls: ({ onRunSelection, onCompare }: any) => (
    <div>
      <button onClick={onRunSelection}>Run Selection</button>
      <button onClick={onCompare}>Compare Methods</button>
    </div>
  )
}))

jest.mock('@/components/FeatureImportanceChart', () => ({
  FeatureImportanceChart: () => <div data-testid="importance-chart" />
}))

jest.mock('@/components/SelectedFeatureSet', () => ({
  SelectedFeatureSet: () => <div data-testid="selected-feature-set" />
}))

jest.mock('@/components/MethodComparisonView', () => ({
  MethodComparisonView: ({ comparison }: any) => (
    <div data-testid="method-comparison-view">
      {comparison.results.length} methods
    </div>
  )
}))

const mockComparison: MethodComparisonResponse = {
  dataset_id: 'ds-1',
  results: [
    {
      method: 'correlation',
      selected_features: ['a', 'b'],
      top_features: [{ feature_name: 'a', score: 0.9, rank: 1, selected: true }],
      execution_time_ms: 100
    },
    {
      method: 'random_forest',
      selected_features: ['a', 'c'],
      top_features: [{ feature_name: 'a', score: 0.8, rank: 1, selected: true }],
      execution_time_ms: 200
    }
  ],
  consensus_features: ['a'],
  overlap_matrix: {},
  recommendations: 'rec'
}

const renderComponent = () =>
  render(
    <FeatureSelection
      datasetId="ds-1"
      columns={['a', 'b', 'c']}
      defaultTargetColumn="target"
    />
  )

describe('FeatureSelection', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(FeatureSelectionService.getSelectedFeatures as jest.Mock).mockResolvedValue({
      dataset_id: 'ds-1',
      selected_features: [],
      has_selection: false
    })
    ;(FeatureSelectionService.compareMethods as jest.Mock).mockResolvedValue(
      mockComparison
    )
  })

  it('renders all three tabs', () => {
    renderComponent()

    expect(screen.getByTestId('tab-configure')).toBeInTheDocument()
    expect(screen.getByTestId('tab-results')).toBeInTheDocument()
    expect(screen.getByTestId('tab-comparison')).toBeInTheDocument()
  })

  it('disables the comparison tab until a comparison has run', () => {
    renderComponent()

    expect(screen.getByTestId('tab-comparison')).toBeDisabled()
    expect(screen.queryByTestId('method-comparison-view')).not.toBeInTheDocument()
  })

  it('stores the full comparison response and switches to the comparison tab', async () => {
    renderComponent()

    fireEvent.click(screen.getByText('Compare Methods'))

    await waitFor(() => {
      expect(FeatureSelectionService.compareMethods).toHaveBeenCalledTimes(1)
    })

    await waitFor(() => {
      expect(screen.getByTestId('tab-comparison')).not.toBeDisabled()
    })

    expect(screen.getByTestId('tabs')).toHaveAttribute('data-active', 'comparison')
    const view = screen.getByTestId('method-comparison-view')
    expect(view).toHaveTextContent('2 methods')
  })

  it('surfaces an error when comparison fails', async () => {
    ;(FeatureSelectionService.compareMethods as jest.Mock).mockRejectedValue(
      new Error('Method comparison failed')
    )
    renderComponent()

    fireEvent.click(screen.getByText('Compare Methods'))

    await waitFor(() => {
      expect(screen.getByText('Method comparison failed')).toBeInTheDocument()
    })
    expect(screen.getByTestId('tab-comparison')).toBeDisabled()
  })
})
