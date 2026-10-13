import { useState } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { onboardingApi } from '@/lib/services/onboarding';
import type { Achievement, OnboardingStatus, StepInfo } from './types';

interface AchievementsResponse {
  achievements?: Achievement[];
}

interface CompleteStepResponse {
  success?: boolean;
  achievements?: unknown[];
}

interface OnboardingData {
  status: OnboardingStatus | null;
  steps: StepInfo[];
  currentStep: StepInfo | null;
  achievements: Achievement[];
}

/** What the page shows before the first load answers. */
const NOTHING_YET: OnboardingData = { status: null, steps: [], currentStep: null, achievements: [] };

/** The step the backend says is current, or none. */
function currentStepOf(status: OnboardingStatus, steps: StepInfo[]): StepInfo | null {
  if (!status.current_step_id) return null;
  return steps.find((s) => s.step_id === status.current_step_id) || null;
}

// Backend base URL + API bearer, via the one onboarding client (#470). A non-2xx
// throws, so the hook's `error` is set instead of parsing an error page as JSON.
async function loadOnboarding(): Promise<OnboardingData> {
  const status = await onboardingApi.getStatus<OnboardingStatus>();
  const steps = await onboardingApi.getSteps<StepInfo[]>();
  const earned = await onboardingApi.getAchievements<AchievementsResponse>();
  return { status, steps, currentStep: currentStepOf(status, steps), achievements: earned.achievements || [] };
}

function earnedSomething(result: CompleteStepResponse): boolean {
  return Boolean(result.achievements && result.achievements.length > 0);
}

/** The onboarding page's data and its two actions. */
export function useOnboardingFlow() {
  const [completingStep, setCompletingStep] = useState(false);
  const [showCelebration, setShowCelebration] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  // The backend names the current step, and the user can pick another in the sidebar.
  const [selectedStep, setSelectedStep] = useState<StepInfo | null>(null);
  const { data, loading, error, reload } = useAsyncData(loadOnboarding, []);

  const celebrate = () => {
    setShowCelebration(true);
    setTimeout(() => setShowCelebration(false), 3000);
  };

  const completeStep = async (stepId: string, completionData?: Record<string, unknown>) => {
    try {
      setCompletingStep(true);
      setActionError(null);
      const result = await onboardingApi.completeStep<CompleteStepResponse>(stepId, completionData || {});
      if (!result.success) return;
      if (earnedSomething(result)) celebrate();
      await reload();
    } catch (err) {
      console.error('Failed to complete step:', err);
      setActionError("Couldn't save that step. Please try again.");
    } finally {
      setCompletingStep(false);
    }
  };

  const skipStep = async (stepId: string) => {
    try {
      setActionError(null);
      await onboardingApi.skipStep(stepId);
      await reload();
    } catch (err) {
      console.error('Failed to skip step:', err);
      setActionError("Couldn't skip that step. Please try again.");
    }
  };

  const loaded = data || NOTHING_YET;
  // "Start Tutorial" opens the first step.
  const startTutorial = () => {
    const first = loaded.steps.find((s) => s.order === 1);
    if (first) setSelectedStep(first);
  };

  return {
    loading,
    error,
    reload,
    status: loaded.status,
    steps: loaded.steps,
    achievements: loaded.achievements,
    currentStep: selectedStep || loaded.currentStep,
    selectStep: setSelectedStep,
    startTutorial,
    completeStep,
    skipStep,
    completingStep,
    showCelebration,
    actionError,
  };
}
