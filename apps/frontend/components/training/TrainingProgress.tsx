'use client';

import { TrainingScoreTable } from './TrainingScoreTable';
import { useEffect, useRef, useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { HugeiconsIcon } from '@hugeicons/react';
import { Alert02Icon, CancelCircleIcon, CheckmarkCircle01Icon, Loading03Icon, RotateLeft01Icon } from '@hugeicons/core-free-icons';
import { modelService, TrainingStatus } from '@/lib/services/model';

/** Show the "Connection lost" warning after this many consecutive poll failures. */
const CONNECTION_LOST_THRESHOLD = 3;
/** Upper bound for the exponential poll-failure backoff, in milliseconds. */
const MAX_BACKOFF_MS = 30000;

interface TrainingProgressProps {
  modelId: string;
  /** Status poll interval in ms; also the base delay for failure backoff. */
  pollInterval?: number;
  onComplete?: (status: TrainingStatus) => void;
  onError?: (status: TrainingStatus) => void;
  onCancelled?: (status: TrainingStatus) => void;
  className?: string;
  /** Slimmer card without the comparison table, for dashboard cards. */
  compact?: boolean;
}

/**
 * Format a duration in seconds as a compact human-readable string,
 * e.g. 134 -> "2m 14s", 45 -> "45s", 3700 -> "1h 1m".
 */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes}m ${total % 60}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

/** Build the "2m 14s elapsed · ~1m 30s remaining" timing line, if data exists. */
function formatTiming(status: TrainingStatus): string | null {
  const parts: string[] = [];
  if (status.elapsed_seconds != null) {
    parts.push(`${formatDuration(status.elapsed_seconds)} elapsed`);
  }
  if (status.estimated_remaining_seconds != null) {
    parts.push(`~${formatDuration(status.estimated_remaining_seconds)} remaining`);
  }
  return parts.length > 0 ? parts.join(' · ') : null;
}

/** Look up the best model's CV score in the comparison results. */
function bestScore(status: TrainingStatus): number | null {
  const entry = status.model_comparison.find(
    (row) => row.algorithm === status.best_algorithm
  );
  return entry?.cv_score ?? null;
}

/**
 * Live training progress panel for an AutoML job.
 *
 * Owns the status polling loop: polls `GET /ml/{model_id}/status` every
 * `pollInterval` ms, stops on terminal states (completed / failed / cancelled)
 * and fires the matching callback. Consecutive poll failures back off
 * exponentially (base `pollInterval`, doubling, capped at 30s); after three
 * failures a "Connection lost" warning with a manual Retry button is shown.
 */
