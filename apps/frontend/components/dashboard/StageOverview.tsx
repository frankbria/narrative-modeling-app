'use client';

import React, { type KeyboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WORKFLOW_STAGES, type StageConfig } from '@/lib/types/workflow';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import {
  Upload,
  BarChart3,
  Wrench,
  Sparkles,
  Brain,
  LineChart,
  Target,
  Rocket,
  ArrowRight,
  Database,
  CheckCircle,
  Lock,
} from 'lucide-react';

// Icon mapping for workflow stages
const STAGE_ICONS: Record<string, React.ElementType> = {
  Upload,
  BarChart3,
  Wrench,
  Sparkles,
  Brain,
  LineChart,
  Target,
  Rocket,
};

type Tone = 'done' | 'current' | 'pending';
type QuickActionsProps = { canTrain: boolean; canDeploy: boolean };
type StageCardProps = {
  stage: StageConfig;
  completed: boolean;
  current: boolean;
  accessible: boolean;
  onOpen(stage: StageConfig): void;
};
type BadgeProps = { completed: boolean; accessible: boolean };

const PILL: Record<Tone, string> = {
  done: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200',
  current: 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200',
  pending: 'bg-muted text-muted-foreground',
};
const TILE: Record<Tone, { box: string; icon: string }> = {
  done: { box: 'bg-green-100 dark:bg-green-900/40', icon: 'text-green-600' },
  current: { box: 'bg-blue-100 dark:bg-blue-900/40', icon: 'text-blue-600' },
  pending: { box: 'bg-muted', icon: 'text-muted-foreground' },
};
const ACCESS = {
  open: { dim: '', tabIndex: 0, suffix: '' },
  locked: { dim: 'opacity-60', tabIndex: -1, suffix: ' (locked)' },
};

// A completed stage reads as done even while it is the current one.
function toneOf(completed: boolean, current: boolean): Tone {
  if (completed) return 'done';
  if (current) return 'current';
  return 'pending';
}

// Stages past the upload carry the dataset they work on in the URL.
function stageHref(route: string, datasetId: string | undefined): string {
  if (datasetId && route !== '/upload') return `${route}/${datasetId}`;
  return route;
}

export function QuickActions(props: QuickActionsProps) {
  const { canTrain, canDeploy } = props;
  const router = useRouter();
  const upload = () => router.push('/upload');
  const train = () => router.push('/model');
  const deployments = () => router.push('/deploy');

  return (
    <Card className="mb-6">
      <CardHeader className="pb-4">
        <CardTitle className="text-lg">Quick Actions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-4">
          <Button onClick={upload} className="flex items-center gap-2">
            <Upload size={16} />
            Upload New Dataset
            <ArrowRight size={16} />
          </Button>
          <Button variant="secondary" onClick={train} disabled={!canTrain} className="flex items-center gap-2">
            <Brain size={16} />
            Train Model
            <ArrowRight size={16} />
          </Button>
          <Button variant="outline" onClick={deployments} disabled={!canDeploy} className="flex items-center gap-2">
            <Rocket size={16} />
            View Deployments
            <ArrowRight size={16} />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function WorkflowProgress() {
  const { state } = useWorkflow();
  const done = state.completedStages;
  const pill = (stage: StageConfig) => {
    const tone = toneOf(done.has(stage.id), state.currentStage === stage.id);
    return (
      <div key={stage.id} className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${PILL[tone]}`}>
        {tone === 'done' && <CheckCircle size={12} />}
        {stage.name}
      </div>
    );
  };

  return (
    <Card className="mb-6" data-testid="workflow-progress">
      <CardHeader>
        <CardTitle className="text-lg">Workflow Progress</CardTitle>
        <CardDescription>
          {done.size} of {WORKFLOW_STAGES.length} stages completed
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Progress value={(done.size / WORKFLOW_STAGES.length) * 100} className="h-3 mb-4" />
        <div className="flex flex-wrap gap-2">{WORKFLOW_STAGES.map(pill)}</div>
      </CardContent>
    </Card>
  );
}

function StageBadge(props: BadgeProps) {
  const { completed, accessible } = props;
  if (completed) return <CheckCircle size={18} className="text-green-500" />;
  if (!accessible) return <Lock size={18} className="text-gray-400" />;
  return null;
}

function StageCard(props: StageCardProps) {
  const { stage, completed, current, accessible, onOpen } = props;
  const Icon = STAGE_ICONS[stage.icon] || Database;
  const tile = TILE[toneOf(completed, current)];
  const access = accessible ? ACCESS.open : ACCESS.locked;
  const ring = current ? 'ring-2 ring-blue-500' : '';
  const open = () => {
    if (accessible) onOpen(stage);
  };
  const openOnEnter = (e: KeyboardEvent) => {
    if (e.key === 'Enter') open();
  };

  return (
    <Card
      className={`cursor-pointer transition-all hover:shadow-md ${access.dim} ${ring}`}
      onClick={open}
      role="button"
      tabIndex={access.tabIndex}
      aria-label={`${stage.name}: ${stage.description}${access.suffix}`}
      onKeyDown={openOnEnter}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div className={`p-2 rounded-lg ${tile.box}`}>
            <Icon size={20} className={tile.icon} />
          </div>
          <StageBadge completed={completed} accessible={accessible} />
        </div>
        <h3 className="font-semibold text-foreground text-sm mb-1">{stage.name}</h3>
        <p className="text-xs text-muted-foreground">{stage.description}</p>
      </CardContent>
    </Card>
  );
}

export function StageCards() {
  const router = useRouter();
  const { state, canAccessStage } = useWorkflow();
  const open = (stage: StageConfig) => router.push(stageHref(stage.route, state.datasetId));
  const card = (stage: StageConfig) => (
    <StageCard
      key={stage.id}
      stage={stage}
      completed={state.completedStages.has(stage.id)}
      current={state.currentStage === stage.id}
      accessible={canAccessStage(stage.id)}
      onOpen={open}
    />
  );

  return (
    <div className="mb-6" data-testid="navigation-cards">
      <h2 className="text-lg font-semibold text-foreground mb-4">Workflow Stages</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">{WORKFLOW_STAGES.map(card)}</div>
    </div>
  );
}

export function HelpCard() {
  const router = useRouter();
  const quickstart = () => router.push('/quickstart');
  const upload = () => router.push('/upload');

  return (
    <Card className="mt-6">
      <CardContent className="py-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h3 className="font-semibold text-foreground">Need help getting started?</h3>
            <p className="text-sm text-muted-foreground">
              Follow the 8-stage workflow to build and deploy your ML models.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={quickstart}>
              Read the Quickstart Guide
            </Button>
            <Button onClick={upload}>
              Start with Data Upload
              <ArrowRight size={14} className="ml-1" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
