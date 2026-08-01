import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { TrainingProgress } from '@/components/training/TrainingProgress';
import type { TrainingStatus } from '@/lib/services/model';

const mockGetTrainingStatus = jest.fn();
jest.mock('@/lib/services/model', () => ({
  modelService: {
    getTrainingStatus: (...args: unknown[]) => mockGetTrainingStatus(...args),
  },
}));

function runningStatus(overrides: Partial<TrainingStatus> = {}): TrainingStatus {
  return {
    model_id: 'm1',
    status: 'running',
    progress: 0.45,
    current_algorithm: 'XGBoost',
    completed_algorithms: 1,
    total_algorithms: 4,
    metrics: {},
    model_comparison: [],
    algorithm_recommendations: [],
    current_stage: 'training',
    elapsed_seconds: 134,
    estimated_remaining_seconds: 90,
    cancellation_requested: false,
    ...overrides,
  };
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

describe('TrainingProgress', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders live progress: percentage, stage, algorithm, counts and timing', async () => {
    mockGetTrainingStatus.mockResolvedValue(runningStatus());

    render(<TrainingProgress modelId="m1" pollInterval={60000} />);

    expect(await screen.findByText('45%')).toBeInTheDocument();
    expect(screen.getByText('training')).toBeInTheDocument();
    expect(screen.getByText(/XGBoost/)).toBeInTheDocument();
    expect(screen.getByText(/1 of 4 algorithms/)).toBeInTheDocument();
    expect(
      screen.getByText(/2m 14s elapsed · ~1m 30s remaining/)
    ).toBeInTheDocument();
  });

  it('renders a live model comparison mini-table when entries exist', async () => {
    mockGetTrainingStatus.mockResolvedValue(
      runningStatus({
        model_comparison: [
          { algorithm: 'Random Forest', cv_score: 0.88, test_score: 0.86 },
          { algorithm: 'Logistic Regression', cv_score: 0.81, test_score: 0.8 },
        ],
      })
    );

    render(<TrainingProgress modelId="m1" pollInterval={60000} />);

    expect(await screen.findByText('Random Forest')).toBeInTheDocument();
    expect(screen.getByText('Logistic Regression')).toBeInTheDocument();
    expect(screen.getByText('0.880')).toBeInTheDocument();
    expect(screen.getByText('0.860')).toBeInTheDocument();
  });

  it('on completion shows a success alert, fires onComplete and stops polling', async () => {
    const completed = runningStatus({
      status: 'completed',
      progress: 1,
      current_algorithm: null,
      completed_algorithms: 4,
      best_algorithm: 'XGBoost',
      model_comparison: [{ algorithm: 'XGBoost', cv_score: 0.91, test_score: 0.9 }],
    });
    mockGetTrainingStatus.mockResolvedValue(completed);
    const onComplete = jest.fn();

    render(<TrainingProgress modelId="m1" pollInterval={50} onComplete={onComplete} />);

    await waitFor(() => expect(onComplete).toHaveBeenCalledWith(completed));
    expect(screen.getByText(/Training complete/i)).toBeInTheDocument();
    expect(screen.getAllByText(/XGBoost/).length).toBeGreaterThanOrEqual(1);
    // The score appears in both the success alert and the comparison table.
    expect(screen.getAllByText(/0\.910/).length).toBeGreaterThanOrEqual(1);

    const callsAfterComplete = mockGetTrainingStatus.mock.calls.length;
    await sleep(200);
    expect(mockGetTrainingStatus.mock.calls.length).toBe(callsAfterComplete);
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it('fires the latest onComplete after the parent re-renders with a new callback identity', async () => {
    // The latest-callback refs are written in an effect rather than during
    // render (#373, react-hooks/refs). This is the invariant that move has to
    // preserve: a parent re-render with a fresh function identity must not
    // restart the poll loop, and the terminal event must call the NEW callback,
    // never the one captured at mount.
    const running = runningStatus();
    mockGetTrainingStatus.mockResolvedValue(running);

    const firstOnComplete = jest.fn();
    const { rerender } = render(
      <TrainingProgress modelId="m1" pollInterval={50} onComplete={firstOnComplete} />
    );

    await waitFor(() => expect(mockGetTrainingStatus).toHaveBeenCalled());
    const pollsBeforeRerender = mockGetTrainingStatus.mock.calls.length;

    const secondOnComplete = jest.fn();
    rerender(<TrainingProgress modelId="m1" pollInterval={50} onComplete={secondOnComplete} />);

    const completed = runningStatus({ status: 'completed', progress: 1, current_algorithm: null });
    mockGetTrainingStatus.mockResolvedValue(completed);

    await waitFor(() => expect(secondOnComplete).toHaveBeenCalledWith(completed));
    expect(firstOnComplete).not.toHaveBeenCalled();

    // A new callback identity must not have torn down and restarted polling.
    expect(mockGetTrainingStatus.mock.calls.length).toBeGreaterThanOrEqual(pollsBeforeRerender);
  });

  it('on failure shows the error message and fires onError', async () => {
    const failed = runningStatus({
      status: 'failed',
      error: 'Target column has only one class',
    });
    mockGetTrainingStatus.mockResolvedValue(failed);
    const onError = jest.fn();

    render(<TrainingProgress modelId="m1" pollInterval={50} onError={onError} />);

    await waitFor(() => expect(onError).toHaveBeenCalledWith(failed));
    expect(screen.getByText(/Training failed/i)).toBeInTheDocument();
    expect(screen.getByText('Target column has only one class')).toBeInTheDocument();
  });

  it('on cancellation shows a notice and fires onCancelled', async () => {
    const cancelled = runningStatus({ status: 'cancelled' });
    mockGetTrainingStatus.mockResolvedValue(cancelled);
    const onCancelled = jest.fn();

    render(
      <TrainingProgress modelId="m1" pollInterval={50} onCancelled={onCancelled} />
    );

    await waitFor(() => expect(onCancelled).toHaveBeenCalledWith(cancelled));
    expect(screen.getByText(/Training cancelled/i)).toBeInTheDocument();
  });

  it('shows a connection-lost warning after 3 consecutive failures and recovers via Retry', async () => {
    mockGetTrainingStatus.mockRejectedValue(new Error('network down'));

    render(<TrainingProgress modelId="m1" pollInterval={20} />);

    expect(
      await screen.findByText(/Connection lost/i, {}, { timeout: 3000 })
    ).toBeInTheDocument();

    mockGetTrainingStatus.mockResolvedValue(runningStatus());
    await userEvent.click(screen.getByRole('button', { name: /Retry/i }));

    expect(await screen.findByText('45%')).toBeInTheDocument();
    expect(screen.queryByText(/Connection lost/i)).not.toBeInTheDocument();
  });

  it('compact mode renders progress without the comparison table', async () => {
    mockGetTrainingStatus.mockResolvedValue(
      runningStatus({
        model_comparison: [{ algorithm: 'Random Forest', cv_score: 0.88, test_score: 0.86 }],
      })
    );

    render(<TrainingProgress modelId="m1" pollInterval={60000} compact />);

    expect(await screen.findByText('45%')).toBeInTheDocument();
    expect(screen.queryByText('Random Forest')).not.toBeInTheDocument();
  });
});
