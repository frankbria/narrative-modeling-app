'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useRouter } from 'next/navigation';
import {
  LineChart as LineChartIcon,
  Download,
  CheckCircle,
  AlertTriangle,
  Lightbulb,
  Target
} from 'lucide-react';
import { modelService, type ModelInfo } from '@/lib/services/model';
import {
  isClassificationMetrics,
  type AIExplanation,
  type ModelComparisonResponse,
  type ModelEvaluationResponse,
  type ShapSummaryResponse
} from '@/lib/types/evaluation';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ConfusionMatrixChart } from '@/components/ConfusionMatrixChart';
import { ROCCurveChart } from '@/components/ROCCurveChart';
import { PRCurveChart } from '@/components/PRCurveChart';
import { ModelComparisonTable } from '@/components/ModelComparisonTable';
import { FeatureImportanceChart } from '@/components/FeatureImportanceChart';
import { ShapSummaryChart } from '@/components/ShapSummaryChart';
import { exportEvaluationCSV, exportEvaluationPDF } from '@/lib/utils/export';

const MIN_COMPARE = 2;
const MAX_COMPARE = 5;

function formatMetricLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-600">{label}</span>
        <Target className="w-4 h-4 text-gray-400" />
      </div>
      <div className="text-2xl font-bold text-gray-900">{value.toFixed(4)}</div>
    </div>
  );
}

function MetricCards({ evaluation }: { evaluation: ModelEvaluationResponse }) {
  const { metrics } = evaluation;
  if (!metrics) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Object.entries(evaluation.stored_metrics).map(([key, value]) => (
          <MetricCard key={key} label={formatMetricLabel(key)} value={value} />
        ))}
      </div>
    );
  }

  const cards: Array<[string, number]> = isClassificationMetrics(metrics)
    ? [
        ['Accuracy', metrics.accuracy],
        ['Precision (weighted)', metrics.precision_weighted],
        ['Recall (weighted)', metrics.recall_weighted],
        ['F1 (weighted)', metrics.f1_weighted],
        ...(metrics.roc_auc !== null ? [['ROC AUC', metrics.roc_auc] as [string, number]] : []),
        ...(metrics.log_loss !== null ? [['Log Loss', metrics.log_loss] as [string, number]] : [])
      ]
    : [
        ['MAE', metrics.mae],
        ['MSE', metrics.mse],
        ['RMSE', metrics.rmse],
        ['R²', metrics.r2],
        ...(metrics.mape !== null ? [['MAPE', metrics.mape] as [string, number]] : [])
      ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {cards.map(([label, value]) => (
        <MetricCard key={label} label={label} value={value} />
      ))}
    </div>
  );
}

