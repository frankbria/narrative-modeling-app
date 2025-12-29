import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import DashboardPage from '@/app/dashboard/page';
import { WorkflowStage, WORKFLOW_STAGES } from '@/lib/types/workflow';

// Mock the router
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
  }),
}));

// Mock auth helpers
jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('mock-token'),
}));

// Mock constants
jest.mock('@/lib/constants', () => ({
  API_URL: 'http://localhost:8000/api/v1',
}));

// Create mock workflow context
const createMockWorkflowState = (overrides = {}) => ({
  currentStage: WorkflowStage.DATA_LOADING,
  completedStages: new Set<WorkflowStage>(),
  stageData: {} as Record<WorkflowStage, unknown>,
  datasetId: undefined,
  modelId: undefined,
  ...overrides,
});

const mockCanAccessStage = jest.fn((stage: WorkflowStage) => {
  // By default, only first stage is accessible
  return stage === WorkflowStage.DATA_LOADING;
});

const mockWorkflowContext = {
  state: createMockWorkflowState(),
  canAccessStage: mockCanAccessStage,
  completeStage: jest.fn(),
  setCurrentStage: jest.fn(),
  setDatasetId: jest.fn(),
  resetWorkflow: jest.fn(),
  loadWorkflow: jest.fn(),
  saveWorkflow: jest.fn(),
  updateHistoryPosition: jest.fn(),
  updateHistoryState: jest.fn(),
  refreshHistory: jest.fn(),
};

jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => mockWorkflowContext,
}));

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Sample test data
const mockDatasets = [
  {
    dataset_id: 'ds-1',
    filename: 'sales_data.csv',
    num_rows: 10000,
    num_columns: 15,
    created_at: new Date().toISOString(),
  },
  {
    dataset_id: 'ds-2',
    filename: 'customer_churn.csv',
    num_rows: 5000,
    num_columns: 20,
    created_at: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
  },
];

const mockModels = [
  {
    model_id: 'model-1',
    name: 'Churn Predictor',
    algorithm: 'Random Forest',
    status: 'trained',
    test_score: 0.85,
    created_at: new Date().toISOString(),
  },
  {
    model_id: 'model-2',
    name: 'Sales Forecaster',
    algorithm: 'XGBoost',
    status: 'deployed',
    test_score: 0.92,
    created_at: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
  },
];

