import React, { useState } from 'react';
import { HugeiconsIcon } from '@/components/ui/icon';
import { Brain01Icon, Loading03Icon } from '@hugeicons/core-free-icons';
import { TrainingProgress } from '@/components/training/TrainingProgress';
import { TrainingLogs } from '@/components/training/TrainingLogs';
import { CancelTrainingButton } from '@/components/training/CancelTrainingButton';
import type { TrainingStatus } from '@/lib/services/model';
import { ExcludedColumnsPanel } from './ExcludedColumnsPanel';
import type { TrainingRun } from './useTrainingRun';

/**
 * A run in progress and its result. `TrainingProgress` owns the status polling
 * and the terminal success / failure / cancellation alerts; this renders what
 * goes around it.
 */

export function StartingRun() {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
      <HugeiconsIcon icon={Loading03Icon} className="w-5 h-5 animate-spin" />
      <span>Starting training…</span>
    </div>
  );
}

// An element, not a component: it takes nothing and never changes.
const RUN_HEADING = (
    <div className="text-center">
      <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-full mb-4">
        <HugeiconsIcon icon={Brain01Icon} className="w-8 h-8 text-primary animate-pulse" />
      </div>
      <h2 className="text-xl font-semibold mb-2">Training Your Model</h2>
      <p className="text-muted-foreground">
        This may take a few minutes depending on your data size
      </p>
    </div>
);

function CancelControl(props: { modelId: string; run: TrainingRun }) {
  const { modelId, run } = props;
  return (
    <div className="flex flex-col items-center gap-2">
      <CancelTrainingButton
        modelId={modelId}
        disabled={run.cancellationRequested}
        onCancelled={run.requestCancellation}
      />
      {run.cancellationRequested && (
        <p className="text-sm text-muted-foreground">
          Cancellation requested — finishing the current algorithm…
        </p>
      )}
    </div>
  );
}

/** Collapsible live log viewer; keeps polling while the job runs and does a final fetch once it completes. */
function LogsToggle(props: { modelId: string; active: boolean }) {
  const [showLogs, setShowLogs] = useState(false);
  const flip = () => setShowLogs((show) => !show);
  return (
    <div className="space-y-2">
      <button onClick={flip} className="text-sm font-medium text-primary hover:text-primary/80">
        {showLogs ? 'Hide Logs' : 'Show Logs'}
      </button>
      {showLogs && <TrainingLogs modelId={props.modelId} isActive={props.active} />}
    </div>
  );
}

type Recommendation = TrainingStatus['algorithm_recommendations'][number];

function explainability(score: number): string {
  if (score >= 7) return 'Easy to explain';
  if (score >= 4) return 'Somewhat easy to explain';
  return 'Hard to explain';
}

function RecommendationCard(props: { rec: Recommendation }) {
  const { rec } = props;
  return (
    <div className="border border-border rounded-lg p-3">
      <div className="flex items-center justify-between">
        <span className="font-medium text-sm">{rec.algorithm_name}</span>
        <span className="text-xs text-muted-foreground">
          {explainability(rec.interpretability_score)}
        </span>
      </div>
      <p className="text-sm text-muted-foreground mt-1">{rec.explanation}</p>
    </div>
  );
}

function Recommendations(props: { recommendations: Recommendation[]; ranAlgorithms: string[] }) {
  // The selector suggests more algorithms than a quick run trains; list only those that ran.
  const recommendations = props.recommendations.filter((rec) =>
    props.ranAlgorithms.includes(rec.algorithm_name),
  );
  if (recommendations.length === 0) return null;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-foreground">Why these algorithms?</h3>
      <div className="space-y-2">
        {recommendations.map((rec) => (
          <RecommendationCard key={rec.algorithm_name} rec={rec} />
        ))}
      </div>
    </div>
  );
}

function KeptColumns(props: { columns: string[] }) {
  const { columns } = props;
  if (columns.length === 0) return null;
  return (
    <p data-testid="kept-columns" className="text-sm text-muted-foreground">
      Kept at your request: <span className="font-mono">{columns.join(', ')}</span>
    </p>
  );
}

function RunSummary(props: { status: TrainingStatus; run: TrainingRun }) {
  const { status, run } = props;
  return (
    <div className="space-y-4">
      {status.explanation && (
        <p className="text-sm text-muted-foreground bg-muted rounded-lg p-3">{status.explanation}</p>
      )}
      <Recommendations
        recommendations={status.algorithm_recommendations}
        ranAlgorithms={status.model_comparison.map((row) => row.algorithm)}
      />
      <KeptColumns columns={run.keepColumns} />
      <ExcludedColumnsPanel modelId={status.model_id} onRetrain={run.retrainKeeping} />
    </div>
  );
}

export function TrainingRunView(props: { modelId: string; run: TrainingRun }) {
  const { modelId, run } = props;
  const running = !run.completed;
  return (
    <div className="space-y-6">
      {running && RUN_HEADING}
      <TrainingProgress
        modelId={modelId}
        onComplete={run.onComplete}
        onError={run.onError}
        onCancelled={run.onCancelled}
      />
      {running && <CancelControl modelId={modelId} run={run} />}
      <LogsToggle modelId={modelId} active={running} />
      {run.completed && <RunSummary status={run.completed} run={run} />}
    </div>
  );
}
