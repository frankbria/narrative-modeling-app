import { useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { modelService, type TrainingMode, type TrainingStatus } from '@/lib/services/model';

/** One training run: start it, follow it to its end, and start it again keeping columns. */

export interface TrainingChoice {
  targetColumn: string;
  mode: TrainingMode;
}

function trainRequest(datasetId: string, choice: TrainingChoice, keepColumns: string[]) {
  // AutoML detects the problem type and compares candidate algorithms, so the
  // dataset, the target and the mode are the whole request.
  const request = {
    dataset_id: datasetId,
    target_column: choice.targetColumn,
    training_config: { training_mode: choice.mode },
  };
  if (keepColumns.length === 0) return request;
  // Columns the user asked to keep although they read as identifiers or dates (#841).
  return { ...request, feature_config: { keep_columns: keepColumns } };
}

function failureMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to start training';
}

export function useTrainingRun() {
  const { state, completeStage } = useWorkflow();
  const [training, setTraining] = useState(false);
  const [modelId, setModelId] = useState<string | null>(null);
  const [completed, setCompleted] = useState<TrainingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelled, setCancelled] = useState(false);
  const [cancellationRequested, setCancellationRequested] = useState(false);
  const [choice, setChoice] = useState<TrainingChoice | null>(null);
  const [keepColumns, setKeepColumns] = useState<string[]>([]);

  const begin = async (next: TrainingChoice, keep: string[]) => {
    if (!state.datasetId) return;
    setTraining(true);
    setModelId(null);
    setCompleted(null);
    setError(null);
    setCancelled(false);
    setCancellationRequested(false);
    setChoice(next);
    setKeepColumns(keep);
    try {
      // TrainingProgress takes over polling once the job id is known.
      const result = await modelService.trainModel(trainRequest(state.datasetId, next, keep));
      setModelId(result.model_id);
    } catch (err) {
      console.error('Failed to train model:', err);
      setError(failureMessage(err));
      setTraining(false);
    }
  };

  // A run started from the form keeps nothing: the form shows no kept columns,
  // so carrying them over from an earlier run would send them unseen.
  const start = (next: TrainingChoice) => begin(next, []);

  /** Run the same training again with these columns kept as features, on top of any kept before. */
  const retrainKeeping = (columns: string[]) => {
    if (!choice) return;
    return begin(choice, [...new Set([...keepColumns, ...columns])]);
  };

  const onComplete = (status: TrainingStatus) => {
    setCompleted(status);
    completeStage(WorkflowStage.MODEL_TRAINING, {
      modelId: status.model_id,
      config: { target_column: choice?.targetColumn },
      metrics: status.metrics,
      bestAlgorithm: status.best_algorithm,
      timestamp: new Date().toISOString(),
    });
  };

  const onError = (status: TrainingStatus) => {
    setError(status.error || 'Training failed');
    setTraining(false);
    setModelId(null);
  };

  const onCancelled = () => {
    setCancelled(true);
    setTraining(false);
    setModelId(null);
  };

  const requestCancellation = () => setCancellationRequested(true);

  return {
    training,
    modelId,
    completed,
    error,
    cancelled,
    cancellationRequested,
    keepColumns,
    start,
    retrainKeeping,
    onComplete,
    onError,
    onCancelled,
    requestCancellation,
  };
}

export type TrainingRun = ReturnType<typeof useTrainingRun>;