describe('DashboardPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
    mockWorkflowContext.state = createMockWorkflowState();
    mockCanAccessStage.mockImplementation((stage: WorkflowStage) =>
      stage === WorkflowStage.DATA_LOADING
    );
  });

  describe('Rendering', () => {
    it('renders the dashboard page with correct structure', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      expect(screen.getByTestId('dashboard')).toBeInTheDocument();
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.getByText(/Welcome to Narrative Modeling/)).toBeInTheDocument();
    });

    it('renders workflow progress section', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      expect(screen.getByTestId('workflow-progress')).toBeInTheDocument();
      expect(screen.getByText('Workflow Progress')).toBeInTheDocument();
      expect(screen.getByText(/0 of 8 stages completed/)).toBeInTheDocument();
    });

    it('renders navigation cards for all workflow stages', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      expect(screen.getByTestId('navigation-cards')).toBeInTheDocument();

      // Navigation cards contain all workflow stages - check within the navigation section
      const navCards = screen.getByTestId('navigation-cards');
      WORKFLOW_STAGES.forEach((stage) => {
        // Use getAllByText since stage names may appear in multiple places
        const elements = within(navCards).getAllByText(stage.name);
        expect(elements.length).toBeGreaterThan(0);
      });
    });

    it('renders recent datasets section', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      expect(screen.getByTestId('recent-datasets')).toBeInTheDocument();
      expect(screen.getByText('Recent Datasets')).toBeInTheDocument();
    });

    it('renders recent models section', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      expect(screen.getByTestId('recent-models')).toBeInTheDocument();
      expect(screen.getByText('Recent Models')).toBeInTheDocument();
    });
  });

  describe('Workflow Progress Calculation', () => {
    it('shows 0% progress when no stages are completed', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      expect(screen.getByText(/0 of 8 stages completed/)).toBeInTheDocument();
    });

    it('shows correct progress when some stages are completed', async () => {
      mockWorkflowContext.state = createMockWorkflowState({
        completedStages: new Set([
          WorkflowStage.DATA_LOADING,
          WorkflowStage.DATA_PROFILING,
        ]),
      });

      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      expect(screen.getByText(/2 of 8 stages completed/)).toBeInTheDocument();
    });

    it('shows 100% progress when all stages are completed', async () => {
      mockWorkflowContext.state = createMockWorkflowState({
        completedStages: new Set(WORKFLOW_STAGES.map((s) => s.id)),
      });

      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      expect(screen.getByText(/8 of 8 stages completed/)).toBeInTheDocument();
    });

    it('displays completed stages with green styling', async () => {
      mockWorkflowContext.state = createMockWorkflowState({
        completedStages: new Set([WorkflowStage.DATA_LOADING]),
        currentStage: WorkflowStage.DATA_PROFILING,
      });

      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      // Find within workflow progress section
      const workflowProgress = screen.getByTestId('workflow-progress');
      const dataLoadingBadge = within(workflowProgress).getByText('Data Loading').closest('div');
      expect(dataLoadingBadge).toHaveClass('bg-green-100', 'text-green-800');
    });

    it('displays current stage with blue styling', async () => {
      mockWorkflowContext.state = createMockWorkflowState({
        currentStage: WorkflowStage.DATA_PROFILING,
        completedStages: new Set([WorkflowStage.DATA_LOADING]),
      });

      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      // Find within workflow progress section
      const workflowProgress = screen.getByTestId('workflow-progress');
      const profilingBadge = within(workflowProgress).getByText('Data Profiling').closest('div');
      expect(profilingBadge).toHaveClass('bg-blue-100', 'text-blue-800');
    });
  });

  describe('Dataset Fetching States', () => {
    it('shows loading state while fetching datasets', async () => {
      let resolvePromise: (value: unknown) => void;
      const fetchPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return fetchPromise;
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      // Check for loading skeleton in datasets section
      const datasetsSection = screen.getByTestId('recent-datasets');
      expect(within(datasetsSection).getAllByClassName ? true : datasetsSection.querySelector('.animate-pulse')).toBeTruthy();

      // Resolve the promise
      resolvePromise!({
        ok: true,
        json: () => Promise.resolve({ datasets: [] }),
      });
    });

    it('shows datasets when fetch succeeds', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: mockDatasets }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('sales_data.csv')).toBeInTheDocument();
        expect(screen.getByText('customer_churn.csv')).toBeInTheDocument();
      });
    });

    it('shows error state when dataset fetch fails', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: false,
            status: 500,
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Unable to load datasets')).toBeInTheDocument();
      });
    });

    it('shows empty state when no datasets exist', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('No datasets yet')).toBeInTheDocument();
        expect(screen.getByText('Upload Dataset')).toBeInTheDocument();
      });
    });

    it('handles malformed API response for datasets', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: 'not-an-array' }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Unable to load datasets')).toBeInTheDocument();
      });
    });

    it('handles null API response for datasets', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(null),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Unable to load datasets')).toBeInTheDocument();
      });
    });
  });

  describe('Model Fetching States', () => {
    it('shows loading state while fetching models', async () => {
      let resolvePromise: (value: unknown) => void;
      const fetchPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return fetchPromise;
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      // Check for loading skeleton in models section
      const modelsSection = screen.getByTestId('recent-models');
      expect(modelsSection.querySelector('.animate-pulse')).toBeTruthy();

      // Resolve the promise
      resolvePromise!({
        ok: true,
        json: () => Promise.resolve({ models: [] }),
      });
    });

    it('shows models when fetch succeeds', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Churn Predictor')).toBeInTheDocument();
        expect(screen.getByText('Sales Forecaster')).toBeInTheDocument();
      });
    });

    it('shows error state when model fetch fails', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: false,
            status: 500,
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Unable to load models')).toBeInTheDocument();
      });
    });

    it('shows empty state when no models exist', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('No models trained yet')).toBeInTheDocument();
      });
    });

    it('handles malformed API response for models', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: { invalid: 'format' } }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Unable to load models')).toBeInTheDocument();
      });
    });

    it('displays model status with appropriate styling', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        const trainedBadge = screen.getByText('trained');
        expect(trainedBadge).toHaveClass('bg-green-100', 'text-green-800');

        const deployedBadge = screen.getByText('deployed');
        expect(deployedBadge).toHaveClass('bg-blue-100', 'text-blue-800');
      });
    });

    it('displays model test scores', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('85.0%')).toBeInTheDocument();
        expect(screen.getByText('92.0%')).toBeInTheDocument();
      });
    });
  });

  describe('Navigation Card Interactions', () => {
    it('navigates to upload page when clicking accessible stage', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      const uploadCard = screen.getByRole('button', { name: /Data Loading.*Upload and connect your data sources/i });
      fireEvent.click(uploadCard);

      expect(mockPush).toHaveBeenCalledWith('/upload');
    });

    it('does not navigate when clicking inaccessible stage', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      const profilingCard = screen.getByRole('button', { name: /Data Profiling.*locked/i });
      fireEvent.click(profilingCard);

      expect(mockPush).not.toHaveBeenCalled();
    });

    it('supports keyboard navigation for accessible stages', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      const uploadCard = screen.getByRole('button', { name: /Data Loading.*Upload and connect your data sources/i });
      fireEvent.keyDown(uploadCard, { key: 'Enter' });

      expect(mockPush).toHaveBeenCalledWith('/upload');
    });

    it('does not navigate on Enter for inaccessible stages', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      const profilingCard = screen.getByRole('button', { name: /Data Profiling.*locked/i });
      fireEvent.keyDown(profilingCard, { key: 'Enter' });

      expect(mockPush).not.toHaveBeenCalled();
    });

    it('shows lock icon for inaccessible stages', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      // The aria-label should indicate locked state
      const lockedCards = screen.getAllByRole('button', { name: /locked/i });
      expect(lockedCards.length).toBeGreaterThan(0);
    });

    it('sets correct tabIndex based on accessibility', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      const uploadCard = screen.getByRole('button', { name: /Data Loading.*Upload and connect your data sources/i });
      expect(uploadCard).toHaveAttribute('tabIndex', '0');

      const profilingCard = screen.getByRole('button', { name: /Data Profiling.*locked/i });
      expect(profilingCard).toHaveAttribute('tabIndex', '-1');
    });

    it('navigates with dataset ID for non-upload stages', async () => {
      mockWorkflowContext.state = createMockWorkflowState({
        datasetId: 'test-dataset-123',
        completedStages: new Set([WorkflowStage.DATA_LOADING]),
        currentStage: WorkflowStage.DATA_PROFILING,
      });

      mockCanAccessStage.mockImplementation((stage: WorkflowStage) =>
        stage === WorkflowStage.DATA_LOADING || stage === WorkflowStage.DATA_PROFILING
      );

      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      const profilingCard = screen.getByRole('button', { name: /Data Profiling.*Explore and understand your data/i });
      fireEvent.click(profilingCard);

      expect(mockPush).toHaveBeenCalledWith('/explore/test-dataset-123');
    });
  });

  describe('Quick Action Button States', () => {
    it('enables Upload New Dataset button always', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      const uploadButton = screen.getByRole('button', { name: /Upload New Dataset/i });
      expect(uploadButton).not.toBeDisabled();
    });

    it('disables Train Model quick action button when no datasets exist', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      // Wait for loading to complete (empty state shows)
      await waitFor(() => {
        expect(screen.getByText('No datasets yet')).toBeInTheDocument();
      });

      // Get all Train Model buttons and find the one in Quick Actions (first one)
      const trainButtons = screen.getAllByRole('button', { name: /Train Model/i });
      // The first one is the quick action button
      expect(trainButtons[0]).toBeDisabled();
    });

    it('enables Train Model quick action button when datasets exist', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: mockDatasets }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      // Wait for datasets to load
      await waitFor(() => {
        expect(screen.getByText('sales_data.csv')).toBeInTheDocument();
      });

      // Get all Train Model buttons and find the one in Quick Actions (first one)
      const trainButtons = screen.getAllByRole('button', { name: /Train Model/i });
      expect(trainButtons[0]).not.toBeDisabled();
    });

    it('disables View Deployments button when no deployed models', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: [{ ...mockModels[0], status: 'trained' }] }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      // Wait for models to load
      await waitFor(() => {
        expect(screen.getByText('Churn Predictor')).toBeInTheDocument();
      });

      const deployButton = screen.getByRole('button', { name: /View Deployments/i });
      expect(deployButton).toBeDisabled();
    });

    it('enables View Deployments button when deployed models exist', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }), // includes deployed model
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      // Wait for models to load
      await waitFor(() => {
        expect(screen.getByText('Sales Forecaster')).toBeInTheDocument();
      });

      const deployButton = screen.getByRole('button', { name: /View Deployments/i });
      expect(deployButton).not.toBeDisabled();
    });

    it('navigates when clicking Upload New Dataset button', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      const uploadButton = screen.getByRole('button', { name: /Upload New Dataset/i });
      fireEvent.click(uploadButton);

      expect(mockPush).toHaveBeenCalledWith('/upload');
    });
  });

  describe('Error Retry Functionality', () => {
    it('shows Retry button when datasets fetch fails', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({ ok: false, status: 500 });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        const datasetsSection = screen.getByTestId('recent-datasets');
        expect(within(datasetsSection).getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });
    });

    it('retries datasets fetch when Retry button is clicked', async () => {
      let fetchCount = 0;
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          fetchCount++;
          if (fetchCount === 1) {
            return Promise.resolve({ ok: false, status: 500 });
          }
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: mockDatasets }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Unable to load datasets')).toBeInTheDocument();
      });

      const datasetsSection = screen.getByTestId('recent-datasets');
      const retryButton = within(datasetsSection).getByRole('button', { name: /Retry/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByText('sales_data.csv')).toBeInTheDocument();
      });
    });

    it('shows Retry button when models fetch fails', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({ ok: false, status: 500 });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        const modelsSection = screen.getByTestId('recent-models');
        expect(within(modelsSection).getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });
    });

    it('retries models fetch when Retry button is clicked', async () => {
      let fetchCount = 0;
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          fetchCount++;
          if (fetchCount === 1) {
            return Promise.resolve({ ok: false, status: 500 });
          }
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Unable to load models')).toBeInTheDocument();
      });

      const modelsSection = screen.getByTestId('recent-models');
      const retryButton = within(modelsSection).getByRole('button', { name: /Retry/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.getByText('Churn Predictor')).toBeInTheDocument();
      });
    });
  });

  describe('Dataset Item Interactions', () => {
    it('navigates to explore page when clicking a dataset', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: mockDatasets }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('sales_data.csv')).toBeInTheDocument();
      });

      const datasetItem = screen.getByText('sales_data.csv').closest('[role="button"]');
      fireEvent.click(datasetItem!);

      expect(mockPush).toHaveBeenCalledWith('/explore/ds-1');
    });

    it('supports keyboard navigation on dataset items', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: mockDatasets }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('sales_data.csv')).toBeInTheDocument();
      });

      const datasetItem = screen.getByText('sales_data.csv').closest('[role="button"]');
      fireEvent.keyDown(datasetItem!, { key: 'Enter' });

      expect(mockPush).toHaveBeenCalledWith('/explore/ds-1');
    });

    it('displays dataset row and column counts', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: mockDatasets }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('10,000 rows, 15 columns')).toBeInTheDocument();
        expect(screen.getByText('5,000 rows, 20 columns')).toBeInTheDocument();
      });
    });
  });

  describe('Model Item Interactions', () => {
    it('navigates to model page when clicking a model', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Churn Predictor')).toBeInTheDocument();
      });

      const modelItem = screen.getByText('Churn Predictor').closest('[role="button"]');
      fireEvent.click(modelItem!);

      expect(mockPush).toHaveBeenCalledWith('/model/model-1');
    });

    it('supports keyboard navigation on model items', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Churn Predictor')).toBeInTheDocument();
      });

      const modelItem = screen.getByText('Churn Predictor').closest('[role="button"]');
      fireEvent.keyDown(modelItem!, { key: 'Enter' });

      expect(mockPush).toHaveBeenCalledWith('/model/model-1');
    });

    it('displays model algorithm names', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Random Forest')).toBeInTheDocument();
        expect(screen.getByText('XGBoost')).toBeInTheDocument();
      });
    });
  });

  describe('View All Buttons', () => {
    it('shows View All Datasets button when datasets exist', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: mockDatasets }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('View All Datasets')).toBeInTheDocument();
      });
    });

    it('navigates to explore when clicking View All Datasets', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: mockDatasets }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('View All Datasets')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('View All Datasets'));
      expect(mockPush).toHaveBeenCalledWith('/explore');
    });

    it('shows View All Models button when models exist', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('View All Models')).toBeInTheDocument();
      });
    });

    it('navigates to model when clicking View All Models', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/models')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ models: mockModels }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ datasets: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('View All Models')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('View All Models'));
      expect(mockPush).toHaveBeenCalledWith('/model');
    });
  });

  describe('Help Section', () => {
    it('renders help section', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      expect(screen.getByText('Need help getting started?')).toBeInTheDocument();
      expect(screen.getByText('Start with Data Upload')).toBeInTheDocument();
    });

    it('navigates to upload when clicking help button', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ datasets: [], models: [] }),
      });

      render(<DashboardPage />);

      const helpButton = screen.getByText('Start with Data Upload');
      fireEvent.click(helpButton);

      expect(mockPush).toHaveBeenCalledWith('/upload');
    });
  });

  describe('Relative Time Formatting', () => {
    it('displays just now for recent items', async () => {
      const recentDataset = {
        ...mockDatasets[0],
        created_at: new Date().toISOString(),
      };

      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: [recentDataset] }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('just now')).toBeInTheDocument();
      });
    });

    it('displays minutes ago for recent items', async () => {
      const minutesAgoDataset = {
        ...mockDatasets[0],
        created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 minutes ago
      };

      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: [minutesAgoDataset] }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('5 minutes ago')).toBeInTheDocument();
      });
    });

    it('displays hours ago for items from today', async () => {
      const hoursAgoDataset = {
        ...mockDatasets[0],
        created_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(), // 3 hours ago
      };

      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: [hoursAgoDataset] }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('3 hours ago')).toBeInTheDocument();
      });
    });

    it('displays days ago for items from this week', async () => {
      const daysAgoDataset = {
        ...mockDatasets[0],
        created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), // 2 days ago
      };

      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/datasets')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ datasets: [daysAgoDataset] }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ models: [] }),
        });
      });

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('2 days ago')).toBeInTheDocument();
      });
    });
  });
});
