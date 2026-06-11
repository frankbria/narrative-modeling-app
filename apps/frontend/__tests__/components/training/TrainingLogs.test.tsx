import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { TrainingLogs } from '@/components/training/TrainingLogs';
import type { TrainingLogsResponse } from '@/lib/services/model';

const mockGetTrainingLogs = jest.fn();
jest.mock('@/lib/services/model', () => ({
  modelService: {
    getTrainingLogs: (...args: unknown[]) => mockGetTrainingLogs(...args),
  },
}));

const logsResponse: TrainingLogsResponse = {
  model_id: 'm1',
  logs: [
    {
      timestamp: '2026-06-10T10:00:00Z',
      level: 'info',
      message: 'Training started',
      stage: 'preprocessing',
    },
    {
      timestamp: '2026-06-10T10:00:10Z',
      level: 'warning',
      message: 'Class imbalance detected',
      stage: 'training',
    },
    {
      timestamp: '2026-06-10T10:00:20Z',
      level: 'error',
      message: 'XGBoost failed to converge',
      stage: 'training',
    },
  ],
  total_count: 3,
  has_more: false,
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

describe('TrainingLogs', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetTrainingLogs.mockResolvedValue(logsResponse);
  });

  it('renders fetched log entries with messages and stage badges', async () => {
    render(<TrainingLogs modelId="m1" pollInterval={60000} />);

    expect(await screen.findByText('Training started')).toBeInTheDocument();
    expect(screen.getByText('Class imbalance detected')).toBeInTheDocument();
    expect(screen.getByText('XGBoost failed to converge')).toBeInTheDocument();
    expect(screen.getByText('preprocessing')).toBeInTheDocument();
    expect(mockGetTrainingLogs).toHaveBeenCalledWith('m1', expect.anything());
  });

  it('filters entries by level via the toggle buttons', async () => {
    render(<TrainingLogs modelId="m1" pollInterval={60000} />);
    expect(await screen.findByText('Training started')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Errors only/i }));
    expect(screen.queryByText('Training started')).not.toBeInTheDocument();
    expect(screen.queryByText('Class imbalance detected')).not.toBeInTheDocument();
    expect(screen.getByText('XGBoost failed to converge')).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: /Warnings \+ Errors/i })
    );
    expect(screen.queryByText('Training started')).not.toBeInTheDocument();
    expect(screen.getByText('Class imbalance detected')).toBeInTheDocument();
    expect(screen.getByText('XGBoost failed to converge')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /^All$/i }));
    expect(screen.getByText('Training started')).toBeInTheDocument();
  });

  it('keeps polling while active', async () => {
    render(<TrainingLogs modelId="m1" pollInterval={30} />);

    await waitFor(() =>
      expect(mockGetTrainingLogs.mock.calls.length).toBeGreaterThanOrEqual(3)
    );
  });

  it('fetches once and does not poll when isActive is false', async () => {
    render(<TrainingLogs modelId="m1" pollInterval={30} isActive={false} />);

    expect(await screen.findByText('Training started')).toBeInTheDocument();
    const calls = mockGetTrainingLogs.mock.calls.length;
    await sleep(150);
    expect(mockGetTrainingLogs.mock.calls.length).toBe(calls);
  });

  it('shows an empty state when there are no logs', async () => {
    mockGetTrainingLogs.mockResolvedValue({
      model_id: 'm1',
      logs: [],
      total_count: 0,
      has_more: false,
    });

    render(<TrainingLogs modelId="m1" pollInterval={60000} />);

    expect(await screen.findByText(/No log entries/i)).toBeInTheDocument();
  });
});
