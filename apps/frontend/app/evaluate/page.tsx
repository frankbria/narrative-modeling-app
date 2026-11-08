'use client';

import React, { useEffect, useState } from 'react';
import { WorkflowStage } from '@/lib/types/workflow';
import { StageNavigation } from '@/components/workflow/StageNavigation';
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
  type AIExplanation,
  type ModelComparisonResponse,
  type ModelEvaluationResponse
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
import { EvaluateError, EvaluateLoading } from '@/components/evaluate/EvaluateStates';
import { MetricList } from '@/components/evaluate/MetricList';
import { VerdictPanel } from '@/components/evaluate/VerdictPanel';
import { buildVerdict, featureScores, metricRows, modelTitle, shapToShow, tabFlags, when } from '@/components/evaluate/evaluationReading';
import { evaluateView, useEvaluation, type EvaluateView, type Evaluation } from '@/components/evaluate/useEvaluation';
import { exportEvaluationCSV, exportEvaluationPDF } from '@/lib/utils/export';

const MIN_COMPARE = 2;
const MAX_COMPARE = 5;

function formatMetricLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-muted rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Target className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="text-2xl font-bold text-foreground">{value.toFixed(4)}</div>
    </div>
  );
}

function StoredMetricCards({ metrics }: { metrics: Record<string, number> }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {Object.entries(metrics).map(([key, value]) => (
        <MetricCard key={key} label={formatMetricLabel(key)} value={value} />
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
      icon: <CheckCircle className="w-4 h-4 text-success mt-0.5 shrink-0" />
    },
    {
      title: 'Concerns',
      items: explanation.concerns,
      icon: <AlertTriangle className="w-4 h-4 text-warning mt-0.5 shrink-0" />
    },
    {
      title: 'Recommendations',
      items: explanation.recommendations,
      icon: <Lightbulb className="w-4 h-4 text-primary mt-0.5 shrink-0" />
    }
  ];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Model Report Card</CardTitle>
          {explanation.generated_by === 'openai' ? (
            <Badge className="bg-primary/10 text-primary hover:bg-primary/10">
              AI-generated
            </Badge>
          ) : (
            <Badge className="bg-muted text-foreground hover:bg-muted">
              Rule-based
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-foreground">{explanation.overall_assessment}</p>
        {lists
          .filter(({ items }) => items.length > 0)
          .map(({ title, items, icon }) => (
            <div key={title}>
              <h4 className="text-sm font-semibold text-foreground mb-1">{title}</h4>
              <ul className="space-y-1">
                {items.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-sm text-foreground">
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
          <p className="text-sm text-muted-foreground">
            Choose {MIN_COMPARE}–{MAX_COMPARE} models trained on this dataset.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {listLoading ? (
            <p className="text-sm text-muted-foreground">Loading models…</p>
          ) : models.length === 0 ? (
            <p className="text-sm text-muted-foreground">No trained models found for this dataset.</p>
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
                      className="text-sm text-foreground cursor-pointer"
                    >
                      {model.name}
                      <span className="ml-2 text-xs text-muted-foreground">{model.algorithm}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
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

type ReadyEvaluation = Evaluation & { evaluation: ModelEvaluationResponse };

function Header({ evaluation }: { evaluation: ModelEvaluationResponse }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
      <div className="flex items-center gap-3">
        <LineChartIcon className="w-6 h-6 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">Model Evaluation</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm text-foreground">
              {modelTitle(evaluation)}
            </span>
            {when(evaluation.algorithm, (name) => <Badge variant="secondary">{name}</Badge>)}
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
  );
}

const PARTIAL_BANNER = (
  <div className="mb-6 p-4 bg-warning/10 rounded-lg border border-warning/30 flex items-start gap-2">
    <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
    <p className="text-sm text-warning">
      Detailed evaluation artifacts aren&apos;t available for this model (trained
      before evaluation persistence). Showing stored training metrics.
    </p>
  </div>
);

function Overview({ ev }: { ev: ReadyEvaluation }) {
  const { evaluation, shap } = ev;
  const verdict = buildVerdict(evaluation);
  const scores = featureScores(evaluation.feature_importance);
  return (
    <>
      {when(verdict, (v) => <VerdictPanel verdict={v} />)}
      {when(verdict, () => <MetricList rows={metricRows(evaluation)} />)}
      {when(!verdict, () => <StoredMetricCards metrics={evaluation.stored_metrics} />)}
      {when(evaluation.ai_explanation, (e) => <ModelReportCard explanation={e} />)}
      {when(scores.length > 0, () => <FeatureImportanceChart features={scores} height={360} />)}
      {when(
        shapToShow(shap),
        (s) => (
          <ShapSummaryChart
            features={s.feature_importance}
            plainLanguage={s.plain_language}
            explainerType={s.explainer_type}
            height={360}
          />
        )
      )}
    </>
  );
}

function Curves({ evaluation }: { evaluation: ModelEvaluationResponse }) {
  return (
    <>
      {when(
        evaluation.roc_curve,
        (roc) => (
          <div data-testid="roc-curve">
            <h3 className="font-semibold text-lg mb-2">ROC Curve</h3>
            <ROCCurveChart data={roc} />
          </div>
        )
      )}
      {when(
        evaluation.pr_curve,
        (pr) => (
          <div>
            <h3 className="font-semibold text-lg mb-2">Precision-Recall Curve</h3>
            <PRCurveChart data={pr} />
          </div>
        )
      )}
    </>
  );
}

function ReadyView({ ev }: { ev: ReadyEvaluation }) {
  const { evaluation } = ev;
  const tabs = tabFlags(evaluation);
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="bg-card rounded-lg shadow-md p-6">
        <Header evaluation={evaluation} />
        {when(evaluation.partial, () => PARTIAL_BANNER)}
        <Tabs defaultValue="overview">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            {when(tabs.confusion, () => <TabsTrigger value="confusion-matrix">Confusion Matrix</TabsTrigger>)}
            {when(tabs.curves, () => <TabsTrigger value="curves">Curves</TabsTrigger>)}
            <TabsTrigger value="compare">Compare</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6 mt-4">
            <Overview ev={ev} />
          </TabsContent>

          {when(
            tabs.confusion,
            (matrix) => (
              <TabsContent value="confusion-matrix" className="mt-4">
                <ConfusionMatrixChart data={matrix} />
              </TabsContent>
            )
          )}

          {when(
            tabs.curves,
            () => (
              <TabsContent value="curves" className="space-y-8 mt-4">
                <Curves evaluation={evaluation} />
              </TabsContent>
            )
          )}

          <TabsContent value="compare" className="mt-4">
            <CompareTab datasetId={ev.datasetId} />
          </TabsContent>
        </Tabs>

        {/* Shared Back / Continue navigation. Evaluation is informational, so
            Continue is always available; onContinue records completion before
            advancing to the prediction stage. */}
        <StageNavigation
          currentStage={WorkflowStage.MODEL_EVALUATION}
          ready
          continueLabel="Continue to Prediction"
          onContinue={ev.proceed}
        />
      </div>
    </div>
  );
}

interface ViewProps {
  ev: Evaluation;
  onBack: () => void;
}

const VIEWS: Record<EvaluateView, (props: ViewProps) => React.ReactElement> = {
  loading: () => <EvaluateLoading />,
  error: ({ ev, onBack }) => (
    <EvaluateError message={ev.error as string} onRetry={ev.reload} onBack={onBack} />
  ),
  empty: ({ onBack }) => (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <h2 className="text-2xl font-semibold mb-2">No Evaluation Data</h2>
        <p className="text-muted-foreground mb-4">Model evaluation data is not available.</p>
        <Button onClick={onBack}>Go to Model Training</Button>
      </div>
    </div>
  ),
  ready: ({ ev }) => <ReadyView ev={ev as ReadyEvaluation} />
};

export default function EvaluatePage() {
  const router = useRouter();
  const ev = useEvaluation();
  const View = VIEWS[evaluateView(ev)];
  return <View ev={ev} onBack={() => router.push('/model')} />;
}
