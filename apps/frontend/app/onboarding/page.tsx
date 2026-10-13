"use client";

import React from 'react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, Star } from 'lucide-react';
import { OnboardingStep } from '@/components/OnboardingStep';
import { OnboardingComplete } from '@/components/onboarding/OnboardingComplete';
import { OnboardingSidebar } from '@/components/onboarding/OnboardingSidebar';
import { OnboardingWelcome } from '@/components/onboarding/OnboardingWelcome';
import { useOnboardingFlow } from '@/components/onboarding/useOnboardingFlow';
import type { OnboardingStatus } from '@/components/onboarding/types';

type OnboardingFlow = ReturnType<typeof useOnboardingFlow>;

/**
 * The onboarding tutorial: a shell over `components/onboarding/` (#809).
 *
 * The page sits beside the app's own sidebar, so what it has room for is its
 * container's width, not the viewport's: the progress sidebar is stacked above the
 * step until the page is 48rem wide (`@3xl/page`), then takes a fixed 16rem column.
 */
export default function OnboardingPage() {
  const flow = useOnboardingFlow();
  const { status } = flow;

  if (flow.loading) return LOADING;
  if (flow.error) return <LoadError onRetry={flow.reload} />;
  if (isComplete(status)) return <OnboardingComplete status={status} achievements={flow.achievements} />;

  return (
    <div className="container mx-auto px-4 py-8">
      <Celebration show={flow.showCelebration} />

      <div className="@container/page">
        <div className="grid grid-cols-1 @3xl/page:grid-cols-[16rem_minmax(0,1fr)] gap-6">
          <OnboardingSidebar
            status={status}
            steps={flow.steps}
            achievements={flow.achievements}
            currentStepId={flow.currentStep?.step_id}
            onSelect={flow.selectStep}
          />

          <div className="min-w-0">
            <ActionError message={flow.actionError} />
            <StepOrWelcome flow={flow} />
          </div>
        </div>
      </div>
    </div>
  );
}

function isComplete(status: OnboardingStatus | null): status is OnboardingStatus {
  return Boolean(status && status.is_onboarding_complete);
}

/** The step the user is on, or the welcome card until they have one. */
function StepOrWelcome(props: { flow: OnboardingFlow }) {
  const { flow } = props;
  if (!flow.currentStep) return <OnboardingWelcome onStart={flow.startTutorial} />;
  return (
    <OnboardingStep
      step={flow.currentStep}
      onComplete={flow.completeStep}
      onSkip={flow.skipStep}
      isCompleting={flow.completingStep}
    />
  );
}

const LOADING = (
  <div className="container mx-auto px-4 py-8">
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
    </div>
  </div>
);

function LoadError(props: { onRetry: VoidFunction }) {
  const { onRetry } = props;
  return (
    <div className="container mx-auto p-6 max-w-2xl">
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription className="flex items-center justify-between gap-4">
          <span>Couldn&apos;t load your onboarding progress. Please try again.</span>
          <Button variant="outline" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    </div>
  );
}

function Celebration(props: { show: boolean }) {
  if (!props.show) return null;
  return (
    <Alert className="mb-6 border-green-200 dark:border-green-900 bg-green-50 dark:bg-green-950/40">
      <Star className="h-4 w-4 text-green-600" />
      <AlertDescription className="text-green-800 dark:text-green-200">
        🎉 Amazing! You&apos;ve earned new achievements! Keep going!
      </AlertDescription>
    </Alert>
  );
}

function ActionError(props: { message: string | null }) {
  if (!props.message) return null;
  return (
    <Alert variant="destructive" className="mb-4">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription>{props.message}</AlertDescription>
    </Alert>
  );
}
