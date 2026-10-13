import { useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import {
  modelService,
  type TrainModelRequest,
  type TrainingMode,
  type TrainingStatus,
} from '@/lib/services/model';
import { excludedFromTraining } from '@/lib/features/columnChoice';

/** One training run: start it, follow it to its end, and start it again keeping columns. */

export interface TrainingChoice {
  targetColumn: string;
  mode: TrainingMode;
}

/** Columns named on the request: kept although a rule set them aside (#841), or left out by the user's own choice (#969). */
export interface ColumnOverrides {
  keep: string[];
  exclude: string[];
}

function featureConfig(columns: ColumnOverrides): TrainModelRequest['feature_config'] {
  const config: TrainModelRequest['feature_config'] = {};
  if (columns.keep.length) config.keep_columns = columns.keep;
  if (columns.exclude.length) config.exclude_columns = columns.exclude;
  return config;
}

export function trainRequest(
  datasetId: string,
  choice: TrainingChoice,
  columns: ColumnOverrides,
): TrainModelRequest {
  // AutoML detects the problem type and compares candidate algorithms, so the
  // dataset, the target and the mode are the whole request, plus any columns named.
  const request: TrainModelRequest = {
    dataset_id: datasetId,
    target_column: choice.targetColumn,
    training_config: { training_mode: choice.mode },
  };
  const config = featureConfig(columns);
  return Object.keys(config ?? {}).length ? { ...request, feature_config: config } : request;
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
      const exclude = excludedFromTraining(
        state.stageData[WorkflowStage.FEATURE_ENGINEERING],
        next.targetColumn,
      );
      const result = await modelService.trainModel(trainRequest(state.datasetId, next, { keep, exclude }));
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
