import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { getAuthToken } from '@/lib/auth-helpers'
import DatasetAnalysisPage from '@/app/explore/[id]/page'

const mockGetAuthToken = getAuthToken as jest.Mock

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
    isHydrated: true,
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
    DataPreviewTable: ({ datasetId, onExport }: any) => (
      <div data-testid="data-preview-table">
        DataPreviewTable for {datasetId}
        <button onClick={onExport}>Export</button>
      </div>
    )
  }
})

jest.mock('@/components/SchemaViewer', () => {
  return {
    SchemaViewer: ({ schema }: any) => (
      <div data-testid="schema-viewer">
        Schema: {schema?.column_count} columns
      </div>
    )
  }
})

jest.mock('@/components/StatisticsDashboard', () => {
  return {
    StatisticsDashboard: ({ datasetId, statistics }: any) => (
      <div data-testid="statistics-dashboard">
        Statistics for {datasetId}
      </div>
    )
  }
})

jest.mock('@/components/QualityReportCard', () => {
  return {
    QualityReportCard: ({ report }: any) => (
      <div data-testid="quality-report-card">
        Quality Score: {(report.overall_quality_score * 100).toFixed(1)}%
      </div>
    )
  }
})

// QualityDashboard (added to the quality tab in #102) does its own data fetch;
// stub it so the tab renders deterministically without hitting the network.
jest.mock('@/components/quality/QualityDashboard', () => ({
  QualityDashboard: ({ fileId }: any) => (
    <div data-testid="quality-dashboard">Quality dashboard for {fileId}</div>
  )
}))

jest.mock('@/components/AIInsightsPanel', () => {
  return {
    AIInsightsPanel: ({ datasetId }: any) => (
      <div data-testid="ai-insights-panel">
        AI Insights for {datasetId}
      </div>
    )
  }
})

// Records every `columns` array the page hands the dashboard, by reference, so
// a test can assert the identity is stable across re-renders (#346).
const mockColumnsProps: unknown[] = []

jest.mock('@/components/InteractiveVisualizationDashboard', () => {
  return {
    InteractiveVisualizationDashboard: ({ datasetId, columns }: { datasetId?: string; columns?: unknown }) => {
      mockColumnsProps.push(columns)
      return (
        <div
          data-testid="visualization-dashboard"
          data-dataset-id={datasetId ?? ''}
          data-columns={JSON.stringify(columns ?? null)}
        >
          Visualizations
        </div>
      )
    }
  }
})

