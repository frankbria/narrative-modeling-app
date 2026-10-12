import { useEffect, useRef, useState } from 'react';
import {
  modelService,
  type BatchJobProgressResponse,
  type BatchJobResponse,
} from '@/lib/services/model';
import { errorMessage, type PredictionContext } from './predictionForm';

/** A batch prediction job: start it, poll it to a terminal state, download its results. */

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled']);
const BATCH_POLL_INTERVAL_MS = 2000;

function saveBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export function useBatchPrediction(ctx: PredictionContext) {
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<BatchJobResponse | null>(null);
  const [progress, setProgress] = useState<BatchJobProgressResponse | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  // Clean up the progress poller on unmount. The flag is re-armed on every
  // mount: StrictMode (and any remount) runs cleanup then the effect again, and
  // a flag that only ever goes false left the poller returning early forever —
  // "Processing…" never cleared even after the job reported completed.
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const finish = async (jobId: string, status: string) => {
    stopPolling();
    const finished = await modelService.getBatchJob(jobId);
    if (!isMountedRef.current) return;
    setJob(finished);
    ctx.setLoading(false);
    if (status === 'completed') ctx.completePrediction({ batchPrediction: true, jobId });
  };

  const poll = async (jobId: string) => {
    try {
      const latest = await modelService.getBatchJobProgress(jobId);
      if (!isMountedRef.current) return;
      setProgress(latest);
      if (TERMINAL_STATUSES.has(latest.status)) await finish(jobId, latest.status);
    } catch {
      stopPolling();
      if (!isMountedRef.current) return;
      ctx.setLoading(false);
      ctx.setActionError('Lost connection to the batch job. Please refresh.');
    }
  };

  const start = async () => {
    if (!file) return;
    ctx.setLoading(true);
    ctx.setActionError(null);
    setJob(null);
    setProgress(null);
    stopPolling();
    try {
      const created = await modelService.createBatchJob(ctx.modelId as string, file, {
        include_probabilities: true,
      });
      setJob(created);
      // Poll progress every 2s until the job reaches a terminal state.
      pollRef.current = setInterval(() => poll(created.job_id), BATCH_POLL_INTERVAL_MS);
    } catch (err) {
      ctx.setActionError(errorMessage(err, 'Failed to start batch prediction'));
      ctx.setLoading(false);
    }
  };

  const download = async () => {
    if (!job) return;
    try {
      const blob = await modelService.downloadBatchResults(job.job_id);
      saveBlob(blob, `batch_results_${job.job_id}.csv`);
    } catch (err) {
      ctx.setActionError(errorMessage(err, 'Failed to download results'));
    }
  };

  return { file, setFile, job, progress, start, download };
}

export type BatchPrediction = ReturnType<typeof useBatchPrediction>;
