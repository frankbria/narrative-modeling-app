'use client';

import React, { useEffect, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useRouter } from 'next/navigation';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { Brain, Zap, Settings, PlayCircle, AlertCircle } from 'lucide-react';
import { useSession } from 'next-auth/react';

interface ModelConfig {
  problem_type: 'classification' | 'regression';
  target_column: string;
  algorithm: string;
  hyperparameters: Record<string, any>;
}

export default function ModelPage() {
  const { data: session } = useSession();
  const { state, completeStage, canAccessStage } = useWorkflow();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [training, setTraining] = useState(false);
  const [modelConfig, setModelConfig] = useState<ModelConfig>({
    problem_type: 'classification',
    target_column: '',
    algorithm: 'auto',
    hyperparameters: {}
  });
  const [columns, setColumns] = useState<string[]>([]);
  const [trainingProgress, setTrainingProgress] = useState(0);

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
        setColumns(data.columns.map((col: any) => col.name));
      }
    } catch (error) {
      console.error('Failed to load columns:', error);
    }
  };

  const handleTrainModel = async () => {
    setTraining(true);
    setTrainingProgress(0);

    try {
      const token = await getAuthToken();
      
      // Start training
      const response = await fetch(`${API_URL}/models/train`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          dataset_id: state.datasetId,
          ...modelConfig
        })
      });

      if (response.ok) {
        const result = await response.json();
        
        // Simulate progress updates
        const progressInterval = setInterval(() => {
          setTrainingProgress(prev => {
            if (prev >= 90) {
              clearInterval(progressInterval);
              return 100;
            }
            return prev + 10;
          });
        }, 1000);

        // Poll for training status
        const checkStatus = async () => {
          const statusResponse = await fetch(
            `${API_URL}/models/${result.model_id}/status`,
            {
              headers: {
                'Authorization': `Bearer ${token}`
              }
            }
          );

          if (statusResponse.ok) {
            const status = await statusResponse.json();
            if (status.status === 'completed') {
              clearInterval(progressInterval);
              setTrainingProgress(100);
              
              completeStage(WorkflowStage.MODEL_TRAINING, {
                modelId: result.model_id,
                config: modelConfig,
                metrics: status.metrics,
                timestamp: new Date().toISOString()
              });
            } else if (status.status === 'failed') {
              clearInterval(progressInterval);
              setTraining(false);
              // Handle error
            } else {
              // Check again in 2 seconds
              setTimeout(checkStatus, 2000);
            }
          }
        };

        setTimeout(checkStatus, 2000);
      }
    } catch (error) {
      console.error('Failed to train model:', error);
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
                disabled={!modelConfig.target_column || loading}
                className={`px-6 py-2 rounded-lg font-medium flex items-center gap-2 ${
                  modelConfig.target_column && !loading
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
                <span>Progress</span>
                <span>{trainingProgress}%</span>
              </div>
              <div className="bg-gray-200 rounded-full h-4 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full transition-all duration-500"
                  style={{ width: `${trainingProgress}%` }}
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {modelConfig.algorithm === 'auto' ? 'AutoML' : modelConfig.algorithm}
                </p>
                <p className="text-sm text-gray-500">Algorithm</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {modelConfig.problem_type}
                </p>
                <p className="text-sm text-gray-500">Problem Type</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {modelConfig.target_column}
                </p>
                <p className="text-sm text-gray-500">Target</p>
              </div>
            </div>

            {trainingProgress === 100 && (
              <div className="text-center">
                <p className="text-green-600 font-medium">Training complete!</p>
                <p className="text-sm text-gray-600 mt-1">
                  Redirecting to evaluation...
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}