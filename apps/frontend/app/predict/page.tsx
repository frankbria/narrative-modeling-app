'use client';

import React, { useEffect, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useRouter } from 'next/navigation';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { Target, Upload, FileText, Send, CheckCircle } from 'lucide-react';
import { useSession } from 'next-auth/react';

interface PredictionInput {
  [key: string]: any;
}

export default function PredictPage() {
  const { data: session } = useSession();
  const { state, completeStage, canAccessStage } = useWorkflow();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [predictionMode, setPredictionMode] = useState<'single' | 'batch'>('single');
  const [features, setFeatures] = useState<any[]>([]);
  const [predictionInput, setPredictionInput] = useState<PredictionInput>({});
  const [prediction, setPrediction] = useState<any>(null);
  const [batchFile, setBatchFile] = useState<File | null>(null);

  useEffect(() => {
    if (!canAccessStage(WorkflowStage.PREDICTION)) {
      router.push('/upload');
      return;
    }

    if (!state.modelId) {
      router.push('/model');
      return;
    }

    loadModelFeatures();
  }, [canAccessStage, router, state.modelId]);

  const loadModelFeatures = async () => {
    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/models/${state.modelId}/features`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setFeatures(data.features);
        
        // Initialize input with default values
        const defaultInput: PredictionInput = {};
        data.features.forEach((feature: any) => {
          defaultInput[feature.name] = feature.type === 'numeric' ? 0 : '';
        });
        setPredictionInput(defaultInput);
      }
    } catch (error) {
      console.error('Failed to load features:', error);
    }
  };

  const handleSinglePrediction = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/models/${state.modelId}/predict`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          features: predictionInput
        })
      });

      if (response.ok) {
        const result = await response.json();
        setPrediction(result);
        
        // Mark stage as complete
        if (!state.completedStages.has(WorkflowStage.PREDICTION)) {
          completeStage(WorkflowStage.PREDICTION, {
            firstPrediction: result,
            timestamp: new Date().toISOString()
          });
        }
      }
    } catch (error) {
      console.error('Failed to make prediction:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleBatchPrediction = async () => {
    if (!batchFile) return;

    setLoading(true);
    try {
      const token = await getAuthToken();
      const formData = new FormData();
      formData.append('file', batchFile);

      const response = await fetch(`${API_URL}/models/${state.modelId}/predict/batch`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (response.ok) {
        const result = await response.json();
        
        // Download results
        window.open(result.download_url, '_blank');
        
        // Mark stage as complete
        if (!state.completedStages.has(WorkflowStage.PREDICTION)) {
          completeStage(WorkflowStage.PREDICTION, {
            batchPrediction: true,
            timestamp: new Date().toISOString()
          });
        }
      }
    } catch (error) {
      console.error('Failed to process batch prediction:', error);
    } finally {
      setLoading(false);
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
          <Target className="w-6 h-6 text-red-500" />
          Make Predictions
        </h1>

        {/* Mode Selection */}
        <div className="mb-6">
          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => setPredictionMode('single')}
              className={`p-4 border-2 rounded-lg transition-colors ${
                predictionMode === 'single'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <Target className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <h3 className="font-semibold">Single Prediction</h3>
              <p className="text-sm text-gray-600 mt-1">
                Enter values manually for one prediction
              </p>
            </button>
            <button
              onClick={() => setPredictionMode('batch')}
              className={`p-4 border-2 rounded-lg transition-colors ${
                predictionMode === 'batch'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <FileText className="w-8 h-8 text-green-600 mx-auto mb-2" />
              <h3 className="font-semibold">Batch Prediction</h3>
              <p className="text-sm text-gray-600 mt-1">
                Upload a CSV file for multiple predictions
              </p>
            </button>
          </div>
        </div>

        {predictionMode === 'single' ? (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg">Enter Feature Values</h3>
            
            <div className="grid grid-cols-2 gap-4">
              {features.map((feature) => (
                <div key={feature.name}>
                  <label className="block text-sm font-medium mb-1">
                    {feature.name}
                  </label>
                  {feature.type === 'numeric' ? (
                    <input
                      type="number"
                      value={predictionInput[feature.name] || 0}
                      onChange={(e) => setPredictionInput(prev => ({
                        ...prev,
                        [feature.name]: parseFloat(e.target.value)
                      }))}
                      className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  ) : (
                    <input
                      type="text"
                      value={predictionInput[feature.name] || ''}
                      onChange={(e) => setPredictionInput(prev => ({
                        ...prev,
                        [feature.name]: e.target.value
                      }))}
                      className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  )}
                </div>
              ))}
            </div>

            {prediction && (
              <div className="mt-6 p-4 bg-green-50 rounded-lg border border-green-200">
                <h4 className="font-semibold mb-2 flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  Prediction Result
                </h4>
                <div className="text-2xl font-bold text-gray-900">
                  {prediction.prediction}
                </div>
                {prediction.confidence && (
                  <div className="mt-2">
                    <span className="text-sm text-gray-600">Confidence: </span>
                    <span className="font-medium">
                      {(prediction.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                )}
                {prediction.probabilities && (
                  <div className="mt-3 space-y-1">
                    <p className="text-sm text-gray-600">Class Probabilities:</p>
                    {Object.entries(prediction.probabilities).map(([cls, prob]: [string, any]) => (
                      <div key={cls} className="flex justify-between text-sm">
                        <span>{cls}:</span>
                        <span className="font-medium">{(prob * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <button
              onClick={handleSinglePrediction}
              disabled={loading}
              className={`w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 ${
                !loading
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              <Send className="w-5 h-5" />
              {loading ? 'Making Prediction...' : 'Make Prediction'}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <h3 className="font-semibold text-lg">Upload Batch File</h3>
            
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setBatchFile(e.target.files?.[0] || null)}
                className="hidden"
                id="batch-file-input"
              />
              <label
                htmlFor="batch-file-input"
                className="cursor-pointer text-blue-600 hover:text-blue-700 font-medium"
              >
                Click to upload CSV file
              </label>
              {batchFile && (
                <p className="mt-2 text-sm text-gray-600">
                  Selected: {batchFile.name}
                </p>
              )}
            </div>

            <div className="p-4 bg-blue-50 rounded-lg">
              <h4 className="font-semibold mb-2">Expected Format</h4>
              <p className="text-sm text-gray-700">
                Your CSV should have columns matching the feature names:
              </p>
              <p className="text-xs font-mono mt-2 text-gray-600">
                {features.map(f => f.name).join(', ')}
              </p>
            </div>

            <button
              onClick={handleBatchPrediction}
              disabled={!batchFile || loading}
              className={`w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 ${
                batchFile && !loading
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              <Send className="w-5 h-5" />
              {loading ? 'Processing...' : 'Process Batch Predictions'}
            </button>
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex justify-between">
          <button
            onClick={() => router.push('/evaluate')}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Back
          </button>
          {state.completedStages.has(WorkflowStage.PREDICTION) && (
            <button
              onClick={() => router.push('/deploy')}
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium"
            >
              Continue to Deployment
            </button>
          )}
        </div>
      </div>
    </div>
  );
}