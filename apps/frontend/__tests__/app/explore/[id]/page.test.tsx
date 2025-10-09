import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import DatasetAnalysisPage from '@/app/explore/[id]/page'

// Mock Next.js navigation
const mockPush = jest.fn()
const mockBack = jest.fn()

jest.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-dataset-id' }),
  useRouter: () => ({
    push: mockPush,
    back: mockBack,
  }),
  usePathname: () => '/explore/test-dataset-id',
}))

// Mock WorkflowContext with proper state
jest.mock('@/lib/contexts/WorkflowContext', () => ({
  WorkflowProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useWorkflow: () => ({
    state: {
      currentStage: 'DATA_PROFILING',
      completedStages: new Set(['DATA_LOADING']),
      stageData: {},
      datasetId: 'test-dataset-id'
    },
    canAccessStage: () => true,
    completeStage: jest.fn(),
    setCurrentStage: jest.fn(),
    setDatasetId: jest.fn(),
    resetWorkflow: jest.fn(),
    loadWorkflow: jest.fn(),
    saveWorkflow: jest.fn()
  })
}))

// Mock components
jest.mock('@/components/DataPreviewTable', () => {
  return {
    DataPreviewTable: ({ datasetId, onExport }) => (
      <div data-testid="data-preview-table">
        DataPreviewTable for {datasetId}
        <button onClick={onExport}>Export</button>
      </div>
    )
  }
})

jest.mock('@/components/SchemaViewer', () => {
  return {
    SchemaViewer: ({ schema }) => (
      <div data-testid="schema-viewer">
        Schema: {schema?.column_count} columns
      </div>
    )
  }
})

jest.mock('@/components/StatisticsDashboard', () => {
  return {
    StatisticsDashboard: ({ datasetId, statistics }) => (
      <div data-testid="statistics-dashboard">
        Statistics for {datasetId}
      </div>
    )
  }
})

jest.mock('@/components/QualityReportCard', () => {
  return {
    QualityReportCard: ({ report }) => (
      <div data-testid="quality-report-card">
        Quality Score: {(report.overall_quality_score * 100).toFixed(1)}%
      </div>
    )
  }
})

jest.mock('@/components/AIInsightsPanel', () => {
  return {
    AIInsightsPanel: ({ datasetId }) => (
      <div data-testid="ai-insights-panel">
        AI Insights for {datasetId}
      </div>
    )
  }
})

const mockProcessedDataset = {
  id: 'test-dataset-id',
  filename: 'test-dataset.csv',
  is_processed: true,
  schema: {
    row_count: 1000,
    column_count: 5,
    columns: ['id', 'name', 'age', 'email', 'city']
  },
  statistics: {
    row_count: 1000,
    column_count: 5,
    missing_values: 5
  },
  quality_report: {
    overall_quality_score: 0.85,
    dimensions: {}
  },
  data_preview: [],
  processed_at: '2023-12-01T10:00:00Z'
}

const mockUnprocessedDataset = {
  ...mockProcessedDataset,
  is_processed: false,
  processed_at: null
}

// Helper to render component (WorkflowProvider is mocked above)
const renderWithWorkflow = (component: React.ReactElement, datasetId?: string) => {
  return render(component)
}

