'use client';

import React, { type KeyboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WORKFLOW_STAGES, type StageConfig } from '@/lib/types/workflow';
import { buildStageUrl } from '@/lib/utils/stageValidation';
import { Button } from '@/components/ui/button';
import { Upload, Brain, Rocket, ArrowRight } from 'lucide-react';

type QuickActionsProps = { canTrain: boolean; canDeploy: boolean };
type StageChipProps = {
  stage: StageConfig;
  completed: boolean;
  current: boolean;
  accessible: boolean;
  onOpen(stage: StageConfig): void;
};

/** The secondary ways in: a new dataset, training, deployments. */
export function QuickActions(props: QuickActionsProps) {
  const { canTrain, canDeploy } = props;
  const router = useRouter();
  const upload = () => router.push('/upload');
  const train = () => router.push('/model');
  const deployments = () => router.push('/deploy');

  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" size="sm" onClick={upload}>
        <Upload size={14} />
        Upload New Dataset
      </Button>
      <Button variant="outline" size="sm" onClick={train} disabled={!canTrain}>
        <Brain size={14} />
        Train Model
      </Button>
      <Button variant="outline" size="sm" onClick={deployments} disabled={!canDeploy}>
        <Rocket size={14} />
        View Deployments
      </Button>
    </div>
  );
}

function stripFill(completed: boolean, current: boolean): string {
  if (current) return 'bg-highlight';
  return completed ? 'bg-primary' : 'bg-border';
}
const stageConfigOf = (id: StageConfig['id']) => WORKFLOW_STAGES.find((stage) => stage.id === id) ?? WORKFLOW_STAGES[0];
// Locked stages leave the tab order.
const TAB_INDEX = { true: 0, false: -1 };
const labelWeight = (current: boolean) => (current ? 'font-bold text-foreground' : 'text-muted-foreground');
const labelHover = (accessible: boolean) => (accessible ? 'group-hover:text-foreground' : '');
const chipLabel = (current: boolean, accessible: boolean) => `${labelWeight(current)} ${labelHover(accessible)}`;
const lockedSuffix = (accessible: boolean) => (accessible ? '' : ' (locked)');
const cursor = (accessible: boolean) => (accessible ? 'cursor-pointer' : 'cursor-not-allowed');

// One cell of the stage strip: done cells are petrol, the open stage is the
// highlighter cell, locked ones are blank.
function StageChip(props: StageChipProps) {
  const { stage, completed, current, accessible, onOpen } = props;
  const open = () => {
    if (accessible) onOpen(stage);
  };
  const openOnEnter = (e: KeyboardEvent) => {
    if (e.key === 'Enter') open();
  };
  const fill = stripFill(completed, current);
  const label = chipLabel(current, accessible);

  return (
    <li className="min-w-0 flex-1">
      <div
        role="button"
        tabIndex={TAB_INDEX[`${accessible}`]}
        aria-label={`${stage.name}: ${stage.description}${lockedSuffix(accessible)}`}
        onClick={open}
        onKeyDown={openOnEnter}
        className={`group grid gap-1.5 rounded-md p-1 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 ${cursor(accessible)}`}
      >
        <span className={`h-1.5 rounded-full ${fill}`} />
        <span
          className={`hidden truncate text-xs sm:block ${label}`}
        >
          {stage.tab}
        </span>
      </div>
    </li>
  );
}

/**
 * The one progress surface on the dashboard: where you are, what is next, and the
 * eight stages as a strip you can jump through. It replaced a progress bar, a row
 * of stage pills and a grid of stage tiles that all said the same thing.
 */
export function ResumeCard(props: QuickActionsProps) {
  const router = useRouter();
  const { state, canAccessStage } = useWorkflow();
  const done = state.completedStages;
  const current = stageConfigOf(state.currentStage);
  const open = (stage: StageConfig) => router.push(buildStageUrl(stage.id, state.datasetId));
  const chip = (stage: StageConfig) => (
    <StageChip
      key={stage.id}
      stage={stage}
      completed={done.has(stage.id)}
      current={state.currentStage === stage.id}
      accessible={canAccessStage(stage.id)}
      onOpen={open}
    />
  );

  return (
    <section
      className="mb-6 rounded-xl border border-border bg-card p-5 shadow-[inset_4px_0_0_var(--primary)] sm:p-6"
      data-testid="workflow-progress"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-muted-foreground">Continue where you left off</p>
          <h2 className="mt-1 text-xl font-bold text-foreground">{current.name}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {current.description}. {done.size} of {WORKFLOW_STAGES.length} stages completed.
          </p>
        </div>
        <Button onClick={() => open(current)}>
          Open {current.tab}
          <ArrowRight size={16} />
        </Button>
      </div>
      <ol className="mt-5 flex gap-1" data-testid="navigation-cards" aria-label="Workflow stages">
        {WORKFLOW_STAGES.map(chip)}
      </ol>
      <div className="mt-5 border-t border-border pt-4">
        <QuickActions {...props} />
      </div>
    </section>
  );
}
