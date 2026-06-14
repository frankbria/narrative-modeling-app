'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { useRouter } from 'next/navigation';
import { Target, Upload, FileText, Send, CheckCircle, AlertTriangle } from 'lucide-react';
import { useSession } from 'next-auth/react';
import {
  modelService,
  type ModelFeatureDescriptor,
  type PredictResponse,
  type BatchJobResponse,
  type BatchJobProgressResponse,
} from '@/lib/services/model';

interface PredictionInput {
  [key: string]: string;
}

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled']);

export default function PredictPage() {
  const { data: session } = useSession();
  const { state, completeStage, canAccessStage, isHydrated } = useWorkflow();
  const router = useRouter();

  const [loading, setLoading] = useState(false);
  const [predictionMode, setPredictionMode] = useState<'single' | 'batch'>('single');
  const [features, setFeatures] = useState<ModelFeatureDescriptor[]>([]);
  const [predictionInput, setPredictionInput] = useState<PredictionInput>({});
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Batch state
  const [batchFile, setBatchFile] = useState<File | null>(null);
  const [batchJob, setBatchJob] = useState<BatchJobResponse | null>(null);
  const [batchProgress, setBatchProgress] = useState<BatchJobProgressResponse | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadModelFeatures = useCallback(async () => {
    try {
      const data = await modelService.getModelFeatures(state.modelId as string);
      setFeatures(data.features);
      const defaultInput: PredictionInput = {};
      data.features.forEach((feature) => {
        defaultInput[feature.name] =
          feature.type === 'categorical' && feature.options?.length
            ? String(feature.options[0])
            : '';
      });
      setPredictionInput(defaultInput);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load model features');
    }
  }, [state.modelId]);

  useEffect(() => {
    // Wait for the workflow to hydrate (backend → localStorage) before gating:
    // child effects run before the provider's hydrate effect, so an early
    // canAccessStage() check sees an empty completedStages set and would
    // wrongly redirect a legitimately-reached prediction stage to /upload.
    if (!isHydrated) return;
    if (!canAccessStage(WorkflowStage.PREDICTION)) {
      router.push('/upload');
      return;
    }
    if (!state.modelId) {
      router.push('/model');
      return;
    }
    loadModelFeatures();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isHydrated, canAccessStage, router, state.modelId]);

  // Clean up the progress poller on unmount.
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // ---- Validation (real-time) ----
  const fieldError = (feature: ModelFeatureDescriptor): string | null => {
    const raw = predictionInput[feature.name];
    if (raw === undefined || raw === null || String(raw).trim() === '') {
      return 'Required';
    }
    if (feature.type === 'number' && Number.isNaN(Number(raw))) {
      return 'Must be a number';
    }
    return null;
  };

  const validationErrors = features
    .map((f) => ({ name: f.name, error: fieldError(f) }))
    .filter((e) => e.error);
  const formValid = features.length > 0 && validationErrors.length === 0;

  const buildRecord = (): Record<string, string | number> => {
    const record: Record<string, string | number> = {};
    features.forEach((feature) => {
      const raw = predictionInput[feature.name];
      record[feature.name] = feature.type === 'number' ? Number(raw) : raw;
    });
    return record;
  };

  const handleSinglePrediction = async () => {
    if (!formValid) return;
    setLoading(true);
    setError(null);
    setPrediction(null);
    try {
      const result = await modelService.predict(state.modelId as string, {
        data: [buildRecord()],
        include_probabilities: true,
      });
      setPrediction(result);

      if (!state.completedStages.has(WorkflowStage.PREDICTION)) {
        completeStage(WorkflowStage.PREDICTION, {
          firstPrediction: result.predictions?.[0],
          timestamp: new Date().toISOString(),
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Prediction failed');
    } finally {
      setLoading(false);
    }
  };

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const handleBatchPrediction = async () => {
    if (!batchFile) return;
    setLoading(true);
    setError(null);
    setBatchJob(null);
    setBatchProgress(null);
    stopPolling();

    try {
      const job = await modelService.createBatchJob(state.modelId as string, batchFile, {
        include_probabilities: true,
      });
      setBatchJob(job);

      // Poll progress every 2s until the job reaches a terminal state.
      pollRef.current = setInterval(async () => {
        try {
          const progress = await modelService.getBatchJobProgress(job.job_id);
          setBatchProgress(progress);
          if (TERMINAL_STATUSES.has(progress.status)) {
            stopPolling();
            const finished = await modelService.getBatchJob(job.job_id);
            setBatchJob(finished);
            setLoading(false);
            if (
              progress.status === 'completed' &&
              !state.completedStages.has(WorkflowStage.PREDICTION)
            ) {
              completeStage(WorkflowStage.PREDICTION, {
                batchPrediction: true,
                jobId: job.job_id,
                timestamp: new Date().toISOString(),
              });
            }
          }
        } catch {
          stopPolling();
          setLoading(false);
          setError('Lost connection to the batch job. Please refresh.');
        }
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start batch prediction');
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!batchJob) return;
    try {
      const blob = await modelService.downloadBatchResults(batchJob.job_id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `batch_results_${batchJob.job_id}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download results');
    }
  };

  const batchComplete = batchJob?.status === 'completed';
  const batchFailed = batchJob?.status === 'failed';
  const summary = batchJob?.results ?? {};

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

        {error && (
          <div
            data-testid="prediction-error"
            className="mb-4 p-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700 flex items-center gap-2"
          >
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Mode Selection */}
        <div className="mb-6">
          <div className="grid grid-cols-2 gap-4">
            <button
              type="button"
              data-testid="single-prediction-link"
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
              type="button"
              data-testid="batch-prediction-link"
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
              {features.map((feature) => {
                const err = fieldError(feature);
                return (
                  <div key={feature.name}>
                    <label className="block text-sm font-medium mb-1" htmlFor={`field-${feature.name}`}>
                      {feature.name}
                    </label>
                    {feature.type === 'categorical' && feature.options?.length ? (
                      <select
                        id={`field-${feature.name}`}
                        name={feature.name}
                        data-feature={feature.name}
                        value={predictionInput[feature.name] ?? ''}
                        onChange={(e) =>
                          setPredictionInput((prev) => ({
                            ...prev,
                            [feature.name]: e.target.value,
                          }))
                        }
                        className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      >
                        {feature.options.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        id={`field-${feature.name}`}
                        name={feature.name}
                        data-feature={feature.name}
                        type={feature.type === 'number' ? 'number' : 'text'}
                        value={predictionInput[feature.name] ?? ''}
                        onChange={(e) =>
                          setPredictionInput((prev) => ({
                            ...prev,
                            [feature.name]: e.target.value,
                          }))
                        }
                        className={`w-full p-2 border rounded-lg focus:ring-2 focus:ring-blue-500 ${
                          err ? 'border-red-400' : 'border-gray-300'
                        }`}
                      />
                    )}
                    {err && (
                      <p className="mt-1 text-xs text-red-600" data-testid={`field-error-${feature.name}`}>
                        {err}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            {prediction && (
              <div
                data-testid="prediction-result"
                className="prediction-output mt-6 p-4 bg-green-50 rounded-lg border border-green-200"
              >
                <h4 className="font-semibold mb-2 flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  Prediction Result
                </h4>
                <div
                  data-testid="prediction-value"
                  className="prediction-value text-2xl font-bold text-gray-900"
                >
                  {String(prediction.predictions?.[0])}
                </div>
                {prediction.confidence?.[0] != null && (
                  <div className="mt-2">
                    <span className="text-sm text-gray-600">Confidence: </span>
                    <span data-testid="confidence-score" className="confidence font-medium">
                      {(prediction.confidence[0] * 100).toFixed(1)}%
                    </span>
                  </div>
                )}
                {prediction.probabilities?.[0] && (
                  <div className="mt-3 space-y-1">
                    <p className="text-sm text-gray-600">Class Probabilities:</p>
                    {prediction.probabilities[0].map((prob, idx) => (
                      <div key={idx} className="flex justify-between text-sm">
                        <span>{prediction.class_labels?.[idx] ?? `Class ${idx}`}:</span>
                        <span className="font-medium">{(prob * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <button
              type="button"
              data-testid="make-prediction"
              onClick={handleSinglePrediction}
              disabled={loading || !formValid}
              className={`w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 ${
                !loading && formValid
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
                data-testid="batch-file-input"
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
                <p className="mt-2 text-sm text-gray-600">Selected: {batchFile.name}</p>
              )}
            </div>

            <div className="p-4 bg-blue-50 rounded-lg">
              <h4 className="font-semibold mb-2">Expected Format</h4>
              <p className="text-sm text-gray-700">
                Your CSV should have columns matching the feature names:
              </p>
              <p className="text-xs font-mono mt-2 text-gray-600">
                {features.map((f) => f.name).join(', ')}
              </p>
            </div>

            {/* Progress */}
            {batchProgress && !batchComplete && !batchFailed && (
              <div data-testid="batch-progress" className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">
                    Processing… {batchProgress.processed_records}/{batchProgress.total_records}
                  </span>
                  <span className="font-medium">
                    {batchProgress.percentage_complete.toFixed(0)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2.5">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all"
                    style={{ width: `${Math.min(100, batchProgress.percentage_complete)}%` }}
                  />
                </div>
              </div>
            )}

            {batchFailed && (
              <div className="p-4 bg-red-50 rounded-lg border border-red-200 text-sm text-red-700">
                Batch prediction failed: {batchJob?.error_message ?? 'unknown error'}
              </div>
            )}

            {/* Summary + download */}
            {batchComplete && (
              <div
                data-testid="batch-summary"
                className="p-4 bg-green-50 rounded-lg border border-green-200 space-y-3"
              >
                <h4 className="font-semibold flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  Batch prediction complete
                </h4>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <div className="text-gray-500">Total</div>
                    <div className="font-semibold">{summary.total_predictions ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Succeeded</div>
                    <div className="font-semibold">{summary.success_count ?? 0}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Errors</div>
                    <div className="font-semibold">{summary.error_count ?? 0}</div>
                  </div>
                </div>

                {summary.prediction_distribution &&
                  Object.keys(summary.prediction_distribution).length > 0 && (
                    <div>
                      <p className="text-sm text-gray-600 mb-1">Prediction distribution:</p>
                      <div className="space-y-1">
                        {Object.entries(
                          summary.prediction_distribution as Record<string, number>
                        ).map(([cls, count]) => (
                          <div key={cls} className="flex justify-between text-sm">
                            <span>{cls}:</span>
                            <span className="font-medium">{count}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {summary.confidence_stats &&
                  Object.keys(summary.confidence_stats).length > 0 && (
                    <p className="text-xs text-gray-600">
                      Mean confidence:{' '}
                      {(
                        (summary.confidence_stats as Record<string, number>).mean * 100
                      ).toFixed(1)}
                      %
                    </p>
                  )}

                <button
                  type="button"
                  data-testid="download-predictions"
                  onClick={handleDownload}
                  className="w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 bg-green-600 text-white hover:bg-green-700"
                >
                  <FileText className="w-5 h-5" />
                  Download Results CSV
                </button>
              </div>
            )}

            <button
              type="button"
              data-testid="start-batch-prediction"
              onClick={handleBatchPrediction}
              disabled={!batchFile || loading}
              className={`w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 ${
                batchFile && !loading
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              <Send className="w-5 h-5" />
              {loading ? 'Processing…' : 'Start Batch Prediction'}
            </button>
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex justify-between">
          <button
            type="button"
            onClick={() => router.push('/evaluate')}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Back
          </button>
          {state.completedStages.has(WorkflowStage.PREDICTION) && (
            <button
              type="button"
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
