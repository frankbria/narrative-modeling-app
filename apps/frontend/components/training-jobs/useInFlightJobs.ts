import { useEffect } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { modelService } from '@/lib/services/model';
import {
  IN_FLIGHT_FETCH_LIMIT,
  IN_FLIGHT_REFRESH_MS,
  mergeInFlight,
} from './trainingJobs';

async function fetchInFlightJobs() {
  const [pending, running] = await Promise.all([
    modelService.listTrainingJobs({ status: 'pending', limit: IN_FLIGHT_FETCH_LIMIT }),
    modelService.listTrainingJobs({ status: 'running', limit: IN_FLIGHT_FETCH_LIMIT }),
  ]);
  return mergeInFlight(pending.jobs, running.jobs);
}

/**
 * The pending and running jobs, refreshed every 10 seconds. `isAuthenticated`
 * is a stable flag: a session object gets a fresh identity on re-renders and
 * session refreshes, and keying off it would re-fetch on every render.
 */
export function useInFlightJobs(isAuthenticated: boolean) {
  const { data, loading, error, reload } = useAsyncData(fetchInFlightJobs, [isAuthenticated], {
    enabled: isAuthenticated,
    errorMessage: 'Failed to fetch training jobs',
    // Polling must not blank the list between ticks.
    keepPreviousData: true,
  });

  // Periodic refresh: reload() runs from the timer callback, not the effect body.
  useEffect(() => {
    if (!isAuthenticated) return;
    const intervalId = setInterval(reload, IN_FLIGHT_REFRESH_MS);
    return () => clearInterval(intervalId);
  }, [isAuthenticated, reload]);

  return { jobs: data ?? [], loading, error, reload };
}
