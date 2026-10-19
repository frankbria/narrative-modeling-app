import { formatDuration } from '@/components/training/TrainingProgress';
import type { TrainingJobStatus, TrainingJobSummary } from '@/lib/services/model';

/** Refresh the in-flight job list this often, in milliseconds. */
export const IN_FLIGHT_REFRESH_MS = 10000;
/** History rows fetched per page. */
export const HISTORY_PAGE_SIZE = 20;
/** Cap for the in-flight fetch; far more concurrent jobs is not expected. */
export const IN_FLIGHT_FETCH_LIMIT = 50;

export type HistoryFilter = 'all' | 'completed' | 'failed' | 'cancelled';

/**
 * "All" history sends the terminal statuses as an explicit backend filter so
 * pagination and total_count apply AFTER filtering — dropping in-flight rows
 * client-side would hide older terminal runs behind pages of running jobs.
 */
const ALL_TERMINAL_FILTER = 'completed,failed,cancelled';

/** The rows fetched after the first page, tagged with the filter they belong to. */
export interface AppendedPages {
  filter: HistoryFilter;
  jobs: TrainingJobSummary[];
  skip: number;
}

export function emptyPages(filter: HistoryFilter): AppendedPages {
  return { filter, jobs: [], skip: 0 };
}

/** The appended pages if they belong to `filter`, else none. */
export function pagesFor(appended: AppendedPages, filter: HistoryFilter): AppendedPages {
  return appended.filter === filter ? appended : emptyPages(filter);
}

export function historyQuery(filter: HistoryFilter, skip: number) {
  return {
    status: filter === 'all' ? ALL_TERMINAL_FILTER : filter,
    limit: HISTORY_PAGE_SIZE,
    skip,
  };
}

/** Adds one fetched page to what is already appended for `filter`. */
export function appendPage(
  previous: AppendedPages,
  filter: HistoryFilter,
  jobs: TrainingJobSummary[],
  skip: number
): AppendedPages {
  return { filter, jobs: [...pagesFor(previous, filter).jobs, ...jobs], skip };
}

/**
 * A job can transition pending->running between the two queries and show up in
 * both lists; dedupe by model_id (running wins).
 */
export function mergeInFlight(
  pending: TrainingJobSummary[],
  running: TrainingJobSummary[]
): TrainingJobSummary[] {
  return Array.from(
    new Map([...pending, ...running].map((job) => [job.model_id, job])).values()
  );
}

export function statusBadgeVariant(
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

const NO_VALUE = '—';

export function durationText(job: TrainingJobSummary): string {
  return job.elapsed_seconds != null ? formatDuration(job.elapsed_seconds) : NO_VALUE;
}

export function algorithmText(job: TrainingJobSummary): string {
  return job.best_algorithm ?? NO_VALUE;
}

export function scoreText(job: TrainingJobSummary): string {
  return job.best_score != null ? job.best_score.toFixed(3) : NO_VALUE;
}
