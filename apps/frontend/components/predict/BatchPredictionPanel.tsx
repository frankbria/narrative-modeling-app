import React from 'react';
import { AlertTriangle, CheckCircle, FileText, Send, Upload } from 'lucide-react';
import type {
  BatchJobProgressResponse,
  BatchJobResponse,
  ModelFeatureDescriptor,
} from '@/lib/services/model';
import type { BatchPrediction } from './useBatchPrediction';

/** Batch mode: pick a CSV, run the job, read its summary, download the results. */

type Summary = BatchJobResponse['results'];

function FilePicker(props: { file: File | null; setFile: BatchPrediction['setFile'] }) {
  const { file, setFile } = props;
  const pick = (e: React.ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] || null);
  return (
    <div className="border-2 border-dashed border-border rounded-lg p-8 text-center">
      <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
      <input
        type="file"
        accept=".csv"
        data-testid="batch-file-input"
        onChange={pick}
        className="hidden"
        id="batch-file-input"
      />
      <label
        htmlFor="batch-file-input"
        className="cursor-pointer text-blue-600 hover:text-blue-700 font-medium"
      >
        Click to upload CSV file
      </label>
      {file && <p className="mt-2 text-sm text-muted-foreground">Selected: {file.name}</p>}
    </div>
  );
}

function ExpectedFormat(props: { features: ModelFeatureDescriptor[] }) {
  const names = props.features.map((f) => f.name).join(', ');
  return (
    <div className="p-4 bg-blue-50 dark:bg-blue-950/40 rounded-lg">
      <h4 className="font-semibold mb-2">Expected Format</h4>
      <p className="text-sm text-foreground">
        Your CSV should have columns matching the feature names:
      </p>
      <p className="text-xs font-mono mt-2 text-muted-foreground">{names}</p>
    </div>
  );
}

function BatchProgress(props: { progress: BatchJobProgressResponse | null }) {
  const { progress } = props;
  if (!progress) return null;
  const width = `${Math.min(100, progress.percentage_complete)}%`;
  return (
    <div data-testid="batch-progress" className="p-4 bg-muted rounded-lg border border-border">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-muted-foreground">
          Processing… {progress.processed_records}/{progress.total_records}
        </span>
        <span className="font-medium">{progress.percentage_complete.toFixed(0)}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div className="bg-blue-600 h-2.5 rounded-full transition-all" style={{ width }} />
      </div>
    </div>
  );
}

function BatchFailure(props: { message?: string | null }) {
  const message = props.message ?? 'unknown error';
  return (
    <div className="p-4 bg-red-50 dark:bg-red-950/40 rounded-lg border border-red-200 dark:border-red-900 text-sm text-red-700 dark:text-red-300">
      Batch prediction failed: {message}
    </div>
  );
}

function SummaryCount(props: { label: string; value?: number }) {
  const value = props.value ?? 0;
  return (
    <div>
      <div className="text-muted-foreground">{props.label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}

function Distribution(props: { distribution?: Record<string, number> }) {
  const entries = Object.entries(props.distribution ?? {});
  if (entries.length === 0) return null;
  return (
    <div>
      <p className="text-sm text-muted-foreground mb-1">Prediction distribution:</p>
      <div className="space-y-1">
        {entries.map(([cls, count]) => (
          <div key={cls} className="flex justify-between text-sm">
            <span>{cls}:</span>
            <span className="font-medium">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MeanConfidence(props: { stats?: Record<string, number> }) {
  const stats = props.stats ?? {};
  if (Object.keys(stats).length === 0) return null;
  return (
    <p className="text-xs text-muted-foreground">
      Mean confidence: {(stats.mean * 100).toFixed(1)}%
    </p>
  );
}

/** A count of rows the downloaded CSV marks, shown only when there are any. */
function FlaggedRows(props: { testId: string; count: unknown; one: string; many: string }) {
  const { count } = props;
  if (typeof count !== 'number' || count <= 0) return null;
  return (
    <p
      data-testid={props.testId}
      className="flex items-center gap-2 text-xs text-amber-800 dark:text-amber-200"
    >
      <AlertTriangle className="w-4 h-4 shrink-0" />
      {count} {count === 1 ? props.one : props.many}
    </p>
  );
}

function BatchSummary(props: { summary: Summary; onDownload: VoidFunction }) {
  const summary = props.summary ?? {};
  return (
    <div
      data-testid="batch-summary"
      className="p-4 bg-green-50 dark:bg-green-950/40 rounded-lg border border-green-200 dark:border-green-900 space-y-3"
    >
      <h4 className="font-semibold flex items-center gap-2">
        <CheckCircle className="w-5 h-5 text-green-600" />
        Batch prediction complete
      </h4>
      <div className="grid grid-cols-3 gap-3 text-sm">
        <SummaryCount label="Total" value={summary.total_predictions} />
        <SummaryCount label="Succeeded" value={summary.success_count} />
        <SummaryCount label="Errors" value={summary.error_count} />
      </div>
      <Distribution distribution={summary.prediction_distribution} />
      <MeanConfidence stats={summary.confidence_stats} />
      {/* Low-confidence count across the batch (#83). */}
      <FlaggedRows
        testId="batch-low-confidence"
        count={summary.low_confidence_count}
        one="low-confidence prediction — review the flagged rows in the downloaded CSV."
        many="low-confidence predictions — review the flagged rows in the downloaded CSV."
      />
      {/* Predictions resting on an input the model had not seen (#838). */}
      <FlaggedRows
        testId="batch-input-warnings"
        count={summary.input_warning_count}
        one="row has an input the model had not seen in training — see the input_warnings column in the downloaded CSV."
        many="rows have an input the model had not seen in training — see the input_warnings column in the downloaded CSV."
      />
      <button
        type="button"
        data-testid="download-predictions"
        onClick={props.onDownload}
        className="w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 bg-green-600 text-white hover:bg-green-700"
      >
        <FileText className="w-5 h-5" />
        Download Results CSV
      </button>
    </div>
  );
}

/** Progress while the job runs, then its failure or its summary. */
function BatchOutcome(props: { batch: BatchPrediction }) {
  const { job, progress, download } = props.batch;
  if (!job) return <BatchProgress progress={progress} />;
  if (job.status === 'completed') return <BatchSummary summary={job.results} onDownload={download} />;
  if (job.status === 'failed') return <BatchFailure message={job.error_message} />;
  return <BatchProgress progress={progress} />;
}

function StartButton(props: { ready: boolean; loading: boolean; onStart: VoidFunction }) {
  const { ready, loading, onStart } = props;
  const colour = ready
    ? 'bg-blue-600 text-white hover:bg-blue-700'
    : 'bg-gray-300 text-muted-foreground cursor-not-allowed';
  return (
    <button
      type="button"
      data-testid="start-batch-prediction"
      onClick={onStart}
      disabled={!ready}
      className={`w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 ${colour}`}
    >
      <Send className="w-5 h-5" />
      {loading ? 'Processing…' : 'Start Batch Prediction'}
    </button>
  );
}

export interface BatchPredictionPanelProps {
  features: ModelFeatureDescriptor[];
  batch: BatchPrediction;
  loading: boolean;
}

export function BatchPredictionPanel(props: BatchPredictionPanelProps) {
  const { batch, loading } = props;
  const ready = Boolean(batch.file) && !loading;
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-lg">Upload Batch File</h3>
      <FilePicker file={batch.file} setFile={batch.setFile} />
      <ExpectedFormat features={props.features} />
      <BatchOutcome batch={batch} />
      <StartButton ready={ready} loading={loading} onStart={batch.start} />
    </div>
  );
}
