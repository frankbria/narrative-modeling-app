'use client';

import { useSession } from 'next-auth/react';
import { InFlightSection } from '@/components/training-jobs/InFlightSection';
import { HistorySection } from '@/components/training-jobs/HistorySection';
import { useInFlightJobs } from '@/components/training-jobs/useInFlightJobs';
import { useTrainingHistory } from '@/components/training-jobs/useTrainingHistory';
import { AlertCircle, ListChecks } from 'lucide-react';

interface ErrorNoticeProps {
  message: string | null;
}

function ErrorNotice(props: ErrorNoticeProps) {
  const { message } = props;
  if (!message) return null;
  return (
    <div className="p-3 bg-red-50 dark:bg-red-950/40 rounded-lg border border-red-200 dark:border-red-900 flex items-start gap-2">
      <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
      <p className="text-sm text-red-800 dark:text-red-200">{message}</p>
    </div>
  );
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
  // `session` gets a fresh object identity on re-renders/session refreshes; the
  // hooks must key off this stable flag or they re-fetch on every render.
  const isAuthenticated = !!session;
  const inFlight = useInFlightJobs(isAuthenticated);
  const history = useTrainingHistory(isAuthenticated);

  // A card's job finished: move it from the in-flight section into the history table.
  const handleJobSettled = () => {
    inFlight.reload();
    history.restart();
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
        <ErrorNotice message={inFlight.error ?? history.error} />
        <InFlightSection
          jobs={inFlight.jobs}
          isLoading={inFlight.loading}
          onSettled={handleJobSettled}
          onCancelled={inFlight.reload}
        />
        <HistorySection
          jobs={history.jobs}
          statusFilter={history.statusFilter}
          hasMore={history.hasMore}
          isLoadingMore={history.isLoadingMore}
          onFilterChange={history.setStatusFilter}
          onLoadMore={history.loadMore}
        />
      </div>
    </div>
  );
}
