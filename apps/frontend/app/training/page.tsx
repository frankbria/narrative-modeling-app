'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { useSession } from 'next-auth/react';
import { modelService, TrainingJobStatus, TrainingJobSummary } from '@/lib/services/model';
import { TrainingProgress, formatDuration } from '@/components/training/TrainingProgress';
import { CancelTrainingButton } from '@/components/training/CancelTrainingButton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { AlertCircle, ListChecks } from 'lucide-react';

/** Refresh the in-flight job list this often, in milliseconds. */
const IN_FLIGHT_REFRESH_MS = 10000;
/** History rows fetched per page. */
const HISTORY_PAGE_SIZE = 20;
/** Cap for the in-flight fetch; far more concurrent jobs is not expected. */
const IN_FLIGHT_FETCH_LIMIT = 50;

type HistoryFilter = 'all' | 'completed' | 'failed' | 'cancelled';

/**
 * "All" history sends the terminal statuses as an explicit backend filter so
 * pagination and total_count apply AFTER filtering — dropping in-flight rows
 * client-side would hide older terminal runs behind pages of running jobs.
 */
const ALL_TERMINAL_FILTER = 'completed,failed,cancelled';

function statusBadgeVariant(
  status: TrainingJobStatus
): 'success' | 'destructive' | 'secondary' | 'outline' {
  switch (status) {
    case 'completed':
      return 'success';
    case 'failed':
      return 'destructive';
    case 'cancelled':
      return 'secondary';
    default:
      return 'outline';
  }
}

/**
 * Training jobs dashboard.
 *
 * "In-Flight Training" lists pending/running jobs as compact live-progress
 * cards (each with a cancel button), refreshed every 10 seconds and whenever a
 * job reaches a terminal state. "Training History" is a filterable, paginated
 * table of completed/failed/cancelled jobs.
 */
