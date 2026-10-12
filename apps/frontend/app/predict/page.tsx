'use client';

import React, { useState } from 'react';
import { WorkflowStage } from '@/lib/types/workflow';
import { useStageGuard } from '@/lib/hooks/useStageGuard';
import { StageNavigation } from '@/components/workflow/StageNavigation';
import { Target } from 'lucide-react';
import { useSession } from 'next-auth/react';
import { BatchPredictionPanel } from '@/components/predict/BatchPredictionPanel';
import { ErrorBanner, ModeToggle, type PredictionMode } from '@/components/predict/PredictChrome';
import { SinglePredictionPanel } from '@/components/predict/SinglePredictionPanel';
import {
  usePredictionContext,
  usePredictionForm,
  useSinglePrediction,
  useTrainedModelGuard,
} from '@/components/predict/predictionForm';
import { useBatchPrediction } from '@/components/predict/useBatchPrediction';

export default function PredictPage() {
  const { data: session } = useSession();
  const { ready } = useStageGuard(WorkflowStage.PREDICTION);

  const [loading, setLoading] = useState(false);
  const [predictionMode, setPredictionMode] = useState<PredictionMode>('single');
  // Track which fields the user has interacted with so validation errors only
  // surface once "touched" — no red "Required" on a pristine form (issue #282).
  // (The submit button stays disabled until the form is valid, so blur is the
  // trigger that reveals what still needs filling.)
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [actionError, setActionError] = useState<string | null>(null);

  const ctx = usePredictionContext(setLoading, setActionError);
  const form = usePredictionForm(ctx.modelId, ready);
  const single = useSinglePrediction(ctx, form);
  const batch = useBatchPrediction(ctx);
  useTrainedModelGuard(ready);

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Please log in to access this page.</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-card rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
          <Target className="w-6 h-6 text-red-500" />
          Make Predictions
        </h1>

        <ErrorBanner actionError={actionError} featuresError={form.featuresError} />
        <ModeToggle mode={predictionMode} setMode={setPredictionMode} />

        {predictionMode === 'single' && (
          <SinglePredictionPanel
            features={form.features}
            values={form.values}
            setValues={form.setValues}
            touched={touched}
            setTouched={setTouched}
            validationErrors={form.validationErrors}
            prediction={single.prediction}
            loading={loading}
            formValid={form.formValid}
            onSubmit={single.predict}
          />
        )}
        {predictionMode === 'batch' && (
          <BatchPredictionPanel features={form.features} batch={batch} loading={loading} />
        )}

        {/* Shared Back / Continue navigation. "Continue to Deployment" enables
            once a prediction has been made (stage marked complete). */}
        <StageNavigation currentStage={WorkflowStage.PREDICTION} loading={loading} />
      </div>
    </div>
  );
}
