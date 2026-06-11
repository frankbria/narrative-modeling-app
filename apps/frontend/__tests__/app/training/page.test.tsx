import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { flushPromises } from '../../utils/mock-helpers';
import TrainingJobsPage from '@/app/training/page';
import type { TrainingJobSummary } from '@/lib/services/model';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), prefetch: jest.fn() }),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'u1' } }, status: 'authenticated' }),
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

const runningJob = job({
  model_id: 'job-run',
  target_column: 'churn',
  status: 'running',
  progress_percentage: 40,
  current_stage: 'training',
  completed_at: null,
  elapsed_seconds: 60,
});
const pendingJob = job({
  model_id: 'job-pend',
  target_column: 'revenue',
  status: 'pending',
  progress_percentage: 0,
  completed_at: null,
  started_at: null,
  elapsed_seconds: null,
});
const completedJob = job({
  model_id: 'job-done',
  target_column: 'tenure',
  status: 'completed',
  best_algorithm: 'XGBoost',
  best_score: 0.91,
});
const failedJob = job({
  model_id: 'job-fail',
  target_column: 'sales',
  status: 'failed',
  elapsed_seconds: 42,
});
const cancelledJob = job({
  model_id: 'job-canc',
  target_column: 'fraud',
  status: 'cancelled',
  elapsed_seconds: 30,
});

function listResponse(jobs: TrainingJobSummary[], totalCount = jobs.length) {
  return { jobs, total_count: totalCount, limit: 20, skip: 0 };
}

function setupDefaultJobLists() {
  mockListTrainingJobs.mockImplementation(
    (options?: { status?: string; skip?: number }) => {
      if (options?.status === 'running') {
        return Promise.resolve(listResponse([runningJob]));
      }
      if (options?.status === 'pending') {
        return Promise.resolve(listResponse([pendingJob]));
      }
      if (options?.status === 'failed') {
        return Promise.resolve(listResponse([failedJob]));
      }
      // History "All" sends the terminal statuses as an explicit filter so
      // the backend paginates over exactly the terminal jobs.
      if (options?.status === 'completed,failed,cancelled') {
        return Promise.resolve(
          listResponse([completedJob, failedJob, cancelledJob])
        );
      }
      return Promise.resolve(listResponse([]));
    }
  );
}

describe('TrainingJobsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultJobLists();
    // Compact TrainingProgress cards poll the status endpoint.
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

  it('renders in-flight cards with cancel buttons and history rows', async () => {
    render(<TrainingJobsPage />);

    // In-flight section: running + pending jobs as cards.
    expect(await screen.findByText('churn')).toBeInTheDocument();
    expect(screen.getByText('revenue')).toBeInTheDocument();
    expect(
      screen.getAllByRole('button', { name: /Cancel Training/i }).length
    ).toBeGreaterThanOrEqual(1);

    // History section: "All" paginates over exactly the terminal statuses
    // backend-side (filtering client-side would hide older terminal runs).
    expect(await screen.findByText('tenure')).toBeInTheDocument();
    expect(mockListTrainingJobs).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'completed,failed,cancelled', skip: 0 })
    );
    expect(screen.getByText('sales')).toBeInTheDocument();
    expect(screen.getByText('fraud')).toBeInTheDocument();
    expect(screen.getByText('XGBoost')).toBeInTheDocument();
    expect(screen.getByText('0.910')).toBeInTheDocument();
    expect(screen.getByText('2m 14s')).toBeInTheDocument();
  });

  it('shows an empty state when no jobs are in flight', async () => {
    mockListTrainingJobs.mockImplementation((options?: { status?: string }) => {
      if (options?.status === 'running' || options?.status === 'pending') {
        return Promise.resolve(listResponse([]));
      }
      return Promise.resolve(listResponse([completedJob]));
    });

    render(<TrainingJobsPage />);

    expect(
      await screen.findByText(/No training jobs are currently running/i)
    ).toBeInTheDocument();
  });

  it('filters the history by status', async () => {
    render(<TrainingJobsPage />);
    expect(await screen.findByText('tenure')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Filter by status/i), {
      target: { value: 'failed' },
    });

    await waitFor(() =>
      expect(mockListTrainingJobs).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'failed', skip: 0 })
      )
    );
    // 'sales' is already visible from the "All" view, so wait for the
    // filtered response to replace the rows before asserting.
    await waitFor(() =>
      expect(screen.queryByText('tenure')).not.toBeInTheDocument()
    );
    expect(screen.getByText('sales')).toBeInTheDocument();
    expect(screen.queryByText('fraud')).not.toBeInTheDocument();
  });

  it('dedupes a job returned by both the pending and running queries', async () => {
    // A job can transition pending->running between the two in-flight
    // queries and appear in both responses.
    mockListTrainingJobs.mockImplementation((options?: { status?: string }) => {
      if (options?.status === 'running' || options?.status === 'pending') {
        return Promise.resolve(listResponse([runningJob]));
      }
      return Promise.resolve(listResponse([]));
    });

    render(<TrainingJobsPage />);

    expect(await screen.findByText('churn')).toBeInTheDocument();
    expect(screen.getAllByText('churn')).toHaveLength(1);
  });

  it('ignores a stale history response that resolves after a newer one', async () => {
    let resolveSlowAll: (value: unknown) => void = () => {};
    mockListTrainingJobs.mockImplementation(
      (options?: { status?: string }) => {
        if (options?.status === 'running' || options?.status === 'pending') {
          return Promise.resolve(listResponse([]));
        }
        if (options?.status === 'failed') {
          return Promise.resolve(listResponse([failedJob]));
        }
        // Initial "All" request: deliberately slow.
        return new Promise((resolve) => {
          resolveSlowAll = resolve;
        });
      }
    );

    render(<TrainingJobsPage />);

    // Switch to "failed" while the initial "All" request is still pending.
    fireEvent.change(await screen.findByLabelText(/Filter by status/i), {
      target: { value: 'failed' },
    });
    expect(await screen.findByText('sales')).toBeInTheDocument();

    // The stale "All" response resolves late and must NOT replace the rows.
    await act(async () => {
      resolveSlowAll(listResponse([completedJob, cancelledJob]));
      await flushPromises();
    });
    expect(screen.queryByText('tenure')).not.toBeInTheDocument();
    expect(screen.getByText('sales')).toBeInTheDocument();
  });

  it('loads more history rows with skip-based pagination', async () => {
    mockListTrainingJobs.mockImplementation(
      (options?: { status?: string; skip?: number }) => {
        if (options?.status === 'running' || options?.status === 'pending') {
          return Promise.resolve(listResponse([]));
        }
        if (options?.skip === 20) {
          return Promise.resolve({
            jobs: [cancelledJob],
            total_count: 25,
            limit: 20,
            skip: 20,
          });
        }
        return Promise.resolve({
          jobs: [completedJob, failedJob],
          total_count: 25,
          limit: 20,
          skip: 0,
        });
      }
    );

    render(<TrainingJobsPage />);
    expect(await screen.findByText('tenure')).toBeInTheDocument();
    expect(screen.queryByText('fraud')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Load more/i }));

    expect(await screen.findByText('fraud')).toBeInTheDocument();
    expect(mockListTrainingJobs).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 20 })
    );
    // Previously loaded rows are kept.
    expect(screen.getByText('tenure')).toBeInTheDocument();
  });
});