function ModelReportCard({ explanation }: { explanation: AIExplanation }) {
  const lists: Array<{
    title: string;
    items: string[];
    icon: React.ReactNode;
  }> = [
    {
      title: 'Strengths',
      items: explanation.strengths,
      icon: <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
    },
    {
      title: 'Concerns',
      items: explanation.concerns,
      icon: <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
    },
    {
      title: 'Recommendations',
      items: explanation.recommendations,
      icon: <Lightbulb className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
    }
  ];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Model Report Card</CardTitle>
          {explanation.generated_by === 'openai' ? (
            <Badge className="bg-purple-100 text-purple-800 hover:bg-purple-100">
              AI-generated
            </Badge>
          ) : (
            <Badge className="bg-gray-100 text-gray-700 hover:bg-gray-100">
              Rule-based
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-gray-700">{explanation.overall_assessment}</p>
        {lists
          .filter(({ items }) => items.length > 0)
          .map(({ title, items, icon }) => (
            <div key={title}>
              <h4 className="text-sm font-semibold text-gray-900 mb-1">{title}</h4>
              <ul className="space-y-1">
                {items.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-sm text-gray-700">
                    {icon}
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
      </CardContent>
    </Card>
  );
}

function CompareTab({ datasetId }: { datasetId?: string }) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<ModelComparisonResponse | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadModels = async () => {
      setListLoading(true);
      setError(null);
      try {
        const result = await modelService.listModels(datasetId);
        if (!cancelled) setModels(result);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load models');
        }
      } finally {
        if (!cancelled) setListLoading(false);
      }
    };
    loadModels();
    return () => {
      cancelled = true;
    };
  }, [datasetId]);

  const toggleModel = (modelId: string, checked: boolean) => {
    setSelectedIds((prev) =>
      checked ? [...prev, modelId] : prev.filter((id) => id !== modelId)
    );
  };

  const handleCompare = async () => {
    setComparing(true);
    setError(null);
    try {
      const result = await modelService.compareModels(selectedIds);
      setComparison(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compare models');
    } finally {
      setComparing(false);
    }
  };

  const canCompare =
    selectedIds.length >= MIN_COMPARE && selectedIds.length <= MAX_COMPARE && !comparing;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Select models to compare</CardTitle>
          <p className="text-sm text-gray-600">
            Choose {MIN_COMPARE}–{MAX_COMPARE} models trained on this dataset.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {listLoading ? (
            <p className="text-sm text-gray-500">Loading models…</p>
          ) : models.length === 0 ? (
            <p className="text-sm text-gray-500">No trained models found for this dataset.</p>
          ) : (
            <ul className="space-y-2">
              {models.map((model) => {
                const checked = selectedIds.includes(model.model_id);
                const atLimit = selectedIds.length >= MAX_COMPARE && !checked;
                return (
                  <li key={model.model_id} className="flex items-center gap-3">
                    <Checkbox
                      id={`compare-${model.model_id}`}
                      checked={checked}
                      disabled={atLimit}
                      onCheckedChange={(value) =>
                        toggleModel(model.model_id, value === true)
                      }
                      aria-label={model.name}
                    />
                    <label
                      htmlFor={`compare-${model.model_id}`}
                      className="text-sm text-gray-900 cursor-pointer"
                    >
                      {model.name}
                      <span className="ml-2 text-xs text-gray-500">{model.algorithm}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          <Button onClick={handleCompare} disabled={!canCompare}>
            {comparing ? 'Comparing…' : 'Compare'}
          </Button>
        </CardContent>
      </Card>

      {comparison && (
        <Card>
          <CardHeader>
            <CardTitle>Comparison results</CardTitle>
          </CardHeader>
          <CardContent>
            <ModelComparisonTable models={comparison.models} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function EvaluatePage() {
  const { state, completeStage, canAccessStage } = useWorkflow();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<ModelEvaluationResponse | null>(null);
  const [shap, setShap] = useState<ShapSummaryResponse | null>(null);

  const loadEvaluation = useCallback(async (modelId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await modelService.getEvaluation(modelId);
      setEvaluation(data);
      // SHAP summary is best-effort enrichment (issue #80): a failure (or a
      // model with no SHAP support) must never block the evaluation view.
      try {
        setShap(await modelService.getShapSummary(modelId));
      } catch {
        setShap(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!canAccessStage(WorkflowStage.MODEL_EVALUATION)) {
      router.push('/upload');
      return;
    }

    if (!state.modelId) {
      router.push('/model');
      return;
    }

    loadEvaluation(state.modelId);
  }, [canAccessStage, router, state.modelId, loadEvaluation]);

  const handleProceedToPrediction = () => {
    completeStage(WorkflowStage.MODEL_EVALUATION, {
      evaluationComplete: true,
      metrics: evaluation?.metrics ?? evaluation?.stored_metrics,
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

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <h2 className="text-2xl font-semibold mb-2">Failed to Load Evaluation</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <Button onClick={() => router.push('/model')}>Go to Model Training</Button>
        </div>
      </div>
    );
  }

  if (!evaluation) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h2 className="text-2xl font-semibold mb-2">No Evaluation Data</h2>
          <p className="text-gray-600 mb-4">Model evaluation data is not available.</p>
          <Button onClick={() => router.push('/model')}>Go to Model Training</Button>
        </div>
      </div>
    );
  }

  const metrics = evaluation.metrics;
  const isClassification = metrics !== null && isClassificationMetrics(metrics);
  const showConfusionTab = isClassification && evaluation.confusion_matrix !== null;
  const showCurvesTab =
    isClassification && (evaluation.roc_curve !== null || evaluation.pr_curve !== null);

  const featureScores = evaluation.feature_importance
    ? (() => {
        const entries = Object.entries(evaluation.feature_importance).sort(
          ([, a], [, b]) => b - a
        );
        const max = entries.length > 0 ? entries[0][1] : 0;
        return entries.map(([name, value], index) => ({
          feature_name: name,
          score: max > 0 ? value / max : 0,
          rank: index + 1,
          selected: true
        }));
      })()
    : null;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <LineChartIcon className="w-6 h-6 text-purple-500" />
            <div>
              <h1 className="text-2xl font-bold">Model Evaluation</h1>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-sm text-gray-700">
                  {evaluation.model_name ?? evaluation.model_id}
                </span>
                {evaluation.algorithm && (
                  <Badge variant="secondary">{evaluation.algorithm}</Badge>
                )}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => exportEvaluationCSV(evaluation)}
              aria-label="Export CSV"
            >
              <Download className="w-4 h-4 mr-2" />
              CSV
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => exportEvaluationPDF(evaluation)}
              aria-label="Export PDF"
            >
              <Download className="w-4 h-4 mr-2" />
              PDF
            </Button>
          </div>
        </div>

        {/* Partial-evaluation banner */}
        {evaluation.partial && (
          <div className="mb-6 p-4 bg-amber-50 rounded-lg border border-amber-200 flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800">
              Detailed evaluation artifacts aren&apos;t available for this model (trained
              before evaluation persistence). Showing stored training metrics.
            </p>
          </div>
        )}

        <Tabs defaultValue="overview">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            {showConfusionTab && (
              <TabsTrigger value="confusion-matrix">Confusion Matrix</TabsTrigger>
            )}
            {showCurvesTab && <TabsTrigger value="curves">Curves</TabsTrigger>}
            <TabsTrigger value="compare">Compare</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6 mt-4">
            <MetricCards evaluation={evaluation} />
            {evaluation.ai_explanation && (
              <ModelReportCard explanation={evaluation.ai_explanation} />
            )}
            {featureScores && featureScores.length > 0 && (
              <FeatureImportanceChart features={featureScores} height={360} />
            )}
            {shap && !shap.partial && shap.feature_importance.length > 0 && (
              <ShapSummaryChart
                features={shap.feature_importance}
                plainLanguage={shap.plain_language}
                explainerType={shap.explainer_type}
                height={360}
              />
            )}
          </TabsContent>

          {showConfusionTab && evaluation.confusion_matrix && (
            <TabsContent value="confusion-matrix" className="mt-4">
              <ConfusionMatrixChart data={evaluation.confusion_matrix} />
            </TabsContent>
          )}

          {showCurvesTab && (
            <TabsContent value="curves" className="space-y-8 mt-4">
              {evaluation.roc_curve && (
                <div>
                  <h3 className="font-semibold text-lg mb-2">ROC Curve</h3>
                  <ROCCurveChart data={evaluation.roc_curve} />
                </div>
              )}
              {evaluation.pr_curve && (
                <div>
                  <h3 className="font-semibold text-lg mb-2">Precision-Recall Curve</h3>
                  <PRCurveChart data={evaluation.pr_curve} />
                </div>
              )}
            </TabsContent>
          )}

          <TabsContent value="compare" className="mt-4">
            <CompareTab datasetId={state.datasetId} />
          </TabsContent>
        </Tabs>

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