describe('DatasetAnalysisPage', () => {
  beforeEach(() => {
    // Mock localStorage
    const localStorageMock = {
      getItem: jest.fn(),
      setItem: jest.fn(),
      removeItem: jest.fn(),
      clear: jest.fn(),
    }
    global.localStorage = localStorageMock as any

    // Reset fetch mock
    fetch.mockReset()
    fetch.mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(mockProcessedDataset),
    })
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it('renders loading state initially', () => {
    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    expect(screen.getByText('Loading dataset...')).toBeInTheDocument()
  })

  it('renders processed dataset correctly', async () => {
    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    expect(screen.getByText('Processed')).toBeInTheDocument()
    expect(screen.getByText('Export Data')).toBeInTheDocument()
    expect(screen.getByText('1,000')).toBeInTheDocument() // Row count
    expect(screen.getByText('5')).toBeInTheDocument() // Column count
    expect(screen.getByText('85.0%')).toBeInTheDocument() // Quality score
  })

  it('shows processing state for unprocessed datasets', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue(mockUnprocessedDataset),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    expect(screen.getByText('Processing...')).toBeInTheDocument()
    expect(screen.getByText('Processing Dataset')).toBeInTheDocument()
    expect(screen.getByText(/Analyzing schema, calculating statistics/)).toBeInTheDocument()
  })

  it('renders all tab sections for processed datasets', async () => {
    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Check tab triggers
    expect(screen.getByText('Overview')).toBeInTheDocument()
    expect(screen.getByText('Schema')).toBeInTheDocument()
    expect(screen.getByText('Statistics')).toBeInTheDocument()
    expect(screen.getByText('Quality')).toBeInTheDocument()
    expect(screen.getByText('AI Insights')).toBeInTheDocument()
  })

  it('switches between tabs correctly', async () => {
    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Check overview tab content is visible by default
    expect(screen.getByTestId('data-preview-table')).toBeInTheDocument()

    // Switch to schema tab
    fireEvent.click(screen.getByText('Schema'))
    expect(screen.getByTestId('schema-viewer')).toBeInTheDocument()

    // Switch to statistics tab
    fireEvent.click(screen.getByText('Statistics'))
    expect(screen.getByTestId('statistics-dashboard')).toBeInTheDocument()

    // Switch to quality tab
    fireEvent.click(screen.getByText('Quality'))
    expect(screen.getByTestId('quality-report-card')).toBeInTheDocument()

    // Switch to insights tab
    fireEvent.click(screen.getByText('AI Insights'))
    expect(screen.getByTestId('ai-insights-panel')).toBeInTheDocument()
  })

  it('handles export functionality', async () => {
    const exportResponse = {
      download_url: 'https://example.com/download/test.csv'
    }

    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockProcessedDataset),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(exportResponse),
      })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('Export Data')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Export Data'))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/data/test-dataset-id/export',
        expect.objectContaining({
          method: 'POST',
          headers: {
            Authorization: 'Bearer mock-token',
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ format: 'csv' })
        })
      )
    })

    expect(window.open).toHaveBeenCalledWith(exportResponse.download_url, '_blank')
  })

  it('starts processing for unprocessed datasets', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockUnprocessedDataset),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockProcessedDataset),
      })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('Processing...')).toBeInTheDocument()
    })

    // Should make API call to start processing
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/data/process',
        expect.objectContaining({
          method: 'POST',
          headers: {
            Authorization: 'Bearer mock-token',
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ file_id: 'test-dataset-id' })
        })
      )
    })
  })

  it('handles API errors gracefully', async () => {
    fetch.mockRejectedValueOnce(new Error('API Error'))
    
    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('API Error')).toBeInTheDocument()
    })

    expect(screen.getByText('Back to Datasets')).toBeInTheDocument()
  })

  it('handles dataset not found', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    })
    
    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('Failed to fetch dataset')).toBeInTheDocument()
    })
  })

  it('displays back navigation', async () => {
    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('Back')).toBeInTheDocument()
    })

    const backLink = screen.getByText('Back').closest('a')
    expect(backLink).toHaveAttribute('href', '/explore')
  })

  it('shows processing timestamp when available', async () => {
    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    expect(screen.getByText(/Processed 12\/1\/2023/)).toBeInTheDocument()
  })

  it('disables export button for unprocessed datasets', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue(mockUnprocessedDataset),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('Export Data')).toBeInTheDocument()
    })

    const exportButton = screen.getByText('Export Data')
    expect(exportButton).toBeDisabled()
  })

  it('handles missing schema gracefully', async () => {
    const datasetWithoutSchema = {
      ...mockProcessedDataset,
      schema: null
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue(datasetWithoutSchema),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    fireEvent.click(screen.getByText('Schema'))
    expect(screen.getByText('Schema information not available')).toBeInTheDocument()
  })

  it('handles missing statistics gracefully', async () => {
    const datasetWithoutStats = {
      ...mockProcessedDataset,
      statistics: null
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue(datasetWithoutStats),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    fireEvent.click(screen.getByText('Statistics'))
    expect(screen.getByText('Statistics not available')).toBeInTheDocument()
  })

  it('handles missing quality report gracefully', async () => {
    const datasetWithoutQuality = {
      ...mockProcessedDataset,
      quality_report: null
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue(datasetWithoutQuality),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    fireEvent.click(screen.getByText('Quality'))
    expect(screen.getByText('Quality report not available')).toBeInTheDocument()
  })
})