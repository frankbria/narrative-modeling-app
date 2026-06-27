import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ModelPage from '@/app/model/page';
import { WorkflowStage } from '@/lib/types/workflow';

// Router
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn(), prefetch: jest.fn() }),
}));

// Authenticated session
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'u1' } }, status: 'authenticated' }),
}));

jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn().mockResolvedValue('mock-token'),
}));

jest.mock('@/lib/constants', () => ({
  API_URL: 'http://localhost:8000/api/v1',
}));

// Workflow context: model-training stage accessible, dataset present.
const mockCompleteStage = jest.fn();
const mockWorkflowContext = {
  state: {
    currentStage: WorkflowStage.MODEL_TRAINING,
    completedStages: new Set<WorkflowStage>(),
    stageData: {} as Record<WorkflowStage, unknown>,
    datasetId: 'ds-1',
    modelId: undefined,
  },
  canAccessStage: jest.fn(() => true),
  completeStage: mockCompleteStage,
  setCurrentStage: jest.fn(),
  setDatasetId: jest.fn(),
  resetWorkflow: jest.fn(),
  loadWorkflow: jest.fn(),
  saveWorkflow: jest.fn(),
};
jest.mock('@/lib/contexts/WorkflowContext', () => ({
  useWorkflow: () => mockWorkflowContext,
}));

// Model service: training endpoints are driven per-test. The same mock feeds
// the page and the embedded TrainingProgress/TrainingLogs/CancelTrainingButton
// components, which all import modelService from this module.
const mockTrainModel = jest.fn();
const mockGetTrainingStatus = jest.fn();
const mockGetTrainingLogs = jest.fn();
const mockCancelTraining = jest.fn();
const mockGetModeRecommendation = jest.fn();
jest.mock('@/lib/services/model', () => ({
  modelService: {
    trainModel: (...args: unknown[]) => mockTrainModel(...args),
    getTrainingStatus: (...args: unknown[]) => mockGetTrainingStatus(...args),
    getTrainingLogs: (...args: unknown[]) => mockGetTrainingLogs(...args),
    cancelTraining: (...args: unknown[]) => mockCancelTraining(...args),
    getModeRecommendation: (...args: unknown[]) => mockGetModeRecommendation(...args),
  },
}));

// UserData endpoint for column loading (the model page reads the column list
// from the UserData record's data_schema).
const mockFetch = jest.fn();
global.fetch = mockFetch as unknown as typeof fetch;

function mockColumnsLoaded() {
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => ({
      data_schema: [{ field_name: 'target' }, { field_name: 'x1' }],
    }),
  });
}

async function startTraining() {
  await waitFor(() =>
    expect(screen.getByRole('option', { name: 'target' })).toBeInTheDocument()
  );
  // Wait for the mode recommendation to apply so the selected training mode is
  // deterministic before training starts (issue #101).
  await waitFor(() =>
    expect(screen.getByTestId('mode-recommendation')).toBeInTheDocument()
  );
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'target' } });
  fireEvent.click(screen.getByRole('button', { name: /Start Training/i }));
  await waitFor(() => expect(mockTrainModel).toHaveBeenCalled());
}

