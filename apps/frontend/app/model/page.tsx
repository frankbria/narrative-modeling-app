'use client';

import React, { useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useStageGuard } from '@/lib/hooks/useStageGuard';
import { StageNavigation } from '@/components/workflow/StageNavigation';
import type { TrainingMode } from '@/lib/services/model';
import { TrainingNotices, TrainingSetup } from '@/components/model-training/TrainingSetup';
import { StartingRun, TrainingRunView } from '@/components/model-training/TrainingRunView';
import { chosenMode, useTrainingOptions } from '@/components/model-training/useTrainingOptions';
import { useTrainingRun, type TrainingRun } from '@/components/model-training/useTrainingRun';
import { Brain } from 'lucide-react';
import { useSession } from 'next-auth/react';

/** The setup form until a run starts, then the run. */
function TrainingBody(props: { run: TrainingRun; setup: React.ReactNode }) {
  const { run } = props;
  if (!run.training) return props.setup;
  if (!run.modelId) return <StartingRun />;
  return <TrainingRunView modelId={run.modelId} run={run} />;
}

/**
 * Model training page.
 *
 * Lets the analyst pick a target column and run AutoML training. The page holds
 * what the user has chosen; `useTrainingRun` holds the run, and reacts to
 * `TrainingProgress`: on completion it records the stage data in the workflow,
 * on failure or cancellation it returns to the configuration view with a notice.
 * After a run the summary lists the columns training left out, and the user can
 * keep one and train again (#841).
 */
export default function ModelPage() {
  const { data: session } = useSession();
  const { state } = useWorkflow();
  // Guard: redirect (with a message) if this stage is not accessible yet.
  useStageGuard(WorkflowStage.MODEL_TRAINING);
  const [targetColumn, setTargetColumn] = useState('');
  // Training mode (issue #101): null until the user picks one.
  const [modeChoice, setModeChoice] = useState<TrainingMode | null>(null);
  const options = useTrainingOptions(state.datasetId);
  const run = useTrainingRun();
  const mode = chosenMode(modeChoice, options.recommendedMode);
  const start = () => run.start({ targetColumn, mode });

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Please log in to access this page.</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-card rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
          <Brain className="w-6 h-6 text-indigo-500" />
          Model Training
        </h1>

        <TrainingNotices error={run.error} cancelled={run.cancelled && !run.training} />
        <TrainingBody
          run={run}
          setup={
            <TrainingSetup
              columns={options.columns}
              targetColumn={targetColumn}
              onTargetChange={setTargetColumn}
              mode={mode}
              onModeChange={setModeChoice}
              recommendedMode={options.recommendedMode}
              reason={options.reason}
              onStart={start}
            />
          }
        />

        {/* Shared Back / Continue navigation. "Continue to Model Evaluation"
            enables once training completes (modelId recorded on the stage). */}
        <StageNavigation
          currentStage={WorkflowStage.MODEL_TRAINING}
          loading={run.training && !run.completed}
        />
      </div>
    </div>
  );
}
