"use client";

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { HugeiconsIcon } from '@hugeicons/react';
import { CheckmarkCircle01Icon, CircleIcon, SkipForwardIcon, PlayIcon, Target02Icon } from '@hugeicons/core-free-icons';
import { OnboardingProgress } from '@/components/OnboardingProgress';
import type { Achievement, OnboardingStatus, StepInfo, StepStatus } from './types';

interface OnboardingSidebarProps {
  status: OnboardingStatus | null;
  steps: StepInfo[];
  achievements: Achievement[];
  currentStepId: string | undefined;
  onSelect(step: StepInfo): void;
}

interface StepRowProps {
  step: StepInfo;
  current: boolean;
  onSelect(step: StepInfo): void;
}

const STEP_ICON: Record<StepStatus, React.ReactNode> = {
  completed: <HugeiconsIcon icon={CheckmarkCircle01Icon} className="h-5 w-5 shrink-0 text-success" />,
  in_progress: <HugeiconsIcon icon={PlayIcon} className="h-5 w-5 shrink-0 text-primary" />,
  skipped: <HugeiconsIcon icon={SkipForwardIcon} className="h-5 w-5 shrink-0 text-muted-foreground" />,
  not_started: <HugeiconsIcon icon={CircleIcon} className="h-5 w-5 shrink-0 text-muted-foreground/60" />,
};

const STATUS_COLOR: Record<StepStatus, string> = {
  completed: 'bg-success/10 text-success',
  in_progress: 'bg-primary/10 text-primary',
  skipped: 'bg-muted text-muted-foreground',
  not_started: 'bg-muted text-muted-foreground',
};

const CURRENT_ROW = 'bg-primary/10 border border-primary/30';

/**
 * The progress card and the list of steps (#809).
 *
 * It is a container of its own: the page puts it beside the content or above it
 * depending on the room the page has, and when it is wide (stacked above) the steps
 * sit two to a row instead of in one long column. Titles wrap; they are never cut.
 */
export function OnboardingSidebar(props: OnboardingSidebarProps) {
  const { status, steps, achievements, currentStepId, onSelect } = props;
  const rows = steps.map((step) => (
    <StepRow key={step.step_id} step={step} current={step.step_id === currentStepId} onSelect={onSelect} />
  ));
  return (
    <div className="@container" data-testid="onboarding-sidebar">
      <Card className="@3xl/page:sticky @3xl/page:top-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HugeiconsIcon icon={Target02Icon} className="h-5 w-5" />
            Your Progress
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <OnboardingProgress status={status} achievements={achievements} />

          <div className="space-y-2">
            <h4 className="font-medium text-sm">Tutorial Steps</h4>
            <div className="grid grid-cols-1 @md:grid-cols-2 gap-2">{rows}</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StepRow(props: StepRowProps) {
  const { step, current, onSelect } = props;
  const highlight = current ? CURRENT_ROW : 'hover:bg-muted';
  const select = () => onSelect(step);
  return (
    <button
      type="button"
      aria-current={current ? 'step' : undefined}
      onClick={select}
      className={`flex w-full items-start gap-2 p-2 rounded-md text-left transition-colors ${highlight}`}
    >
      {STEP_ICON[step.status]}
      <span className="flex-1 min-w-0">
        <span className="block text-sm font-medium break-words" data-testid="onboarding-step-title">
          {step.title}
        </span>
        <Badge variant="secondary" className={`text-xs ${STATUS_COLOR[step.status]}`}>
          {step.status.replace('_', ' ')}
        </Badge>
      </span>
    </button>
  );
}
