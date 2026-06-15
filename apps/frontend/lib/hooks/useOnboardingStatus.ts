'use client';

/**
 * Onboarding status hook (issue #152).
 *
 * Fetches the authenticated user's onboarding progress from
 * `GET /api/v1/onboarding/status` so callers (e.g. the dashboard) can redirect
 * first-time users into the onboarding flow.
 *
 * Fails open: if the status request errors, `isComplete` stays `true` so a
 * transient backend hiccup never traps a returning user on an onboarding loop.
 */

import { useEffect, useState } from 'react';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';

export interface UseOnboardingStatusResult {
  /** True once all required onboarding steps are done (or on fetch error). */
  isComplete: boolean;
  /** True while the status request is in flight. */
  isLoading: boolean;
  /** The step the user should resume on, if any. */
  currentStepId: string | null;
  /** Set when the status request failed (callers should not redirect on error). */
  error: string | null;
}

export function useOnboardingStatus(): UseOnboardingStatusResult {
  const [isComplete, setIsComplete] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [currentStepId, setCurrentStepId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const token = await getAuthToken();

        const response = await fetch(`${API_URL}/onboarding/status`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch onboarding status (${response.status})`);
        }

        const data = await response.json();
        if (cancelled) return;

        setIsComplete(Boolean(data.is_onboarding_complete));
        setCurrentStepId(data.current_step_id ?? null);
      } catch (err) {
        if (cancelled) return;
        // Fail open — don't trap the user behind a broken status check.
        setIsComplete(true);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    fetchStatus();

    return () => {
      cancelled = true;
    };
  }, []);

  return { isComplete, isLoading, currentStepId, error };
}
