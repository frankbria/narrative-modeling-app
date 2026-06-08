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

// Model service: trainModel + getTrainingStatus are driven per-test.
const mockTrainModel = jest.fn();
const mockGetTrainingStatus = jest.fn();
jest.mock('@/lib/services/model', () => ({
  modelService: {
    trainModel: (...args: unknown[]) => mockTrainModel(...args),
    getTrainingStatus: (...args: unknown[]) => mockGetTrainingStatus(...args),
  },
}));

// Schema endpoint for column loading.
const mockFetch = jest.fn();
global.fetch = mockFetch as unknown as typeof fetch;

function mockColumnsLoaded() {
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => ({ columns: [{ name: 'target' }, { name: 'x1' }] }),
  });
}

describe('ModelPage training wiring', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockColumnsLoaded();
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
      algorithm_recommendations: [],
    });

    render(<ModelPage />);

    // Wait for columns to load and select the target.
    await waitFor(() => expect(screen.getByRole('option', { name: 'target' })).toBeInTheDocument());
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'target' } });

    fireEvent.click(screen.getByRole('button', { name: /Start Training/i }));

    // trainModel called with the correct real payload.
    await waitFor(() => expect(mockTrainModel).toHaveBeenCalled());
    expect(mockTrainModel).toHaveBeenCalledWith({
      dataset_id: 'ds-1',
      target_column: 'target',
    });

    // Status is polled after ~2s; allow time for the first poll to resolve.
    expect(
      await screen.findByText('Training complete!', {}, { timeout: 5000 })
    ).toBeInTheDocument();
    // 'XGBoost' appears both as the best-model label and in the comparison table.
    expect(screen.getAllByText('XGBoost').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Random Forest')).toBeInTheDocument();
    expect(screen.getByText(/XGBoost won/)).toBeInTheDocument();
    expect(mockCompleteStage).toHaveBeenCalledWith(
      WorkflowStage.MODEL_TRAINING,
      expect.objectContaining({ modelId: 'model_1', bestAlgorithm: 'XGBoost' })
    );
  }, 15000);

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

    await waitFor(() => expect(screen.getByRole('option', { name: 'target' })).toBeInTheDocument());
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'target' } });
    fireEvent.click(screen.getByRole('button', { name: /Start Training/i }));

    await waitFor(() => expect(mockTrainModel).toHaveBeenCalled());

    expect(
      await screen.findByText('Training failed', {}, { timeout: 5000 })
    ).toBeInTheDocument();
    expect(screen.getByText('Unsupported file type: txt')).toBeInTheDocument();
  }, 15000);
});