export function TrainingProgress({
  modelId,
  pollInterval = 2000,
  onComplete,
  onError,
  onCancelled,
  className = '',
  compact = false,
}: TrainingProgressProps) {
  const [status, setStatus] = useState<TrainingStatus | null>(null);
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);
  // Bumped by the Retry button to restart the polling effect from scratch.
  const [retryNonce, setRetryNonce] = useState(0);

  // Keep callbacks in refs so parent re-renders with new function identities
  // don't restart the polling loop. The assignment happens in an effect, not
  // during render — writing a ref while rendering is not safe under concurrent
  // rendering (react-hooks/refs). Every read is inside the async poll loop,
  // which only runs after commit, so it always sees the latest values.
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);
  const onCancelledRef = useRef(onCancelled);
  useEffect(() => {
    onCompleteRef.current = onComplete;
    onErrorRef.current = onError;
    onCancelledRef.current = onCancelled;
  });

  useEffect(() => {
    let isMounted = true;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let failures = 0;

    const poll = async () => {
      try {
        const next = await modelService.getTrainingStatus(modelId);
        if (!isMounted) return;

        failures = 0;
        setConsecutiveFailures(0);
        setStatus(next);

        if (next.status === 'completed') {
          onCompleteRef.current?.(next);
          return;
        }
        if (next.status === 'failed') {
          onErrorRef.current?.(next);
          return;
        }
        if (next.status === 'cancelled') {
          onCancelledRef.current?.(next);
          return;
        }

        timeoutId = setTimeout(poll, pollInterval);
      } catch {
        if (!isMounted) return;
        failures += 1;
        setConsecutiveFailures(failures);
        // Exponential backoff: pollInterval, 2x, 4x, ... capped at 30s.
        const backoff = Math.min(pollInterval * 2 ** (failures - 1), MAX_BACKOFF_MS);
        timeoutId = setTimeout(poll, backoff);
      }
    };

    poll();

    return () => {
      isMounted = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [modelId, pollInterval, retryNonce]);

  const handleRetry = () => {
    setConsecutiveFailures(0);
    setRetryNonce((nonce) => nonce + 1);
  };

  const connectionLost = consecutiveFailures >= CONNECTION_LOST_THRESHOLD;
  const progressPercent = Math.round((status?.progress ?? 0) * 100);
  const timing = status ? formatTiming(status) : null;
  const isRunning =
    !status || status.status === 'pending' || status.status === 'running';

  return (
    <div
      className={`bg-card rounded-lg border border-border ${
        compact ? 'p-4 space-y-3' : 'p-6 space-y-4'
      } ${className}`}
    >
      {connectionLost && (
        <Alert className="border-warning/30 bg-warning/10 text-warning">
          <HugeiconsIcon icon={Alert02Icon} className="h-4 w-4 text-warning" />
          <AlertTitle>Connection lost — retrying</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-2">
            <span>Unable to reach the training status endpoint.</span>
            <Button variant="outline" size="sm" onClick={handleRetry}>
              <HugeiconsIcon icon={RotateLeft01Icon} className="w-4 h-4 mr-1" />
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {isRunning && (
        <>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <HugeiconsIcon icon={Loading03Icon} className="w-4 h-4 text-primary animate-spin shrink-0" />
              <span className="text-sm font-medium truncate">
                {status?.current_algorithm
                  ? `Training ${status.current_algorithm}`
                  : 'Training in progress'}
              </span>
            </div>
            {status?.current_stage && (
              <Badge variant="secondary">{status.current_stage}</Badge>
            )}
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                {status && status.total_algorithms > 0
                  ? `${status.completed_algorithms} of ${status.total_algorithms} algorithms trained`
                  : 'Progress'}
              </span>
              <span className="font-medium">{progressPercent}%</span>
            </div>
            <Progress value={progressPercent} className={compact ? 'h-2' : 'h-3'} />
            {timing && <p className="text-xs text-muted-foreground text-right">{timing}</p>}
          </div>
        </>
      )}

      {status?.status === 'completed' && (
        <Alert className="border-success/30 bg-success/10 text-success">
          <HugeiconsIcon icon={CheckmarkCircle01Icon} className="h-4 w-4 text-success" />
          <AlertTitle>Training complete</AlertTitle>
          <AlertDescription>
            {status.best_algorithm ? (
              <span>
                Best model: <span className="font-semibold">{status.best_algorithm}</span>
                {bestScore(status) != null && (
                  <span> (CV score {bestScore(status)!.toFixed(3)})</span>
                )}
              </span>
            ) : (
              <span>The model is ready to use.</span>
            )}
          </AlertDescription>
        </Alert>
      )}

      {status?.status === 'failed' && (
        <Alert variant="destructive">
          <HugeiconsIcon icon={CancelCircleIcon} className="h-4 w-4" />
          <AlertTitle>Training failed</AlertTitle>
          <AlertDescription>
            {status.error || 'An unknown error occurred during training.'}
          </AlertDescription>
        </Alert>
      )}

      {status?.status === 'cancelled' && (
        <Alert>
          <HugeiconsIcon icon={Alert02Icon} className="h-4 w-4" />
          <AlertTitle>Training cancelled</AlertTitle>
          <AlertDescription>
            Training was stopped before completion. You can start a new run at any time.
          </AlertDescription>
        </Alert>
      )}

      {!compact && status && status.model_comparison.length > 0 && (
        <TrainingScoreTable status={status} />
      )}
    </div>
  );
}

export default TrainingProgress;
