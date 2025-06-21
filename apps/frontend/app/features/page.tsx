'use client';

import React, { useEffect, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useRouter } from 'next/navigation';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { Sparkles, Brain, TrendingUp, AlertCircle } from 'lucide-react';

export default function FeaturesPage() {
  const { state, completeStage, canAccessStage } = useWorkflow();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [features, setFeatures] = useState<any[]>([]);
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [aiSuggestions, setAiSuggestions] = useState<any>(null);

  useEffect(() => {
    if (!canAccessStage(WorkflowStage.FEATURE_ENGINEERING)) {
      router.push('/upload');
      return;
    }

    loadFeatures();
  }, [canAccessStage, router]);

  const loadFeatures = async () => {
    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/datasets/${state.datasetId}/features`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setFeatures(data.features);
        setSelectedFeatures(data.features.map((f: any) => f.name));
        
        // Get AI suggestions
        const suggestionsResponse = await fetch(
          `${API_URL}/datasets/${state.datasetId}/features/suggestions`,
          {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          }
        );
        
        if (suggestionsResponse.ok) {
          const suggestions = await suggestionsResponse.json();
          setAiSuggestions(suggestions);
        }
      }
    } catch (error) {
      console.error('Failed to load features:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFeatureToggle = (featureName: string) => {
    setSelectedFeatures(prev => 
      prev.includes(featureName) 
        ? prev.filter(f => f !== featureName)
        : [...prev, featureName]
    );
  };

  const handleGenerateFeatures = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      const response = await fetch(
        `${API_URL}/datasets/${state.datasetId}/features/generate`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            selectedFeatures,
            generateInteractions: true,
            generatePolynomials: false,
            generateDateFeatures: true
          })
        }
      );

      if (response.ok) {
        const result = await response.json();
        completeStage(WorkflowStage.FEATURE_ENGINEERING, {
          selectedFeatures,
          generatedFeatures: result.newFeatures,
          timestamp: new Date().toISOString()
        });
      }
    } catch (error) {
      console.error('Failed to generate features:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!state.datasetId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-2xl font-semibold mb-2">No Dataset Selected</h2>
          <p className="text-gray-600 mb-4">Please complete the previous steps first.</p>
          <button
            onClick={() => router.push('/upload')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go to Data Loading
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-yellow-500" />
          Feature Engineering
        </h1>

        {/* AI Suggestions */}
        {aiSuggestions && (
          <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h3 className="font-semibold mb-2 flex items-center gap-2">
              <Brain className="w-5 h-5 text-blue-600" />
              AI Recommendations
            </h3>
            <p className="text-sm text-gray-700 mb-3">{aiSuggestions.summary}</p>
            <div className="flex flex-wrap gap-2">
              {aiSuggestions.recommendations?.map((rec: any, idx: number) => (
                <span
                  key={idx}
                  className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                >
                  {rec}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Feature Selection */}
        <div className="space-y-4">
          <h3 className="font-semibold text-lg">Select Features</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {features.map((feature) => (
              <label
                key={feature.name}
                className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedFeatures.includes(feature.name)}
                  onChange={() => handleFeatureToggle(feature.name)}
                  className="w-4 h-4 text-blue-600"
                />
                <div className="flex-1">
                  <span className="font-medium">{feature.name}</span>
                  <span className="text-xs text-gray-500 block">{feature.type}</span>
                </div>
                {feature.importance && (
                  <div className="flex items-center gap-1">
                    <TrendingUp className="w-4 h-4 text-green-600" />
                    <span className="text-xs text-green-600">
                      {(feature.importance * 100).toFixed(0)}%
                    </span>
                  </div>
                )}
              </label>
            ))}
          </div>
        </div>

        {/* Feature Generation Options */}
        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="font-semibold mb-3">Feature Generation Options</h3>
          <div className="space-y-2">
            <label className="flex items-center space-x-2">
              <input type="checkbox" defaultChecked className="w-4 h-4" />
              <span>Generate interaction features</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" defaultChecked className="w-4 h-4" />
              <span>Extract date/time features</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="w-4 h-4" />
              <span>Create polynomial features</span>
            </label>
          </div>
        </div>

        {/* Warning */}
        {selectedFeatures.length < 2 && (
          <div className="mt-4 p-3 bg-yellow-50 rounded-lg border border-yellow-200 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
            <div className="text-sm text-yellow-800">
              <p className="font-semibold">Too few features selected</p>
              <p>Select at least 2 features for effective modeling.</p>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex justify-between">
          <button
            onClick={() => router.push('/prepare')}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Back
          </button>
          <button
            onClick={handleGenerateFeatures}
            disabled={selectedFeatures.length < 2 || loading}
            className={`px-6 py-2 rounded-lg font-medium transition-colors ${
              selectedFeatures.length >= 2 && !loading
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            {loading ? 'Generating...' : 'Generate Features'}
          </button>
        </div>
      </div>
    </div>
  );
}