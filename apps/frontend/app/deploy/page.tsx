'use client';

import React, { useEffect, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useRouter } from 'next/navigation';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { Rocket, Cloud, Shield, Globe, CheckCircle, Copy } from 'lucide-react';

export default function DeployPage() {
  const { state, completeStage, canAccessStage } = useWorkflow();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [deployment, setDeployment] = useState<any>(null);
  const [deploymentStatus, setDeploymentStatus] = useState<'idle' | 'deploying' | 'deployed'>('idle');

  useEffect(() => {
    if (!canAccessStage(WorkflowStage.DEPLOYMENT)) {
      router.push('/upload');
      return;
    }

    if (!state.modelId) {
      router.push('/model');
      return;
    }

    // Check if already deployed
    checkDeploymentStatus();
  }, [canAccessStage, router, state.modelId]);

  const checkDeploymentStatus = async () => {
    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/models/${state.modelId}/deployment`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.deployment) {
          setDeployment(data.deployment);
          setDeploymentStatus('deployed');
        }
      }
    } catch (error) {
      console.error('Failed to check deployment status:', error);
    }
  };

  const handleDeploy = async () => {
    setLoading(true);
    setDeploymentStatus('deploying');

    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/models/${state.modelId}/deploy`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          deployment_type: 'api',
          auto_scaling: true,
          min_instances: 1,
          max_instances: 5
        })
      });

      if (response.ok) {
        const data = await response.json();
        setDeployment(data);
        setDeploymentStatus('deployed');
        
        completeStage(WorkflowStage.DEPLOYMENT, {
          deploymentId: data.id,
          apiEndpoint: data.api_endpoint,
          timestamp: new Date().toISOString()
        });
      }
    } catch (error) {
      console.error('Failed to deploy model:', error);
      setDeploymentStatus('idle');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  if (deploymentStatus === 'idle') {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-md p-8">
          <div className="text-center mb-8">
            <Rocket className="w-16 h-16 text-blue-600 mx-auto mb-4" />
            <h1 className="text-3xl font-bold mb-2">Deploy Your Model</h1>
            <p className="text-gray-600">
              Deploy your trained model to production with one click
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="text-center p-4">
              <Cloud className="w-12 h-12 text-blue-500 mx-auto mb-2" />
              <h3 className="font-semibold mb-1">Cloud Infrastructure</h3>
              <p className="text-sm text-gray-600">
                Automatically provisioned and managed
              </p>
            </div>
            <div className="text-center p-4">
              <Shield className="w-12 h-12 text-green-500 mx-auto mb-2" />
              <h3 className="font-semibold mb-1">Secure API</h3>
              <p className="text-sm text-gray-600">
                API key authentication and rate limiting
              </p>
            </div>
            <div className="text-center p-4">
              <Globe className="w-12 h-12 text-purple-500 mx-auto mb-2" />
              <h3 className="font-semibold mb-1">Global Availability</h3>
              <p className="text-sm text-gray-600">
                Low latency endpoints worldwide
              </p>
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-6 mb-6">
            <h3 className="font-semibold mb-3">Deployment Configuration</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-700">Deployment Type</span>
                <span className="font-medium">REST API</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-700">Auto-scaling</span>
                <span className="font-medium text-green-600">Enabled</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-700">Instance Range</span>
                <span className="font-medium">1-5 instances</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-700">Estimated Cost</span>
                <span className="font-medium">$0.10/1000 requests</span>
              </div>
            </div>
          </div>

          <div className="flex justify-between">
            <button
              onClick={() => router.push('/predict')}
              className="px-4 py-2 text-gray-600 hover:text-gray-800"
            >
              Back
            </button>
            <button
              onClick={handleDeploy}
              disabled={loading}
              className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
            >
              {loading ? 'Deploying...' : 'Deploy Model'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (deploymentStatus === 'deploying') {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <h2 className="text-2xl font-semibold mb-2">Deploying Your Model</h2>
          <p className="text-gray-600">This may take a few moments...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white rounded-lg shadow-md p-8">
        <div className="text-center mb-8">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
          <h1 className="text-3xl font-bold mb-2">Model Deployed Successfully!</h1>
          <p className="text-gray-600">
            Your model is now available via REST API
          </p>
        </div>

        {deployment && (
          <div className="space-y-6">
            <div className="bg-gray-50 rounded-lg p-6">
              <h3 className="font-semibold mb-4">API Endpoint</h3>
              <div className="flex items-center gap-2 mb-2">
                <code className="flex-1 bg-gray-800 text-green-400 p-3 rounded font-mono text-sm">
                  {deployment.api_endpoint}
                </code>
                <button
                  onClick={() => copyToClipboard(deployment.api_endpoint)}
                  className="p-2 hover:bg-gray-200 rounded"
                >
                  <Copy className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="bg-gray-50 rounded-lg p-6">
              <h3 className="font-semibold mb-4">API Key</h3>
              <div className="flex items-center gap-2 mb-2">
                <code className="flex-1 bg-gray-800 text-green-400 p-3 rounded font-mono text-sm">
                  {deployment.api_key}
                </code>
                <button
                  onClick={() => copyToClipboard(deployment.api_key)}
                  className="p-2 hover:bg-gray-200 rounded"
                >
                  <Copy className="w-5 h-5" />
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Keep this key secure. You won't be able to see it again.
              </p>
            </div>

            <div className="bg-blue-50 rounded-lg p-6">
              <h3 className="font-semibold mb-3">Example Request</h3>
              <pre className="bg-gray-800 text-gray-100 p-4 rounded overflow-x-auto text-sm">
{`curl -X POST ${deployment.api_endpoint}/predict \\
  -H "Authorization: Bearer ${deployment.api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "features": {
      "feature1": 123,
      "feature2": "value"
    }
  }'`}
              </pre>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="font-medium mb-2">Status</h4>
                <span className="inline-flex items-center gap-1 text-green-600">
                  <CheckCircle className="w-4 h-4" />
                  Active
                </span>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="font-medium mb-2">Requests Today</h4>
                <span className="text-2xl font-bold">0</span>
              </div>
            </div>
          </div>
        )}

        <div className="mt-8 flex justify-center">
          <button
            onClick={() => router.push('/')}
            className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium"
          >
            Complete Workflow
          </button>
        </div>
      </div>
    </div>
  );
}