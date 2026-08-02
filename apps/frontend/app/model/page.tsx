'use client';

import React, { useState } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useStageGuard } from '@/lib/hooks/useStageGuard';
import { StageNavigation } from '@/components/workflow/StageNavigation';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { modelService, TrainingStatus, TrainingMode } from '@/lib/services/model';
import { TrainingProgress } from '@/components/training/TrainingProgress';
import { TrainingLogs } from '@/components/training/TrainingLogs';
import { CancelTrainingButton } from '@/components/training/CancelTrainingButton';
import { TrainingModeSelector } from '@/components/TrainingModeSelector';
import { Brain, Zap, PlayCircle, AlertCircle, Info, Loader2 } from 'lucide-react';
import { useSession } from 'next-auth/react';

interface ModelConfig {
  // AutoML auto-detects the problem type and chooses the algorithm, so the
  // target column is the only user-provided training input.
  target_column: string;
}

/**
 * Model training page.
 *
 * Lets the analyst pick a target column and run AutoML training. The
 * `TrainingProgress` component owns the status polling and renders the live
 * progress (stage, algorithm, timing, comparison) plus the terminal success /
 * failure / cancellation alerts; this page reacts to its callbacks: on
 * completion it records the stage data in the workflow and renders the
 * best-model explanation and algorithm recommendations, on failure or
 * cancellation it returns to the configuration view with a notice. A
 * collapsible `TrainingLogs` panel and a `CancelTrainingButton` accompany the
 * progress display while the job runs.
 */
