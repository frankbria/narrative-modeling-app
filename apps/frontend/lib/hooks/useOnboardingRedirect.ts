import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useOnboardingStatus } from '@/lib/hooks/useOnboardingStatus';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';

type UserId = string | null | undefined;
type OnboardingStatus = { isComplete: boolean; isLoading: boolean; error: unknown };

// localStorage flag set when a returning user opts out of onboarding so the
// dashboard stops redirecting them ("Skip for now" / ?skipOnboarding=true).
// Scoped per user so one account's choice can't bypass onboarding for another
// account on a shared browser.
function onboardingSkipKey(userId: UserId): string {
  return `onboarding_skipped:${userId ?? 'anonymous'}`;
}

/** True once the user has opted out: in this URL (which is remembered), or before. */
function hasSkipped(userId: UserId): boolean {
  const skipKey = onboardingSkipKey(userId);
  if (new URLSearchParams(window.location.search).get('skipOnboarding') === 'true') {
    window.localStorage.setItem(skipKey, 'true');
    return true;
  }
  return window.localStorage.getItem(skipKey) === 'true';
}

// Fails open: a status error or an in-flight request never triggers a redirect.
function shouldOnboard(userId: UserId, status: OnboardingStatus): boolean {
  if (hasSkipped(userId)) return false;
  return !(status.isLoading || status.error || status.isComplete);
}

/**
 * Sends a first-time user from the dashboard into the onboarding flow (issue #152,
 * AC1), unless they asked to skip it.
 */
export function useOnboardingRedirect(): void {
  const router = useRouter();
  const { user } = useCurrentUser();
  const { isComplete, isLoading, error } = useOnboardingStatus();
  const userId = user?.id;

  useEffect(() => {
    if (shouldOnboard(userId, { isComplete, isLoading, error })) router.push('/onboarding');
  }, [isComplete, isLoading, error, userId, router]);
}
