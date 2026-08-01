'use client';

import React, { useEffect, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useStageGuard } from '@/lib/hooks/useStageGuard';
import { StageNavigation } from '@/components/workflow/StageNavigation';
import { useRouter } from 'next/navigation';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { Rocket, Cloud, Shield, Globe, CheckCircle, Copy, BookOpen } from 'lucide-react';
import type { DeployResponse, ModelDeploymentView } from '@/lib/types/api';
import { modelService } from '@/lib/services/model';
import type { ModelFeatureDescriptor } from '@/lib/services/model';
import { EndpointTester } from '@/components/EndpointTester';
import { SdkPanel } from '@/components/SdkPanel';

export default function DeployPage() {
  const { state, completeStage, requestStageRedirect } = useWorkflow();
  const router = useRouter();
  const { ready } = useStageGuard(WorkflowStage.DEPLOYMENT);
  const [loading, setLoading] = useState(false);
  const [deployment, setDeployment] = useState<DeployResponse | null>(null);
  const [deploymentStatus, setDeploymentStatus] = useState<'idle' | 'deploying' | 'deployed'>('idle');
  // Real features for the example request (AC3). Empty until loaded.
  const [exampleFeatures, setExampleFeatures] = useState<ModelFeatureDescriptor[]>([]);

  useEffect(() => {
    if (deploymentStatus !== 'deployed' || !state.modelId) return;
    let active = true;
    modelService
      .getModelFeatures(state.modelId)
      .then((data) => {
        if (active) setExampleFeatures(data.features);
      })
      .catch(() => {
        /* example falls back to a generic body */
      });
    return () => {
      active = false;
    };
  }, [deploymentStatus, state.modelId]);

  // FastAPI serves the interactive Swagger UI at the host root `/docs`; API_URL
  // includes the `/api/v1` prefix, so strip it to reach the docs page.
  const docsUrl = `${API_URL.replace(/\/api\/v1\/?$/, '')}/docs`;

  const checkDeploymentStatus = async () => {
    try {
      const token = await getAuthToken();
      // Real trained models are MLModel documents served at /ml/{id} (issue #84;
      // the old /models/{id} ModelConfig surface is dead and 404s). Deployment
      // state lives on the model record's top-level fields.
      const response = await fetch(`${API_URL}/ml/${state.modelId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = (await response.json()) as ModelDeploymentView;
        if (data.is_deployed) {
          setDeployment({
            model_id: state.modelId ?? '',
            status: 'deployed',
            deployed_at: data.deployed_at ?? '',
            deployment_endpoint: data.deployment_endpoint ?? null,
            message: 'Model is deployed'
          });
          setDeploymentStatus('deployed');
        }
      }
    } catch (error) {
      console.error('Failed to check deployment status:', error);
    }
  };

  useEffect(() => {
    // Stage access (with a helpful redirect) is handled by useStageGuard.
    if (!ready) return;
    if (!state.modelId) {
      requestStageRedirect(
        WorkflowStage.MODEL_TRAINING,
        'Train a model before deploying it.'
      );
      return;
    }
    // Check if already deployed
    checkDeploymentStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, state.modelId]);

  const handleDeploy = async () => {
    setLoading(true);
    setDeploymentStatus('deploying');

    try {
      const token = await getAuthToken();
      // Backend route is PUT /ml/{id}/deploy on the real MLModel surface (issue
      // #84). The backend synthesizes the production serving URL when `endpoint`
      // is omitted, but we supply it explicitly so the URL matches the host the
      // browser is talking to (the route at /production/v1/models/{id}/predict).
      const servingEndpoint = `${API_URL}/production/v1/models/${state.modelId}`;
      const response = await fetch(`${API_URL}/ml/${state.modelId}/deploy`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ endpoint: servingEndpoint })
      });

      if (response.ok) {
        const data = (await response.json()) as DeployResponse;
        setDeployment(data);
        setDeploymentStatus('deployed');

        completeStage(WorkflowStage.DEPLOYMENT, {
          deploymentId: data.model_id,
          apiEndpoint: data.deployment_endpoint,
          timestamp: new Date().toISOString()
        });
      } else {
        // A 4xx/5xx does not throw; without this the spinner would hang forever.
        console.error(`Failed to deploy model: ${response.status} ${response.statusText}`);
        setDeploymentStatus('idle');
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
              {deployment.deployment_endpoint ? (
                <div className="flex items-center gap-2 mb-2">
                  <code className="flex-1 bg-gray-800 text-green-400 p-3 rounded font-mono text-sm">
                    {deployment.deployment_endpoint}
                  </code>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(deployment.deployment_endpoint!)}
                    aria-label="Copy API endpoint"
                    className="p-2 hover:bg-gray-200 rounded"
                  >
                    <Copy className="w-5 h-5" />
                  </button>
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No endpoint URL was assigned. Your model is deployed and ready to serve predictions.
                </p>
              )}
            </div>

            <div className="bg-blue-50 rounded-lg p-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold">Example Request</h3>
                <a
                  href={docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-blue-700 hover:underline"
                >
                  <BookOpen className="w-4 h-4" />
                  View interactive API docs
                </a>
              </div>
              <pre className="bg-gray-800 text-gray-100 p-4 rounded overflow-x-auto text-sm">
{`curl -X POST ${deployment.deployment_endpoint ?? '<deployment-endpoint>'}/predict \\
  -H "X-API-Key: <your-api-key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "data": [
      { ${exampleFeatures.length
        ? exampleFeatures
            .map((f) =>
              f.type === 'number'
                ? `"${f.name}": 0`
                : `"${f.name}": ${JSON.stringify(f.options?.[0] ?? 'value')}`
            )
            .join(', ')
        : '"feature1": 0, "feature2": "value"'} }
    ]
  }'`}
              </pre>
              <p className="text-xs text-gray-500 mt-2">
                The production prediction API authenticates with an{' '}
                <code className="font-mono">X-API-Key</code> header. Generate a
                key from your account settings before calling the endpoint.
              </p>
            </div>

            {deployment.deployment_endpoint && state.modelId && (
              <EndpointTester
                modelId={state.modelId}
                endpoint={deployment.deployment_endpoint}
              />
            )}

            {state.modelId && (
              <SdkPanel key={state.modelId} modelId={state.modelId} />
            )}

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

        {/* Final stage — terminal CTA via the shared navigation component. */}
        <div className="mt-8">
          <StageNavigation
            currentStage={WorkflowStage.DEPLOYMENT}
            hideBack
            onFinish={() => router.push('/')}
            finishLabel="Complete Workflow"
          />
        </div>
      </div>
    </div>
  );
}