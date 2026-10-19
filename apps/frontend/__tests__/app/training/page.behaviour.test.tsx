import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import TrainingJobsPage from '@/app/training/page';
import type { TrainingJobSummary } from '@/lib/services/model';

let mockSession: { user: { id: string } } | null = { user: { id: 'u1' } };
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: mockSession, status: mockSession ? 'authenticated' : 'unauthenticated' }),
}));

const mockListTrainingJobs = jest.fn();
const mockGetTrainingStatus = jest.fn();
const mockCancelTraining = jest.fn();
jest.mock('@/lib/services/model', () => ({
  modelService: {
    listTrainingJobs: (...args: unknown[]) => mockListTrainingJobs(...args),
    getTrainingStatus: (...args: unknown[]) => mockGetTrainingStatus(...args),
    cancelTraining: (...args: unknown[]) => mockCancelTraining(...args),
  },
}));

function job(overrides: Partial<TrainingJobSummary>): TrainingJobSummary {
  return {
    model_id: 'job-1',
    dataset_id: 'ds-1',
    target_column: 'target',
    status: 'completed',
    progress_percentage: 100,
    current_stage: null,
    created_at: '2026-06-10T09:00:00Z',
    started_at: '2026-06-10T09:00:05Z',
    completed_at: '2026-06-10T09:02:19Z',
    best_algorithm: null,
    best_score: null,
    elapsed_seconds: 134,
    ...overrides,
  };
}

const runningJob = job({ model_id: 'job-run', target_column: 'churn', status: 'running', completed_at: null });
const completedJob = job({ model_id: 'job-done', target_column: 'tenure', best_algorithm: 'XGBoost', best_score: 0.91 });
const failedJob = job({ model_id: 'job-fail', target_column: 'sales', status: 'failed', elapsed_seconds: null });
const cancelledJob = job({ model_id: 'job-canc', target_column: 'fraud', status: 'cancelled' });

const page = (jobs: TrainingJobSummary[], total = jobs.length) => ({ jobs, total_count: total, limit: 20, skip: 0 });
const isInFlight = (o?: { status?: string }) => o?.status === 'running' || o?.status === 'pending';

// Running job in flight; history "All" holds one row, with a second page behind it.
function twoHistoryPages() {
  mockListTrainingJobs.mockImplementation((o?: { status?: string; skip?: number }) => {
    if (o?.status === 'running') return Promise.resolve(page([runningJob]));
    if (o?.status === 'pending') return Promise.resolve(page([]));
    if (o?.skip === 20) return Promise.resolve(page([cancelledJob], 21));
    if (o?.status === 'failed') return Promise.resolve(page([failedJob]));
    return Promise.resolve(page([completedJob], 21));
  });
}

const historyCalls = () =>
  mockListTrainingJobs.mock.calls.map(([o]) => o).filter((o) => !isInFlight(o));
const inFlightCalls = () => mockListTrainingJobs.mock.calls.map(([o]) => o).filter(isInFlight);

