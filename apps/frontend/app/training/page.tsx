'use client';

import React, { useCallback, useEffect, useState } from 'react';
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
  const [inFlightJobs, setInFlightJobs] = useState<TrainingJobSummary[]>([]);
  const [historyJobs, setHistoryJobs] = useState<TrainingJobSummary[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historySkip, setHistorySkip] = useState(0);
  const [statusFilter, setStatusFilter] = useState<HistoryFilter>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInFlight = useCallback(async () => {
    try {
      const [pending, running] = await Promise.all([
        modelService.listTrainingJobs({ status: 'pending', limit: IN_FLIGHT_FETCH_LIMIT }),
        modelService.listTrainingJobs({ status: 'running', limit: IN_FLIGHT_FETCH_LIMIT }),
      ]);
      setInFlightJobs([...running.jobs, ...pending.jobs]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch training jobs');
    }
  }, []);

  const fetchHistory = useCallback(
    async (filter: HistoryFilter, skip: number, append: boolean) => {
      try {
        const response = await modelService.listTrainingJobs({
          status: filter === 'all' ? ALL_TERMINAL_FILTER : filter,
          limit: HISTORY_PAGE_SIZE,
          skip,
        });
        setHistoryJobs((prev) =>
          append ? [...prev, ...response.jobs] : response.jobs
        );
        setHistoryTotal(response.total_count);
        setHistorySkip(skip);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch training history');
      }
    },
    []
  );

  // `session` gets a fresh object identity on re-renders/session refreshes;
  // effects must key off this stable flag or they re-fetch (and silently
  // reset the filtered history back to "all") on every render.
  const isAuthenticated = !!session;

  // Initial in-flight load + periodic refresh.
  useEffect(() => {
    if (!isAuthenticated) return;

    let isMounted = true;
    fetchInFlight().finally(() => {
      if (isMounted) setIsLoading(false);
    });

    const intervalId = setInterval(fetchInFlight, IN_FLIGHT_REFRESH_MS);
    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [isAuthenticated, fetchInFlight]);

  // History load: initial and whenever the status filter changes.
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchHistory(statusFilter, 0, false);
  }, [isAuthenticated, statusFilter, fetchHistory]);

  // A card's job finished (completed/failed/cancelled): move it from the
  // in-flight section into the history table.
  const handleJobSettled = useCallback(() => {
    fetchInFlight();
    fetchHistory(statusFilter, 0, false);
  }, [fetchInFlight, fetchHistory, statusFilter]);

  const hasMoreHistory = historySkip + HISTORY_PAGE_SIZE < historyTotal;

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-600">Please log in to access this page.</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6 space-y-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ListChecks className="w-6 h-6 text-indigo-500" />
          Training Jobs
        </h1>

        {error && (
          <div className="p-3 bg-red-50 rounded-lg border border-red-200 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* In-flight jobs */}
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">In-Flight Training</h2>
          {isLoading ? (
            <p className="text-sm text-gray-500">Loading training jobs…</p>
          ) : inFlightJobs.length === 0 ? (
            <p className="text-sm text-gray-500">
              No training jobs are currently running.
            </p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {inFlightJobs.map((job) => (
                <div
                  key={job.model_id}
                  className="border border-gray-200 rounded-lg p-4 space-y-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium truncate">{job.target_column}</p>
                      <p className="text-xs text-gray-500 truncate">
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
              className="p-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          {historyJobs.length === 0 ? (
            <p className="text-sm text-gray-500">No finished training jobs yet.</p>
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
                      <span className="block text-xs text-gray-500">
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
                onClick={() =>
                  fetchHistory(statusFilter, historySkip + HISTORY_PAGE_SIZE, true)
                }
              >
                Load more
              </Button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