describe('ModelPage training wiring', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockColumnsLoaded();
    // Default: recommendation resolves to comprehensive (issue #101). The page
    // preselects it, so trainModel sends training_mode: 'comprehensive'.
    mockGetModeRecommendation.mockResolvedValue({
      recommended_mode: 'comprehensive',
      reason: 'small enough to afford a thorough search',
      n_rows: 100,
      n_features: 2,
    });
    mockGetTrainingLogs.mockResolvedValue({
      model_id: 'model_1',
      logs: [],
      total_count: 0,
      has_more: false,
    });
  });

  it('starts real training and shows the comparison on completion', async () => {
    mockTrainModel.mockResolvedValue({ model_id: 'model_1', status: 'training', message: 'ok' });
    mockGetTrainingStatus.mockResolvedValue({
      model_id: 'model_1',
      status: 'completed',
      progress: 1.0,
      current_algorithm: null,
      completed_algorithms: 2,
      total_algorithms: 2,
      metrics: { cv_score: 0.91 },
      best_algorithm: 'XGBoost',
      explanation: 'XGBoost won with a ROC AUC of 0.910.',
      model_comparison: [
        { algorithm: 'XGBoost', cv_score: 0.91, test_score: 0.9, training_time: 1.2 },
        { algorithm: 'Random Forest', cv_score: 0.88, test_score: 0.86, training_time: 0.8 },
      ],
      algorithm_recommendations: [
        {
          algorithm_name: 'XGBoost',
          priority: 9,
          expected_performance: '85-95% accuracy',
          training_time_estimate: '3-10 minutes',
          interpretability_score: 5,
          explanation: 'State-of-the-art gradient boosting, often best performance',
          pros: ['Often best accuracy'],
          cons: ['Less interpretable'],
        },
      ],
    });

    render(<ModelPage />);
    await startTraining();

    // trainModel called with the correct real payload, including the selected
    // training mode (preselected from the recommendation — issue #101).
    expect(mockTrainModel).toHaveBeenCalledWith({
      dataset_id: 'ds-1',
      target_column: 'target',
      training_config: { training_mode: 'comprehensive' },
    });

    // TrainingProgress polls the status and surfaces completion.
    expect(
      await screen.findByText(/Training complete/i, {}, { timeout: 5000 })
    ).toBeInTheDocument();
    // 'XGBoost' appears both as the best-model label and in the comparison table.
    expect(screen.getAllByText(/XGBoost/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Random Forest')).toBeInTheDocument();
    expect(screen.getByText(/XGBoost won/)).toBeInTheDocument();
    // Algorithm recommendations are rendered for the analyst (acceptance criterion).
    expect(screen.getByText('Why these algorithms?')).toBeInTheDocument();
    expect(
      screen.getByText(/State-of-the-art gradient boosting/)
    ).toBeInTheDocument();
    expect(mockCompleteStage).toHaveBeenCalledWith(
      WorkflowStage.MODEL_TRAINING,
      expect.objectContaining({ modelId: 'model_1', bestAlgorithm: 'XGBoost' })
    );
  }, 15000);

  it('keeps a user mode choice made before a slow recommendation resolves', async () => {
    // Defer the recommendation so the user can pick first (codex P2 fix).
    let resolveRec: (value: unknown) => void = () => {};
    mockGetModeRecommendation.mockReturnValue(
      new Promise((resolve) => {
        resolveRec = resolve;
      })
    );
    mockTrainModel.mockResolvedValue({ model_id: 'm', status: 'training', message: 'ok' });
    mockGetTrainingStatus.mockResolvedValue({
      model_id: 'm',
      status: 'training',
      progress: 0,
      completed_algorithms: 0,
      total_algorithms: 0,
      metrics: {},
      model_comparison: [],
      algorithm_recommendations: [],
    });

    render(<ModelPage />);
    await waitFor(() =>
      expect(screen.getByRole('option', { name: 'target' })).toBeInTheDocument()
    );

    // User explicitly picks comprehensive before the recommendation arrives.
    fireEvent.click(screen.getByTestId('mode-option-comprehensive'));
    // Recommendation (quick) resolves late and must NOT override the pick.
    resolveRec({ recommended_mode: 'quick', reason: 'big data', n_rows: 1, n_features: 1 });
    await screen.findByTestId('mode-recommendation');

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'target' } });
    fireEvent.click(screen.getByRole('button', { name: /Start Training/i }));
    await waitFor(() => expect(mockTrainModel).toHaveBeenCalled());

    expect(mockTrainModel).toHaveBeenCalledWith({
      dataset_id: 'ds-1',
      target_column: 'target',
      training_config: { training_mode: 'comprehensive' },
    });
  });

  it('surfaces a backend failure status as an error message', async () => {
    mockTrainModel.mockResolvedValue({ model_id: 'model_2', status: 'training', message: 'ok' });
    mockGetTrainingStatus.mockResolvedValue({
      model_id: 'model_2',
      status: 'failed',
      progress: 0,
      completed_algorithms: 0,
      total_algorithms: 0,
      metrics: {},
      model_comparison: [],
      algorithm_recommendations: [],
      error: 'Unsupported file type: txt',
    });

    render(<ModelPage />);
    await startTraining();

    expect(
      await screen.findByText('Training failed', {}, { timeout: 5000 })
    ).toBeInTheDocument();
    expect(screen.getByText('Unsupported file type: txt')).toBeInTheDocument();
    // The page returns to the configuration view so training can be retried.
    expect(
      screen.getByRole('button', { name: /Start Training/i })
    ).toBeInTheDocument();
  }, 15000);

  it('shows a cancel button and a collapsible logs panel while training runs', async () => {
    mockTrainModel.mockResolvedValue({ model_id: 'model_3', status: 'training', message: 'ok' });
    mockGetTrainingStatus.mockResolvedValue({
      model_id: 'model_3',
      status: 'running',
      progress: 0.25,
      current_algorithm: 'Random Forest',
      completed_algorithms: 1,
      total_algorithms: 4,
      metrics: {},
      model_comparison: [],
      algorithm_recommendations: [],
      current_stage: 'training',
      elapsed_seconds: 30,
      estimated_remaining_seconds: 90,
    });
    mockGetTrainingLogs.mockResolvedValue({
      model_id: 'model_3',
      logs: [
        {
          timestamp: '2026-06-10T10:00:00Z',
          level: 'info',
          message: 'Training started',
          stage: 'preprocessing',
        },
      ],
      total_count: 1,
      has_more: false,
    });

    render(<ModelPage />);
    await startTraining();

    expect(await screen.findByText('25%', {}, { timeout: 5000 })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Cancel Training/i })
    ).toBeInTheDocument();

    // Logs are collapsed by default and toggle open on demand.
    expect(screen.queryByText('Training started')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Show Logs/i }));
    expect(await screen.findByText('Training started')).toBeInTheDocument();
  }, 15000);

  it('returns to the configuration view with a notice when training is cancelled', async () => {
    mockTrainModel.mockResolvedValue({ model_id: 'model_4', status: 'training', message: 'ok' });
    mockGetTrainingStatus.mockResolvedValue({
      model_id: 'model_4',
      status: 'cancelled',
      progress: 0.5,
      completed_algorithms: 2,
      total_algorithms: 4,
      metrics: {},
      model_comparison: [],
      algorithm_recommendations: [],
    });

    render(<ModelPage />);
    await startTraining();

    expect(
      await screen.findByText(/Training cancelled/i, {}, { timeout: 5000 })
    ).toBeInTheDocument();
    // Back on the configuration view, ready for a new run.
    expect(
      screen.getByRole('button', { name: /Start Training/i })
    ).toBeInTheDocument();
    expect(mockCompleteStage).not.toHaveBeenCalled();
  }, 15000);
});
