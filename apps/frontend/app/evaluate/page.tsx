'use client';

import React, { useEffect, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useRouter } from 'next/navigation';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { LineChart, BarChart3, Target, TrendingUp, AlertTriangle } from 'lucide-react';

export default function EvaluatePage() {
  const { state, completeStage, canAccessStage } = useWorkflow();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [evaluation, setEvaluation] = useState<any>(null);

  useEffect(() => {
    if (!canAccessStage(WorkflowStage.MODEL_EVALUATION)) {
      router.push('/upload');
      return;
    }

    if (!state.modelId) {
      router.push('/model');
      return;
    }

    loadEvaluation();
  }, [canAccessStage, router, state.modelId]);

  const loadEvaluation = async () => {
    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/models/${state.modelId}/evaluation`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setEvaluation(data);
      }
    } catch (error) {
      console.error('Failed to load evaluation:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleProceedToPrediction = () => {
    completeStage(WorkflowStage.MODEL_EVALUATION, {
      evaluationComplete: true,
      metrics: evaluation?.metrics,
      timestamp: new Date().toISOString()
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!evaluation) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-2xl font-semibold mb-2">No Evaluation Data</h2>
          <p className="text-gray-600 mb-4">Model evaluation data is not available.</p>
          <button
            onClick={() => router.push('/model')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go to Model Training
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
          <LineChart className="w-6 h-6 text-purple-500" />
          Model Evaluation
        </h1>

        {/* Performance Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {Object.entries(evaluation.metrics || {}).map(([key, value]: [string, any]) => (
            <div key={key} className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600">
                  {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </span>
                <Target className="w-4 h-4 text-gray-400" />
              </div>
              <div className="text-2xl font-bold text-gray-900">
                {typeof value === 'number' ? value.toFixed(4) : value}
              </div>
              {typeof value === 'number' && (
                <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                    style={{ width: `${Math.min(value * 100, 100)}%` }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Feature Importance */}
        {evaluation.feature_importance && (
          <div className="mb-6">
            <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              Feature Importance
            </h3>
            <div className="space-y-2">
              {evaluation.feature_importance
                .sort((a: any, b: any) => b.importance - a.importance)
                .slice(0, 10)
                .map((feature: any) => (
                  <div key={feature.name} className="flex items-center gap-2">
                    <span className="text-sm text-gray-600 w-32 truncate">
                      {feature.name}
                    </span>
                    <div className="flex-1 h-4 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500"
                        style={{ width: `${feature.importance * 100}%` }}
                      />
                    </div>
                    <span className="text-sm text-gray-700 w-16 text-right">
                      {(feature.importance * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Model Insights */}
        {evaluation.insights && (
          <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h3 className="font-semibold mb-2 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-600" />
              Model Insights
            </h3>
            <ul className="space-y-1 text-sm text-gray-700">
              {evaluation.insights.map((insight: string, idx: number) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-blue-600 mt-0.5">•</span>
                  <span>{insight}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Warnings */}
        {evaluation.warnings && evaluation.warnings.length > 0 && (
          <div className="mb-6 p-4 bg-yellow-50 rounded-lg border border-yellow-200">
            <h3 className="font-semibold mb-2 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-yellow-600" />
              Warnings
            </h3>
            <ul className="space-y-1 text-sm text-yellow-800">
              {evaluation.warnings.map((warning: string, idx: number) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-yellow-600 mt-0.5">!</span>
                  <span>{warning}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex justify-between">
          <button
            onClick={() => router.push('/model')}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Back to Training
          </button>
          <button
            onClick={handleProceedToPrediction}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
          >
            Proceed to Prediction
          </button>
        </div>
      </div>
    </div>
  );
}