export default function ModelPage() {
  const { data: session } = useSession();
  const { state, completeStage } = useWorkflow();
  const [training, setTraining] = useState(false);
  const [modelConfig, setModelConfig] = useState<ModelConfig>({
    target_column: ''
  });
  const [trainingModelId, setTrainingModelId] = useState<string | null>(null);
  const [completedStatus, setCompletedStatus] = useState<TrainingStatus | null>(null);
  const [trainingError, setTrainingError] = useState<string | null>(null);
  const [cancelledNotice, setCancelledNotice] = useState(false);
  const [cancellationRequested, setCancellationRequested] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  // Training mode (issue #101). Defaults to Quick; updated to the dataset-based
  // recommendation when it loads (before the user interacts).
  // A user pick beats the recommendation, including one that arrives later.
  // Expressed as an override rather than a ref + conditional setState: null means
  // "untouched", so a late recommendation simply shows through.
  const [modeChoice, setModeChoice] = useState<TrainingMode | null>(null);

  const handleModeChange = (mode: TrainingMode) => {
    setModeChoice(mode);
  };

  // Guard: redirect (with a message) if this stage is not accessible yet.
  useStageGuard(WorkflowStage.MODEL_TRAINING);

  // Two independent loads, deliberately NOT combined: the recommendation is
  // advisory and can be slow, and folding it in with the columns would make the
  // whole form wait on it. A test pins that — it defers the recommendation and
  // still expects the column options to render.
  const { data: columnData } = useAsyncData(
    async () => {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/datasets/${state.datasetId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return [] as string[];
      const body = await response.json();
      return ((body.data_schema ?? []) as { field_name: string }[]).map(
        (field) => field.field_name
      );
    },
    [state.datasetId],
    { enabled: !!state.datasetId },
  );

  const { data: recommendation } = useAsyncData(
    // Advisory only — a failure just leaves the Quick default in place.
    () =>
      modelService
        .getModeRecommendation(state.datasetId as string)
        .catch((error) => {
          console.error('Failed to load mode recommendation:', error);
          return null;
        }),
    [state.datasetId],
    { enabled: !!state.datasetId },
  );

  const columns = columnData ?? [];
  const recommendedMode = recommendation?.recommended_mode;
  const recommendationReason = recommendation?.reason;
  const trainingMode: TrainingMode = modeChoice ?? recommendedMode ?? 'quick';

  const handleTrainModel = async () => {
    if (!state.datasetId) return;

    setTraining(true);
    setTrainingModelId(null);
    setCompletedStatus(null);
    setTrainingError(null);
    setCancelledNotice(false);
    setCancellationRequested(false);
    setShowLogs(false);

    try {
      // Start real AutoML training. The backend auto-detects the problem type
      // and the engine compares candidate algorithms, so we only need the
      // dataset and target column here. TrainingProgress takes over polling
      // once the job id is known.
      const result = await modelService.trainModel({
        dataset_id: state.datasetId,
        target_column: modelConfig.target_column,
        training_config: { training_mode: trainingMode },
      });

      setTrainingModelId(result.model_id);
    } catch (error) {
      console.error('Failed to train model:', error);
      setTrainingError(
        error instanceof Error ? error.message : 'Failed to start training'
      );
      setTraining(false);
    }
  };

  const handleTrainingComplete = (status: TrainingStatus) => {
    setCompletedStatus(status);
    completeStage(WorkflowStage.MODEL_TRAINING, {
      modelId: status.model_id,
      config: modelConfig,
      metrics: status.metrics,
      bestAlgorithm: status.best_algorithm,
      timestamp: new Date().toISOString(),
    });
  };

  const handleTrainingError = (status: TrainingStatus) => {
    setTrainingError(status.error || 'Training failed');
    setTraining(false);
    setTrainingModelId(null);
  };

  const handleTrainingCancelled = () => {
    setCancelledNotice(true);
    setTraining(false);
    setTrainingModelId(null);
  };

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

        {/* Training errors are shown above the form so they remain visible after
            a failure returns the user to the configuration view. */}
        {trainingError && (
          <div className="mb-6 p-3 bg-red-50 rounded-lg border border-red-200 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
            <div className="text-sm text-red-800">
              <p className="font-semibold">Training failed</p>
              <p>{trainingError}</p>
            </div>
          </div>
        )}

        {/* A cancelled run returns the analyst to the configuration view with a
            notice so they can adjust the setup and start a new run. */}
        {cancelledNotice && !training && (
          <div className="mb-6 p-3 bg-blue-50 rounded-lg border border-blue-200 flex items-start gap-2">
            <Info className="w-5 h-5 text-blue-600 mt-0.5" />
            <div className="text-sm text-blue-800">
              <p className="font-semibold">Training cancelled</p>
              <p>The training run was stopped. You can start a new run below.</p>
            </div>
          </div>
        )}

        {!training ? (
          <div className="space-y-6">
            {/* AutoML auto-detects the problem type and compares several
                algorithms, so the only required input is the target column.
                The training mode (issue #101) tunes how many algorithms run and
                the time budget. */}
            <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-200 flex items-start gap-3">
              <Zap className="w-5 h-5 text-indigo-500 mt-0.5" />
              <div className="text-sm text-indigo-900">
                <p className="font-semibold">AI-guided AutoML</p>
                <p className="mt-1 text-indigo-800">
                  We automatically detect whether this is a classification or
                  regression problem, train and cross-validate several algorithms
                  (Logistic/Linear Regression, Random Forest, XGBoost and more),
                  and pick the best model — with an explanation of why.
                </p>
              </div>
            </div>

            {/* Target Column Selection */}
            <div>
              <label className="block text-sm font-medium mb-2">Target Column</label>
              <select
                value={modelConfig.target_column}
                onChange={(e) => setModelConfig(prev => ({ ...prev, target_column: e.target.value }))}
                className="w-full p-2 border border-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Select target column...</option>
                {columns.map(column => (
                  <option key={column} value={column}>{column}</option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground mt-1">
                The column you want the model to predict.
              </p>
            </div>

            {/* Training mode (issue #101): Quick vs Comprehensive. */}
            <TrainingModeSelector
              value={trainingMode}
              onChange={handleModeChange}
              recommendedMode={recommendedMode}
              reason={recommendationReason}
            />

            {/* Warning */}
            {!modelConfig.target_column && (
              <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-200 flex items-start gap-2">
                <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
                <div className="text-sm text-yellow-800">
                  <p className="font-semibold">Target column required</p>
                  <p>Please select the column you want to predict.</p>
                </div>
              </div>
            )}

            {/* Action: start training. Back / Continue live in the shared
                StageNavigation footer below. */}
            <div className="flex justify-end pt-4">
              <button
                onClick={handleTrainModel}
                disabled={!modelConfig.target_column || training}
                className={`px-6 py-2 rounded-lg font-medium flex items-center gap-2 ${
                  modelConfig.target_column && !training
                    ? 'bg-blue-600 text-white hover:bg-blue-700'
                    : 'bg-gray-300 text-muted-foreground cursor-not-allowed'
                }`}
              >
                <PlayCircle className="w-5 h-5" />
                Start Training
              </button>
            </div>
          </div>
        ) : !trainingModelId ? (
          <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Starting training…</span>
          </div>
        ) : (
          <div className="space-y-6">
            {!completedStatus && (
              <div className="text-center">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
                  <Brain className="w-8 h-8 text-blue-600 animate-pulse" />
                </div>
                <h2 className="text-xl font-semibold mb-2">Training Your Model</h2>
                <p className="text-muted-foreground">
                  This may take a few minutes depending on your data size
                </p>
              </div>
            )}

            <TrainingProgress
              modelId={trainingModelId}
              onComplete={handleTrainingComplete}
              onError={handleTrainingError}
              onCancelled={handleTrainingCancelled}
            />

            {!completedStatus && (
              <div className="flex flex-col items-center gap-2">
                <CancelTrainingButton
                  modelId={trainingModelId}
                  disabled={cancellationRequested}
                  onCancelled={() => setCancellationRequested(true)}
                />
                {cancellationRequested && (
                  <p className="text-sm text-muted-foreground">
                    Cancellation requested — finishing the current algorithm…
                  </p>
                )}
              </div>
            )}

            {/* Collapsible live log viewer; keeps polling while the job runs and
                does a final fetch once it completes. */}
            <div className="space-y-2">
              <button
                onClick={() => setShowLogs((show) => !show)}
                className="text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                {showLogs ? 'Hide Logs' : 'Show Logs'}
              </button>
              {showLogs && (
                <TrainingLogs
                  modelId={trainingModelId}
                  isActive={!completedStatus}
                />
              )}
            </div>

            {completedStatus && (
              <div className="space-y-4">
                {completedStatus.explanation && (
                  <p className="text-sm text-muted-foreground bg-muted rounded-lg p-3">
                    {completedStatus.explanation}
                  </p>
                )}

                {completedStatus.algorithm_recommendations.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-foreground">
                      Why these algorithms?
                    </h3>
                    <div className="space-y-2">
                      {completedStatus.algorithm_recommendations.map((rec) => (
                        <div
                          key={rec.algorithm_name}
                          className="border border-border rounded-lg p-3"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-sm">
                              {rec.algorithm_name}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              Priority {rec.priority}/10 · Interpretability{' '}
                              {rec.interpretability_score}/10
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {rec.explanation}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Shared Back / Continue navigation. "Continue to Model Evaluation"
            enables once training completes (modelId recorded on the stage). */}
        <StageNavigation currentStage={WorkflowStage.MODEL_TRAINING} loading={training && !completedStatus} />
      </div>
    </div>
  );
}
