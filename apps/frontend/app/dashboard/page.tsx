'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WORKFLOW_STAGES, WorkflowStage } from '@/lib/types/workflow';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import {
  Upload,
  BarChart3,
  Wrench,
  Sparkles,
  Brain,
  LineChart,
  Target,
  Rocket,
  ArrowRight,
  Database,
  CheckCircle,
  AlertCircle,
  Lock
} from 'lucide-react';

// Icon mapping for workflow stages
const STAGE_ICONS: Record<string, React.ElementType> = {
  Upload,
  BarChart3,
  Wrench,
  Sparkles,
  Brain,
  LineChart,
  Target,
  Rocket
};

interface DatasetItem {
  dataset_id: string;
  filename: string;
  num_rows: number;
  num_columns: number;
  created_at: string;
}

interface ModelItem {
  model_id: string;
  name: string;
  algorithm: string;
  status: string;
  test_score: number | null;
  created_at: string;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  return date.toLocaleDateString();
}

function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'training':
      return 'bg-yellow-100 text-yellow-800';
    case 'trained':
      return 'bg-green-100 text-green-800';
    case 'deployed':
      return 'bg-blue-100 text-blue-800';
    case 'failed':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const { state, canAccessStage } = useWorkflow();

  const [recentDatasets, setRecentDatasets] = useState<DatasetItem[]>([]);
  const [recentModels, setRecentModels] = useState<ModelItem[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [datasetsError, setDatasetsError] = useState<string | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);

  // Calculate workflow progress
  const progressPercentage = useMemo(() => {
    return (state.completedStages.size / WORKFLOW_STAGES.length) * 100;
  }, [state.completedStages]);

  const fetchRecentDatasets = async () => {
    try {
      setIsLoadingDatasets(true);
      setDatasetsError(null);
      const token = await getAuthToken();

      const response = await fetch(`${API_URL}/datasets?page=1&limit=5`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch datasets');
      }

      const data = await response.json();

      // Validate API response structure
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid API response format');
      }

      const datasets = data.datasets;
      if (datasets !== undefined && !Array.isArray(datasets)) {
        throw new Error('Invalid datasets format: expected array');
      }

      setRecentDatasets(datasets || []);
    } catch (error) {
      console.error('Error fetching datasets:', error);
      setDatasetsError('Unable to load datasets');
    } finally {
      setIsLoadingDatasets(false);
    }
  };

  const fetchRecentModels = async () => {
    try {
      setIsLoadingModels(true);
      setModelsError(null);
      const token = await getAuthToken();

      const response = await fetch(`${API_URL}/models?page=1&limit=5`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch models');
      }

      const data = await response.json();

      // Validate API response structure
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid API response format');
      }

      const models = data.models;
      if (models !== undefined && !Array.isArray(models)) {
        throw new Error('Invalid models format: expected array');
      }

      setRecentModels(models || []);
    } catch (error) {
      console.error('Error fetching models:', error);
      setModelsError('Unable to load models');
    } finally {
      setIsLoadingModels(false);
    }
  };

  useEffect(() => {
    fetchRecentDatasets();
    fetchRecentModels();
  }, []);

  const handleNavigateToStage = (route: string, stageId: WorkflowStage) => {
    if (canAccessStage(stageId)) {
      const datasetId = state.datasetId;
      // For stages that need dataset ID in the URL
      if (datasetId && route !== '/upload') {
        router.push(`${route}/${datasetId}`);
      } else {
        router.push(route);
      }
    }
  };

  const hasDeployedModels = recentModels.some(m => m.status.toLowerCase() === 'deployed');

  return (
    <div className="max-w-7xl mx-auto p-6" data-testid="dashboard">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-2">
          Welcome to Narrative Modeling. Track your progress through the 8-stage ML workflow.
        </p>
      </div>

      {/* Quick Actions */}
      <Card className="mb-6">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <Button
              onClick={() => router.push('/upload')}
              className="flex items-center gap-2"
            >
              <Upload size={16} />
              Upload New Dataset
              <ArrowRight size={16} />
            </Button>
            <Button
              variant="secondary"
              onClick={() => router.push('/model')}
              disabled={recentDatasets.length === 0}
              className="flex items-center gap-2"
            >
              <Brain size={16} />
              Train Model
              <ArrowRight size={16} />
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push('/deploy')}
              disabled={!hasDeployedModels}
              className="flex items-center gap-2"
            >
              <Rocket size={16} />
              View Deployments
              <ArrowRight size={16} />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Workflow Progress */}
      <Card className="mb-6" data-testid="workflow-progress">
        <CardHeader>
          <CardTitle className="text-lg">Workflow Progress</CardTitle>
          <CardDescription>
            {state.completedStages.size} of {WORKFLOW_STAGES.length} stages completed
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Progress value={progressPercentage} className="h-3 mb-4" />
          <div className="flex flex-wrap gap-2">
            {WORKFLOW_STAGES.map((stage) => {
              const isCompleted = state.completedStages.has(stage.id);
              const isCurrent = state.currentStage === stage.id;

              return (
                <div
                  key={stage.id}
                  className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                    isCompleted
                      ? 'bg-green-100 text-green-800'
                      : isCurrent
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {isCompleted && <CheckCircle size={12} />}
                  {stage.name}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Navigation Cards */}
      <div className="mb-6" data-testid="navigation-cards">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Workflow Stages</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {WORKFLOW_STAGES.map((stage) => {
            const Icon = STAGE_ICONS[stage.icon] || Database;
            const isCompleted = state.completedStages.has(stage.id);
            const isAccessible = canAccessStage(stage.id);
            const isCurrent = state.currentStage === stage.id;

            return (
              <Card
                key={stage.id}
                className={`cursor-pointer transition-all hover:shadow-md ${
                  !isAccessible ? 'opacity-60' : ''
                } ${isCurrent ? 'ring-2 ring-blue-500' : ''}`}
                onClick={() => isAccessible && handleNavigateToStage(stage.route, stage.id)}
                role="button"
                tabIndex={isAccessible ? 0 : -1}
                aria-label={`${stage.name}: ${stage.description}${!isAccessible ? ' (locked)' : ''}`}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && isAccessible) {
                    handleNavigateToStage(stage.route, stage.id);
                  }
                }}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className={`p-2 rounded-lg ${
                      isCompleted
                        ? 'bg-green-100'
                        : isCurrent
                        ? 'bg-blue-100'
                        : 'bg-gray-100'
                    }`}>
                      <Icon
                        size={20}
                        className={
                          isCompleted
                            ? 'text-green-600'
                            : isCurrent
                            ? 'text-blue-600'
                            : 'text-gray-500'
                        }
                      />
                    </div>
                    {isCompleted ? (
                      <CheckCircle size={18} className="text-green-500" />
                    ) : !isAccessible ? (
                      <Lock size={18} className="text-gray-400" />
                    ) : null}
                  </div>
                  <h3 className="font-semibold text-gray-900 text-sm mb-1">{stage.name}</h3>
                  <p className="text-xs text-gray-600">{stage.description}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Recent Activity Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Datasets */}
        <Card data-testid="recent-datasets">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Database size={20} />
              Recent Datasets
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingDatasets ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse flex items-center gap-3">
                    <div className="h-10 w-10 bg-gray-200 rounded" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-gray-200 rounded w-3/4" />
                      <div className="h-3 bg-gray-200 rounded w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : datasetsError ? (
              <div className="flex items-center gap-2 text-red-600 py-4">
                <AlertCircle size={16} />
                <span className="text-sm">{datasetsError}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={fetchRecentDatasets}
                  className="ml-2"
                >
                  Retry
                </Button>
              </div>
            ) : recentDatasets.length > 0 ? (
              <div className="space-y-3">
                {recentDatasets.map((dataset) => (
                  <div
                    key={dataset.dataset_id}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => router.push(`/explore/${dataset.dataset_id}`)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        router.push(`/explore/${dataset.dataset_id}`);
                      }
                    }}
                  >
                    <div className="p-2 bg-blue-100 rounded">
                      <Database size={16} className="text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm text-gray-900 truncate">
                        {dataset.filename}
                      </p>
                      <p className="text-xs text-gray-500">
                        {dataset.num_rows.toLocaleString()} rows, {dataset.num_columns} columns
                      </p>
                    </div>
                    <span className="text-xs text-gray-400">
                      {formatRelativeTime(dataset.created_at)}
                    </span>
                  </div>
                ))}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push('/explore')}
                  className="w-full mt-2"
                >
                  View All Datasets
                  <ArrowRight size={14} className="ml-1" />
                </Button>
              </div>
            ) : (
              <div className="text-center py-8">
                <Database size={32} className="mx-auto text-gray-300 mb-3" />
                <p className="text-gray-500 text-sm mb-4">No datasets yet</p>
                <Button
                  size="sm"
                  onClick={() => router.push('/upload')}
                >
                  <Upload size={14} className="mr-1" />
                  Upload Dataset
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Models */}
        <Card data-testid="recent-models">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Brain size={20} />
              Recent Models
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingModels ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse flex items-center gap-3">
                    <div className="h-10 w-10 bg-gray-200 rounded" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-gray-200 rounded w-3/4" />
                      <div className="h-3 bg-gray-200 rounded w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : modelsError ? (
              <div className="flex items-center gap-2 text-red-600 py-4">
                <AlertCircle size={16} />
                <span className="text-sm">{modelsError}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={fetchRecentModels}
                  className="ml-2"
                >
                  Retry
                </Button>
              </div>
            ) : recentModels.length > 0 ? (
              <div className="space-y-3">
                {recentModels.map((model) => (
                  <div
                    key={model.model_id}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => router.push(`/model/${model.model_id}`)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        router.push(`/model/${model.model_id}`);
                      }
                    }}
                  >
                    <div className="p-2 bg-purple-100 rounded">
                      <Brain size={16} className="text-purple-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm text-gray-900 truncate">
                        {model.name}
                      </p>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">{model.algorithm}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${getStatusColor(model.status)}`}>
                          {model.status}
                        </span>
                      </div>
                    </div>
                    {model.test_score !== null && (
                      <span className="text-xs font-medium text-green-600">
                        {(model.test_score * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>
                ))}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push('/model')}
                  className="w-full mt-2"
                >
                  View All Models
                  <ArrowRight size={14} className="ml-1" />
                </Button>
              </div>
            ) : (
              <div className="text-center py-8">
                <Brain size={32} className="mx-auto text-gray-300 mb-3" />
                <p className="text-gray-500 text-sm mb-4">No models trained yet</p>
                <Button
                  size="sm"
                  onClick={() => router.push('/model')}
                  disabled={recentDatasets.length === 0}
                >
                  <Sparkles size={14} className="mr-1" />
                  Train Model
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Help Section */}
      <Card className="mt-6">
        <CardContent className="py-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h3 className="font-semibold text-gray-900">Need help getting started?</h3>
              <p className="text-sm text-gray-600">
                Follow the 8-stage workflow to build and deploy your ML models.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => router.push('/upload')}
            >
              Start with Data Upload
              <ArrowRight size={14} className="ml-1" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
