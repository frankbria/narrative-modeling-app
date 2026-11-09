import React from 'react';
import { HugeiconsIcon } from '@hugeicons/react';
import { Alert02Icon, CheckmarkCircle01Icon, FileEditIcon, SentIcon, Upload04Icon } from '@hugeicons/core-free-icons';
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
      <HugeiconsIcon icon={Upload04Icon} className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
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
        className="cursor-pointer text-primary hover:text-primary/80 font-medium"
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
    <div className="p-4 bg-primary/10 rounded-lg">
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
      <div className="w-full bg-muted rounded-full h-2.5">
        <div className="bg-primary h-2.5 rounded-full transition-all" style={{ width }} />
      </div>
    </div>
  );
}

function BatchFailure(props: { message?: string | null }) {
  const message = props.message ?? 'unknown error';
  return (
    <div className="p-4 bg-destructive/10 rounded-lg border border-destructive/30 text-sm text-destructive">
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
      className="flex items-center gap-2 text-xs text-warning"
    >
      <HugeiconsIcon icon={Alert02Icon} className="w-4 h-4 shrink-0" />
      {count} {count === 1 ? props.one : props.many}
    </p>
  );
}

function BatchSummary(props: { summary: Summary; onDownload: VoidFunction }) {
  const summary = props.summary ?? {};
  return (
    <div
      data-testid="batch-summary"
      className="p-4 bg-success/10 rounded-lg border border-success/30 space-y-3"
    >
      <h4 className="font-semibold flex items-center gap-2">
        <HugeiconsIcon icon={CheckmarkCircle01Icon} className="w-5 h-5 text-success" />
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
        className="w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
      >
        <HugeiconsIcon icon={FileEditIcon} className="w-5 h-5" />
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
    ? 'bg-primary text-primary-foreground hover:bg-primary/90'
    : 'bg-muted text-muted-foreground cursor-not-allowed';
  return (
    <button
      type="button"
      data-testid="start-batch-prediction"
      onClick={onStart}
      disabled={!ready}
      className={`w-full py-2 rounded-lg font-medium flex items-center justify-center gap-2 ${colour}`}
    >
      <HugeiconsIcon icon={SentIcon} className="w-5 h-5" />
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