describe('TrainingJobsPage behaviour', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession = { user: { id: 'u1' } };
    mockGetTrainingStatus.mockResolvedValue({
      model_id: 'job-run',
      status: 'running',
      progress: 0.4,
      current_algorithm: 'Random Forest',
      completed_algorithms: 1,
      total_algorithms: 4,
      metrics: {},
      model_comparison: [],
      algorithm_recommendations: [],
      current_stage: 'training',
      elapsed_seconds: 60,
      estimated_remaining_seconds: 90,
    });
  });

  it('asks a signed-out visitor to log in and fetches nothing', () => {
    mockSession = null;
    render(<TrainingJobsPage />);
    expect(screen.getByText('Please log in to access this page.')).toBeInTheDocument();
    expect(mockListTrainingJobs).not.toHaveBeenCalled();
  });

  it('shows a loading line until the in-flight list arrives', async () => {
    twoHistoryPages();
    render(<TrainingJobsPage />);
    expect(screen.getByText('Loading training jobs…')).toBeInTheDocument();
    expect(await screen.findByText('churn')).toBeInTheDocument();
    expect(screen.queryByText('Loading training jobs…')).not.toBeInTheDocument();
  });

  it('shows the in-flight failure message', async () => {
    mockListTrainingJobs.mockImplementation((o?: { status?: string }) =>
      isInFlight(o) ? Promise.reject(new Error('boom')) : Promise.resolve(page([]))
    );
    render(<TrainingJobsPage />);
    expect(await screen.findByText('Failed to fetch training jobs')).toBeInTheDocument();
  });

  it('shows the history failure message', async () => {
    mockListTrainingJobs.mockImplementation((o?: { status?: string }) =>
      isInFlight(o) ? Promise.resolve(page([])) : Promise.reject(new Error('boom'))
    );
    render(<TrainingJobsPage />);
    expect(await screen.findByText('Failed to fetch training history')).toBeInTheDocument();
  });

  it('prefers the in-flight failure when both fail', async () => {
    mockListTrainingJobs.mockRejectedValue(new Error('boom'));
    render(<TrainingJobsPage />);
    expect(await screen.findByText('Failed to fetch training jobs')).toBeInTheDocument();
    expect(screen.queryByText('Failed to fetch training history')).not.toBeInTheDocument();
  });

  it('says so when there is no finished job', async () => {
    mockListTrainingJobs.mockResolvedValue(page([]));
    render(<TrainingJobsPage />);
    expect(await screen.findByText('No finished training jobs yet.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Load more/i })).not.toBeInTheDocument();
  });

  it('shows a dash where a finished job has no duration, algorithm or score', async () => {
    mockListTrainingJobs.mockImplementation((o?: { status?: string }) =>
      Promise.resolve(isInFlight(o) ? page([]) : page([failedJob]))
    );
    render(<TrainingJobsPage />);
    await screen.findByText('sales');
    expect(screen.getAllByText('—')).toHaveLength(3);
  });

  it('colours each history status by its own badge variant', async () => {
    mockListTrainingJobs.mockImplementation((o?: { status?: string }) =>
      Promise.resolve(
        isInFlight(o)
          ? page([])
          : page([completedJob, failedJob, cancelledJob, job({ model_id: 'x', status: 'pending', target_column: 'odd' })])
      )
    );
    render(<TrainingJobsPage />);
    await screen.findByText('tenure');
    const badge = (text: string) => screen.getAllByText(text).find((el) => el.className.includes('rounded-full'))!;
    expect(badge('completed')).toHaveClass('bg-green-600');
    expect(badge('failed')).toHaveClass('bg-destructive');
    expect(badge('cancelled')).toHaveClass('bg-secondary');
    expect(badge('pending')).not.toHaveClass('bg-primary', 'bg-green-600', 'bg-destructive', 'bg-secondary');
  });

  it('refreshes the in-flight list every ten seconds', async () => {
    jest.useFakeTimers();
    try {
      twoHistoryPages();
      render(<TrainingJobsPage />);
      await act(async () => {
        await jest.advanceTimersByTimeAsync(0);
      });
      const before = inFlightCalls().length;
      await act(async () => {
        await jest.advanceTimersByTimeAsync(10000);
      });
      expect(inFlightCalls().length).toBe(before + 2);
      await act(async () => {
        await jest.advanceTimersByTimeAsync(10000);
      });
      expect(inFlightCalls().length).toBe(before + 4);
    } finally {
      jest.useRealTimers();
    }
  });

  it('shows Load more only while rows remain, and hides it after the last page', async () => {
    twoHistoryPages();
    render(<TrainingJobsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Load more/i }));
    expect(await screen.findByText('fraud')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Load more/i })).not.toBeInTheDocument();
  });

  it('fetches a page once however often Load more is clicked while it is in flight', async () => {
    let resolveSecond: (value: unknown) => void = () => {};
    mockListTrainingJobs.mockImplementation((o?: { status?: string; skip?: number }) => {
      if (isInFlight(o)) return Promise.resolve(page([]));
      if (o?.skip === 20) return new Promise((resolve) => (resolveSecond = resolve));
      return Promise.resolve(page([completedJob], 21));
    });
    render(<TrainingJobsPage />);
    const more = await screen.findByRole('button', { name: /Load more/i });
    fireEvent.click(more);
    const loading = await screen.findByRole('button', { name: 'Loading…' });
    expect(loading).toBeDisabled();
    fireEvent.click(loading);
    expect(historyCalls().filter((o) => o.skip === 20)).toHaveLength(1);
    await act(async () => resolveSecond(page([cancelledJob], 21)));
    expect(await screen.findByText('fraud')).toBeInTheDocument();
  });

  it('asks for the next page under the status filter in force', async () => {
    twoHistoryPages();
    mockListTrainingJobs.mockImplementation((o?: { status?: string; skip?: number }) => {
      if (isInFlight(o)) return Promise.resolve(page([]));
      if (o?.skip === 20) return Promise.resolve(page([cancelledJob], 21));
      return Promise.resolve(page([failedJob], 21));
    });
    render(<TrainingJobsPage />);
    await screen.findByText('Training History');
    fireEvent.change(screen.getByLabelText(/Filter by status/i), { target: { value: 'failed' } });
    await waitFor(() => expect(historyCalls().some((o) => o.status === 'failed')).toBe(true));
    fireEvent.click(await screen.findByRole('button', { name: /Load more/i }));
    await screen.findByText('fraud');
    expect(historyCalls().find((o) => o.skip === 20)).toEqual({ status: 'failed', limit: 20, skip: 20 });
  });

  it('drops the appended rows when the filter changes', async () => {
    twoHistoryPages();
    render(<TrainingJobsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Load more/i }));
    await screen.findByText('fraud');
    fireEvent.change(screen.getByLabelText(/Filter by status/i), { target: { value: 'failed' } });
    await screen.findByText('sales');
    expect(screen.queryByText('fraud')).not.toBeInTheDocument();
    expect(screen.queryByText('tenure')).not.toBeInTheDocument();
  });

  it('moves a finished job out of the cards and restarts the history from its first page', async () => {
    jest.useFakeTimers();
    try {
      twoHistoryPages();
      render(<TrainingJobsPage />);
      await act(async () => {
        await jest.advanceTimersByTimeAsync(0);
      });
      fireEvent.click(screen.getByRole('button', { name: /Load more/i }));
      await act(async () => {
        await jest.advanceTimersByTimeAsync(0);
      });
      expect(screen.getByText('fraud')).toBeInTheDocument();
      const inFlightBefore = inFlightCalls().length;
      const historyBefore = historyCalls().length;
      mockGetTrainingStatus.mockResolvedValue({
        model_id: 'job-run',
        status: 'completed',
        progress: 1,
        completed_algorithms: 4,
        total_algorithms: 4,
        metrics: {},
        model_comparison: [],
        algorithm_recommendations: [],
        current_stage: null,
        elapsed_seconds: 60,
        estimated_remaining_seconds: 0,
      });
      // Once it has finished the backend no longer lists it as in flight (a card that
      // stayed would remount after the reload and settle again, forever).
      mockListTrainingJobs.mockImplementation((o?: { status?: string; skip?: number }) => {
        if (isInFlight(o)) return Promise.resolve(page([]));
        if (o?.skip === 20) return Promise.resolve(page([cancelledJob], 21));
        return Promise.resolve(page([completedJob], 21));
      });
      // The card's next status poll (2s) reports completion.
      await act(async () => {
        await jest.advanceTimersByTimeAsync(2000);
      });
      expect(inFlightCalls().length).toBe(inFlightBefore + 2);
      expect(historyCalls().length).toBe(historyBefore + 1);
      expect(historyCalls().at(-1)).toEqual({ status: 'completed,failed,cancelled', limit: 20, skip: 0 });
      expect(screen.queryByText('fraud')).not.toBeInTheDocument();
      expect(screen.queryByText('churn')).not.toBeInTheDocument();
      expect(screen.getByText('tenure')).toBeInTheDocument();
    } finally {
      jest.useRealTimers();
    }
  });

  it('reloads the in-flight list after a cancel', async () => {
    twoHistoryPages();
    mockCancelTraining.mockResolvedValue({ model_id: 'job-run', status: 'cancelled' });
    render(<TrainingJobsPage />);
    await screen.findByText('churn');
    const before = inFlightCalls().length;
    fireEvent.click(screen.getByRole('button', { name: /Cancel Training/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Yes, cancel training/i }));
    await waitFor(() => expect(mockCancelTraining).toHaveBeenCalledWith('job-run'));
    await waitFor(() => expect(inFlightCalls().length).toBe(before + 2));
  });
});
