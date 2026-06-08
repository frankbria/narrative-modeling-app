'use client';

import React, { useEffect, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useRouter } from 'next/navigation';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { modelService, TrainingStatus } from '@/lib/services/model';
import { Brain, Zap, Settings, PlayCircle, AlertCircle } from 'lucide-react';
import { useSession } from 'next-auth/react';

interface ModelConfig {
  problem_type: 'classification' | 'regression';
  target_column: string;
  algorithm: string;
  hyperparameters: Record<string, unknown>;
}

// How often to poll the training status endpoint, in milliseconds.
const STATUS_POLL_INTERVAL_MS = 2000;

export default function ModelPage() {
  const { data: session } = useSession();
  const { state, completeStage, canAccessStage } = useWorkflow();
  const router = useRouter();
  const [training, setTraining] = useState(false);
  const [modelConfig, setModelConfig] = useState<ModelConfig>({
    problem_type: 'classification',
    target_column: '',
    algorithm: 'auto',
    hyperparameters: {}
  });
  const [columns, setColumns] = useState<string[]>([]);
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus | null>(null);
  const [trainingError, setTrainingError] = useState<string | null>(null);

  useEffect(() => {
    if (!canAccessStage(WorkflowStage.MODEL_TRAINING)) {
      router.push('/upload');
      return;
    }

    if (!state.datasetId) {
      router.push('/upload');
      return;
    }

    loadDatasetColumns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canAccessStage, router, state.datasetId]);

  const loadDatasetColumns = async () => {
    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/datasets/${state.datasetId}/schema`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setColumns(data.columns.map((col: { name: string }) => col.name));
      }
    } catch (error) {
      console.error('Failed to load columns:', error);
    }
  };

  const handleTrainModel = async () => {
    if (!state.datasetId) return;

    setTraining(true);
    setTrainingProgress(0);
    setTrainingStatus(null);
    setTrainingError(null);

    try {
      // Start real AutoML training. The backend auto-detects the problem type
      // and the engine compares candidate algorithms, so we only need the
      // dataset and target column here.
      const result = await modelService.trainModel({
        dataset_id: state.datasetId,
        target_column: modelConfig.target_column,
      });

      // Poll the real status endpoint until the job completes or fails, driving
      // the progress bar from the job's actual per-algorithm progress.
      const checkStatus = async () => {
        try {
          const status = await modelService.getTrainingStatus(result.model_id);
          setTrainingStatus(status);
          setTrainingProgress(Math.round(status.progress * 100));

          if (status.status === 'completed') {
            setTrainingProgress(100);
            completeStage(WorkflowStage.MODEL_TRAINING, {
              modelId: result.model_id,
              config: modelConfig,
              metrics: status.metrics,
              bestAlgorithm: status.best_algorithm,
              timestamp: new Date().toISOString(),
            });
          } else if (status.status === 'failed') {
            setTrainingError(status.error || 'Training failed');
            setTraining(false);
          } else {
            setTimeout(checkStatus, STATUS_POLL_INTERVAL_MS);
          }
        } catch (error) {
          console.error('Failed to fetch training status:', error);
          setTrainingError(
            error instanceof Error ? error.message : 'Failed to fetch training status'
          );
          setTraining(false);
        }
      };

      setTimeout(checkStatus, STATUS_POLL_INTERVAL_MS);
    } catch (error) {
      console.error('Failed to train model:', error);
      setTrainingError(
        error instanceof Error ? error.message : 'Failed to start training'
      );
      setTraining(false);
    }
  };

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-600">Please log in to access this page.</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
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

        {!training ? (
          <div className="space-y-6">
            {/* Problem Type Selection */}
            <div>
              <label className="block text-sm font-medium mb-2">Problem Type</label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => setModelConfig(prev => ({ ...prev, problem_type: 'classification' }))}
                  className={`p-4 border-2 rounded-lg transition-colors ${
                    modelConfig.problem_type === 'classification'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <h3 className="font-semibold">Classification</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    Predict categories or classes
                  </p>
                </button>
                <button
                  onClick={() => setModelConfig(prev => ({ ...prev, problem_type: 'regression' }))}
                  className={`p-4 border-2 rounded-lg transition-colors ${
                    modelConfig.problem_type === 'regression'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <h3 className="font-semibold">Regression</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    Predict continuous values
                  </p>
                </button>
              </div>
            </div>

            {/* Target Column Selection */}
            <div>
              <label className="block text-sm font-medium mb-2">Target Column</label>
              <select
                value={modelConfig.target_column}
                onChange={(e) => setModelConfig(prev => ({ ...prev, target_column: e.target.value }))}
                className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Select target column...</option>
                {columns.map(column => (
                  <option key={column} value={column}>{column}</option>
                ))}
              </select>
            </div>

            {/* Algorithm Selection */}
            <div>
              <label className="block text-sm font-medium mb-2">Algorithm</label>
              <div className="grid grid-cols-3 gap-3">
                <button
                  onClick={() => setModelConfig(prev => ({ ...prev, algorithm: 'auto' }))}
                  className={`p-3 border rounded-lg transition-colors ${
                    modelConfig.algorithm === 'auto'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Zap className="w-5 h-5 mx-auto mb-1 text-yellow-500" />
                  <p className="text-sm font-medium">AutoML</p>
                  <p className="text-xs text-gray-500">Let AI choose</p>
                </button>
                <button
                  onClick={() => setModelConfig(prev => ({ ...prev, algorithm: 'random_forest' }))}
                  className={`p-3 border rounded-lg transition-colors ${
                    modelConfig.algorithm === 'random_forest'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Settings className="w-5 h-5 mx-auto mb-1 text-green-500" />
                  <p className="text-sm font-medium">Random Forest</p>
                  <p className="text-xs text-gray-500">Robust & accurate</p>
                </button>
                <button
                  onClick={() => setModelConfig(prev => ({ ...prev, algorithm: 'xgboost' }))}
                  className={`p-3 border rounded-lg transition-colors ${
                    modelConfig.algorithm === 'xgboost'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Settings className="w-5 h-5 mx-auto mb-1 text-purple-500" />
                  <p className="text-sm font-medium">XGBoost</p>
                  <p className="text-xs text-gray-500">High performance</p>
                </button>
              </div>
            </div>

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

            {/* Actions */}
            <div className="flex justify-between pt-4">
              <button
                onClick={() => router.push('/features')}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Back
              </button>
              <button
                onClick={handleTrainModel}
                disabled={!modelConfig.target_column || training}
                className={`px-6 py-2 rounded-lg font-medium flex items-center gap-2 ${
                  modelConfig.target_column && !training
                    ? 'bg-blue-600 text-white hover:bg-blue-700'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                <PlayCircle className="w-5 h-5" />
                Start Training
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
                <Brain className="w-8 h-8 text-blue-600 animate-pulse" />
              </div>
              <h2 className="text-xl font-semibold mb-2">Training Your Model</h2>
              <p className="text-gray-600">
                This may take a few minutes depending on your data size
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>
                  {trainingStatus?.current_algorithm
                    ? `Training ${trainingStatus.current_algorithm}`
                    : 'Progress'}
                </span>
                <span>{trainingProgress}%</span>
              </div>
              <div className="bg-gray-200 rounded-full h-4 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full transition-all duration-500"
                  style={{ width: `${trainingProgress}%` }}
                />
              </div>
              {trainingStatus && trainingStatus.total_algorithms > 0 && (
                <p className="text-sm text-gray-500 text-right">
                  {trainingStatus.completed_algorithms} of{' '}
                  {trainingStatus.total_algorithms} algorithms trained
                </p>
              )}
            </div>

            {trainingStatus?.status === 'completed' && (
              <div className="space-y-4">
                <div className="text-center">
                  <p className="text-green-600 font-medium">Training complete!</p>
                  {trainingStatus.best_algorithm && (
                    <p className="text-sm text-gray-600 mt-1">
                      Best model:{' '}
                      <span className="font-semibold">
                        {trainingStatus.best_algorithm}
                      </span>
                    </p>
                  )}
                </div>

                {trainingStatus.explanation && (
                  <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
                    {trainingStatus.explanation}
                  </p>
                )}

                {trainingStatus.model_comparison.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-gray-500 border-b">
                          <th className="py-2 pr-4">Algorithm</th>
                          <th className="py-2 pr-4">CV Score</th>
                          <th className="py-2 pr-4">Test Score</th>
                          <th className="py-2">Time (s)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {trainingStatus.model_comparison.map((row) => (
                          <tr
                            key={row.algorithm}
                            className={
                              row.algorithm === trainingStatus.best_algorithm
                                ? 'bg-yellow-50 font-medium'
                                : ''
                            }
                          >
                            <td className="py-2 pr-4">{row.algorithm}</td>
                            <td className="py-2 pr-4">
                              {row.cv_score != null ? row.cv_score.toFixed(3) : '—'}
                            </td>
                            <td className="py-2 pr-4">
                              {row.test_score != null ? row.test_score.toFixed(3) : '—'}
                            </td>
                            <td className="py-2">
                              {row.training_time != null
                                ? row.training_time.toFixed(1)
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}