jest.mock('@/components/ModelTrainingButton', () => {
  return {
    ModelTrainingButton: () => <div>Model Training</div>
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

// Radix tab triggers do not switch on a bare click() in JSDOM; they need the
// full pointer sequence (proven by the visualizations test above).
const activateTab = (name: RegExp) => {
  const tab = screen.getByRole('tab', { name })
  fireEvent.mouseDown(tab)
  fireEvent.mouseUp(tab)
  fireEvent.click(tab)
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
    ;(global.fetch as jest.Mock).mockReset()
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(mockProcessedDataset),
    })
  })

  afterEach(() => {
    jest.clearAllMocks()
    // Restore the default token resolution mocked globally in jest.setup.js
    mockGetAuthToken.mockResolvedValue('mock-token')
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

  it('normalizes a null dataset id from the API `_id` field (issue #170)', async () => {
    // The /user_data response carries the Mongo id as `_id` and leaves `id`
    // null; the page must normalize it so children (visualizations, preview)
    // receive a real id rather than null and can fetch real data.
    ;(global.fetch as jest.Mock).mockReset()
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        ...mockProcessedDataset,
        id: null,
        _id: 'real-mongo-id',
      }),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    // DataPreviewTable (overview tab) receives datasetId={dataset.id}.
    await waitFor(() => {
      expect(screen.getByTestId('data-preview-table')).toHaveTextContent(
        'DataPreviewTable for real-mongo-id'
      )
    }, { timeout: 3000 })
  })

  it('falls back to the route param when both id and _id are absent', async () => {
    ;(global.fetch as jest.Mock).mockReset()
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({ ...mockProcessedDataset, id: null }),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      // useParams() is mocked to id: 'test-dataset-id'
      expect(screen.getByTestId('data-preview-table')).toHaveTextContent(
        'DataPreviewTable for test-dataset-id'
      )
    }, { timeout: 3000 })
  })

  it('shows processing state for unprocessed datasets', async () => {
    // Metadata says unprocessed; the follow-up /data/process call is made but
    // returns non-ok so the dataset stays unprocessed and the processing UI
    // remains visible (previously the default mock flipped it to processed).
    ;(global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockUnprocessedDataset),
      })
      .mockResolvedValueOnce({ ok: false, status: 500 })

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

    // Overview tab content is visible by default
    expect(screen.getByTestId('data-preview-table')).toBeInTheDocument()

    activateTab(/schema/i)
    await waitFor(() => expect(screen.getByTestId('schema-viewer')).toBeInTheDocument())

    activateTab(/statistics/i)
    await waitFor(() => expect(screen.getByTestId('statistics-dashboard')).toBeInTheDocument())

    activateTab(/quality/i)
    await waitFor(() => expect(screen.getByTestId('quality-report-card')).toBeInTheDocument())

    activateTab(/ai insights/i)
    await waitFor(() => expect(screen.getByTestId('ai-insights-panel')).toBeInTheDocument())
  })

  it('handles export functionality', async () => {
    const exportResponse = {
      download_url: 'https://example.com/download/test.csv'
    }

    ;(global.fetch as jest.Mock)
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
    ;(global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockUnprocessedDataset),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockProcessedDataset),
      })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    // An unprocessed dataset triggers a POST to /data/process.
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

  it('shows an auth-required error when an unprocessed dataset is loaded without a token', async () => {
    // Null token + unprocessed dataset triggers the guard at page.tsx lines 106-108.
    mockGetAuthToken.mockResolvedValue(null)
    ;(global.fetch as jest.Mock).mockReset()
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(mockUnprocessedDataset),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(
        screen.getByText('Authentication required to process this dataset')
      ).toBeInTheDocument()
    })

    // The guard returns before any /data/process call is made.
    const processCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]) =>
      String(url).includes('/data/process')
    )
    expect(processCalls).toHaveLength(0)
  })

  it('hands the dashboard the same columns array across re-renders', async () => {
    // The dashboard keys its chart fetch on this prop. Built inline in the JSX it
    // was a fresh array every render, so the fetch effect re-ran, re-rendered and
    // re-fetched without end — the scatter/boxplot/line tabs sat on "Loading
    // visualization…" forever. Identity, not deep equality, is what matters.
    mockColumnsProps.length = 0

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    const activate = (name: RegExp) => {
      const tab = screen.getByRole('tab', { name })
      fireEvent.mouseDown(tab)
      fireEvent.mouseUp(tab)
      fireEvent.click(tab)
    }

    activate(/visualization/i)
    await waitFor(() => {
      expect(screen.getByTestId('visualization-dashboard')).toBeInTheDocument()
    })

    // Re-render the page (tab away and back) and check the same array comes through.
    activate(/schema/i)
    activate(/visualization/i)
    await waitFor(() => {
      expect(screen.getByTestId('visualization-dashboard')).toBeInTheDocument()
    })

    expect(mockColumnsProps.length).toBeGreaterThan(1)
    for (const columns of mockColumnsProps) {
      expect(columns).toBe(mockColumnsProps[0])
    }
  })

  it('maps schema column types when rendering the visualizations tab', async () => {
    // The wire shape is the backend's ColumnSchema (schema_inference.py):
    // canonical `data_type` (integer/float/currency/.../categorical/datetime),
    // `cardinality` instead of unique_count, and NO `type` field. Legacy
    // pandas-style `type` entries must still classify for older documents.
    const datasetWithTypedColumns = {
      ...mockProcessedDataset,
      schema: {
        row_count: 1000,
        column_count: 5,
        columns: [
          { name: 'age', data_type: 'integer', cardinality: 50, null_count: 0, nullable: false, unique: false, null_percentage: 0 },
          { name: 'price', data_type: 'currency', cardinality: 800, null_count: 2, nullable: true, unique: false, null_percentage: 0.2 },
          { name: 'city', data_type: 'categorical', cardinality: 10, null_count: 0, nullable: false, unique: false, null_percentage: 0 },
          { name: 'signup', data_type: 'datetime', cardinality: 900, null_count: 0, nullable: false, unique: false, null_percentage: 0 },
          { name: 'legacy_score', type: 'int64', unique_count: 42, null_count: 1 },
        ],
      },
    }

    ;(global.fetch as jest.Mock).mockReset()
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(datasetWithTypedColumns),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    // Activate the visualizations tab so its TabsContent (and the column-type
    // mapping at page.tsx lines 423-427) renders.
    const vizTab = screen.getByRole('tab', { name: /visualization/i })
    fireEvent.mouseDown(vizTab)
    fireEvent.mouseUp(vizTab)
    fireEvent.click(vizTab)

    await waitFor(() => {
      expect(screen.getByTestId('visualization-dashboard')).toBeInTheDocument()
    })

    const dashboard = screen.getByTestId('visualization-dashboard')
    const passedColumns = JSON.parse(dashboard.getAttribute('data-columns') ?? 'null')
    expect(passedColumns).toEqual([
      { name: 'age', type: 'numeric', unique_count: 50, null_count: 0 },
      { name: 'price', type: 'numeric', unique_count: 800, null_count: 2 },
      { name: 'city', type: 'categorical', unique_count: 10, null_count: 0 },
      { name: 'signup', type: 'datetime', unique_count: 900, null_count: 0 },
      { name: 'legacy_score', type: 'numeric', unique_count: 42, null_count: 1 },
    ])
  })

  it('handles API errors gracefully', async () => {
    ;(global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API Error'))
    
    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')
    
    await waitFor(() => {
      expect(screen.getByText('API Error')).toBeInTheDocument()
    })

    expect(screen.getByText('Back to Datasets')).toBeInTheDocument()
  })

  it('handles dataset not found', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
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
    // Keep the dataset unprocessed: metadata unprocessed + /data/process non-ok.
    ;(global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: jest.fn().mockResolvedValue(mockUnprocessedDataset),
      })
      .mockResolvedValueOnce({ ok: false, status: 500 })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('Export Data')).toBeInTheDocument()
    })

    // Export is gated on is_processed (disabled={!dataset.is_processed}).
    expect(screen.getByRole('button', { name: 'Export Data' })).toBeDisabled()
  })

  it('handles missing schema gracefully', async () => {
    const datasetWithoutSchema = {
      ...mockProcessedDataset,
      schema: null
    }

    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(datasetWithoutSchema),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    activateTab(/schema/i)
    await waitFor(() =>
      expect(screen.getByText('Schema information not available')).toBeInTheDocument()
    )
  })

  it('handles missing statistics gracefully', async () => {
    const datasetWithoutStats = {
      ...mockProcessedDataset,
      statistics: null
    }

    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(datasetWithoutStats),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    activateTab(/statistics/i)
    await waitFor(() =>
      expect(screen.getByText('Statistics not available')).toBeInTheDocument()
    )
  })

  it('handles missing quality report gracefully', async () => {
    const datasetWithoutQuality = {
      ...mockProcessedDataset,
      quality_report: null
    }

    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue(datasetWithoutQuality),
    })

    renderWithWorkflow(<DatasetAnalysisPage />, 'test-dataset-id')

    await waitFor(() => {
      expect(screen.getByText('test-dataset.csv')).toBeInTheDocument()
    }, { timeout: 3000 })

    activateTab(/quality/i)
    // QualityReportCard degrades to a fallback when quality_report is null.
    await waitFor(() =>
      expect(screen.getByText('Quality report not available')).toBeInTheDocument()
    )
  })
})