import { useState } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { modelService } from '@/lib/services/model';
import {
  HISTORY_PAGE_SIZE,
  appendPage,
  emptyPages,
  historyQuery,
  pagesFor,
  type AppendedPages,
  type HistoryFilter,
} from './trainingJobs';

/**
 * The finished-job history: a first page that follows the status filter, plus
 * later pages the user asks for. The later pages are appended by `loadMore`
 * rather than by an effect, because paging is user-driven — which is also why
 * the accumulating shape never fitted a keyed loader. They are tagged with their
 * filter, so changing the filter discards them by derivation instead of a reset.
 */
export function useTrainingHistory(isAuthenticated: boolean) {
  const [statusFilter, setStatusFilter] = useState<HistoryFilter>('all');
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [appended, setAppended] = useState<AppendedPages>(emptyPages('all'));

  const { data: firstPage, error, reload } = useAsyncData(
    () => modelService.listTrainingJobs(historyQuery(statusFilter, 0)),
    [isAuthenticated, statusFilter],
    {
      enabled: isAuthenticated,
      errorMessage: 'Failed to fetch training history',
      keepPreviousData: true,
    }
  );

  const pages = pagesFor(appended, statusFilter);
  const total = firstPage?.total_count ?? 0;

  // Append-mode fetches accumulate rows, so rapid clicks would append the
  // same page twice; the button is disabled while a page is in flight.
  const loadMore = async () => {
    if (isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const nextSkip = pages.skip + HISTORY_PAGE_SIZE;
      const response = await modelService.listTrainingJobs(historyQuery(statusFilter, nextSkip));
      setAppended((prev) => appendPage(prev, statusFilter, response.jobs, nextSkip));
    } finally {
      setIsLoadingMore(false);
    }
  };

  // Back to the first page, e.g. after a job finished and joined the history.
  const restart = () => {
    setAppended(emptyPages(statusFilter));
    reload();
  };

  return {
    jobs: [...(firstPage?.jobs ?? []), ...pages.jobs],
    error,
    statusFilter,
    setStatusFilter,
    hasMore: pages.skip + HISTORY_PAGE_SIZE < total,
    isLoadingMore,
    loadMore,
    restart,
  };
}