export default function TrainingJobsPage() {
  const { data: session } = useSession();
  const [statusFilter, setStatusFilter] = useState<HistoryFilter>('all');
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  // Monotonic id so an out-of-order history response (slow request for a
  // previous filter resolving late) can never overwrite newer rows.

  // `session` gets a fresh object identity on re-renders/session refreshes; the
  // hooks must key off this stable flag or they re-fetch on every render.
  const isAuthenticated = !!session;

  const {
    data: inFlightData,
    loading: isLoadingInFlight,
    error: inFlightError,
    reload: fetchInFlight,
  } = useAsyncData(
    async () => {
      const [pending, running] = await Promise.all([
        modelService.listTrainingJobs({ status: 'pending', limit: IN_FLIGHT_FETCH_LIMIT }),
        modelService.listTrainingJobs({ status: 'running', limit: IN_FLIGHT_FETCH_LIMIT }),
      ]);
      // A job can transition pending->running between the two queries and
      // show up in both lists; dedupe by model_id (running wins).
      return Array.from(
        new Map(
          [...pending.jobs, ...running.jobs].map((job) => [job.model_id, job])
        ).values()
      );
    },
    [isAuthenticated],
    {
      enabled: isAuthenticated,
      errorMessage: 'Failed to fetch training jobs',
      // Polling must not blank the list between ticks.
      keepPreviousData: true,
    },
  );
  const inFlightJobs = inFlightData ?? [];

  // Periodic refresh: reload() runs from the timer callback, not the effect body.
  useEffect(() => {
    if (!isAuthenticated) return;
    const intervalId = setInterval(fetchInFlight, IN_FLIGHT_REFRESH_MS);
    return () => clearInterval(intervalId);
  }, [isAuthenticated, fetchInFlight]);

  // First page of history. Later pages are appended by the Load more handler
  // below rather than by an effect, because paging is user-driven — which is
  // also why the accumulating shape never fitted a keyed loader.
  const {
    data: historyPage,
    error: historyError,
    reload: reloadHistory,
  } = useAsyncData(
    () =>
      modelService.listTrainingJobs({
        status: statusFilter === 'all' ? ALL_TERMINAL_FILTER : statusFilter,
        limit: HISTORY_PAGE_SIZE,
        skip: 0,
      }),
    [isAuthenticated, statusFilter],
    { enabled: isAuthenticated, errorMessage: 'Failed to fetch training history', keepPreviousData: true },
  );

  // Pages beyond the first, tagged with the filter they belong to so changing
  // the filter discards them by derivation instead of a reset.
  const [appended, setAppended] = useState<{
    filter: HistoryFilter;
    jobs: TrainingJobSummary[];
    skip: number;
  }>({ filter: statusFilter, jobs: [], skip: 0 });
  const appendedForFilter =
    appended.filter === statusFilter ? appended : { filter: statusFilter, jobs: [], skip: 0 };

  const historyJobs = [...(historyPage?.jobs ?? []), ...appendedForFilter.jobs];
  const historyTotal = historyPage?.total_count ?? 0;
  const historySkip = appendedForFilter.skip;

  const error = inFlightError ?? historyError;
  const isLoading = isLoadingInFlight;


  // A card's job finished (completed/failed/cancelled): move it from the
  // in-flight section into the history table.
  const handleJobSettled = useCallback(() => {
    fetchInFlight();
    setAppended({ filter: statusFilter, jobs: [], skip: 0 });
    reloadHistory();
  }, [fetchInFlight, reloadHistory, statusFilter]);

  const hasMoreHistory = historySkip + HISTORY_PAGE_SIZE < historyTotal;

  // Append-mode fetches accumulate rows, so rapid clicks would append the
  // same page twice; disable the button while a page is in flight.
  const handleLoadMore = async () => {
    if (isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const nextSkip = historySkip + HISTORY_PAGE_SIZE;
      const response = await modelService.listTrainingJobs({
        status: statusFilter === 'all' ? ALL_TERMINAL_FILTER : statusFilter,
        limit: HISTORY_PAGE_SIZE,
        skip: nextSkip,
      });
      setAppended((prev) => {
        const base =
          prev.filter === statusFilter ? prev : { filter: statusFilter, jobs: [], skip: 0 };
        return { filter: statusFilter, jobs: [...base.jobs, ...response.jobs], skip: nextSkip };
      });
    } finally {
      setIsLoadingMore(false);
    }
  };

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Please log in to access this page.</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-card rounded-lg shadow-md p-6 space-y-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ListChecks className="w-6 h-6 text-indigo-500" />
          Training Jobs
        </h1>

        {error && (
          <div className="p-3 bg-red-50 dark:bg-red-950/40 rounded-lg border border-red-200 dark:border-red-900 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
            <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
          </div>
        )}

        {/* In-flight jobs */}
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">In-Flight Training</h2>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading training jobs…</p>
          ) : inFlightJobs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No training jobs are currently running.
            </p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {inFlightJobs.map((job) => (
                <div
                  key={job.model_id}
                  className="border border-border rounded-lg p-4 space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium truncate">{job.target_column}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        Dataset {job.dataset_id}
                      </p>
                    </div>
                    <Badge variant="outline">{job.status}</Badge>
                  </div>
                  <TrainingProgress
                    modelId={job.model_id}
                    compact
                    onComplete={handleJobSettled}
                    onError={handleJobSettled}
                    onCancelled={handleJobSettled}
                  />
                  <CancelTrainingButton
                    modelId={job.model_id}
                    onCancelled={fetchInFlight}
                    className="w-full"
                  />
                </div>
              ))}
            </div>
          )}
        </section>

        {/* History */}
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">Training History</h2>
            <select
              aria-label="Filter by status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as HistoryFilter)}
              className="p-2 text-sm border border-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          {historyJobs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No finished training jobs yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Best Algorithm</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {historyJobs.map((job) => (
                  <TableRow key={job.model_id}>
                    <TableCell>
                      <Badge variant={statusBadgeVariant(job.status)}>
                        {job.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="font-medium">{job.target_column}</span>
                      <span className="block text-xs text-muted-foreground">
                        Dataset {job.dataset_id}
                      </span>
                    </TableCell>
                    <TableCell>
                      {job.elapsed_seconds != null
                        ? formatDuration(job.elapsed_seconds)
                        : '—'}
                    </TableCell>
                    <TableCell>{job.best_algorithm ?? '—'}</TableCell>
                    <TableCell>
                      {job.best_score != null ? job.best_score.toFixed(3) : '—'}
                    </TableCell>
                    <TableCell>
                      {new Date(job.created_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {hasMoreHistory && (
            <div className="flex justify-center">
              <Button
                variant="outline"
                disabled={isLoadingMore}
                onClick={handleLoadMore}
              >
                {isLoadingMore ? 'Loading…' : 'Load more'}
              </Button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
