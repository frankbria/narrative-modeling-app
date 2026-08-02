'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Loader2,
  X,
  RotateCcw
} from 'lucide-react';
import {
  TransformationService,
  BulkTransformationProgressResponse
} from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';

/**
 * Props for the BulkTransformationProgress component
 */
interface BulkTransformationProgressProps {
  jobId: string;
  datasetId: string;
  onComplete: (result: BulkTransformationProgressResponse) => void;
  onCancel?: () => void;
  pollInterval?: number;
  className?: string;
}

/**
 * Format seconds into human-readable time
 */
function formatTime(seconds: number | undefined): string {
  if (seconds === undefined || seconds === null) return '--';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

/**
 * Get status badge variant and color
 */
function getStatusInfo(status: string): { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string; color: string } {
  switch (status) {
    case 'pending':
      return { variant: 'secondary', label: 'Pending', color: 'text-muted-foreground' };
    case 'running':
      return { variant: 'default', label: 'Running', color: 'text-blue-600' };
    case 'completed':
      return { variant: 'default', label: 'Completed', color: 'text-green-600' };
    case 'partially_completed':
      return { variant: 'outline', label: 'Partially Completed', color: 'text-yellow-600' };
    case 'failed':
      return { variant: 'destructive', label: 'Failed', color: 'text-red-600' };
    case 'cancelled':
      return { variant: 'secondary', label: 'Cancelled', color: 'text-muted-foreground' };
    default:
      return { variant: 'secondary', label: status, color: 'text-muted-foreground' };
  }
}

/**
 * BulkTransformationProgress Component
 *
 * Displays real-time progress of a bulk transformation job including:
 * - Progress bar with percentage
 * - Column counts (processed, successful, failed)
 * - Currently processing column
 * - Estimated time remaining
 * - Cancel and retry actions
 */
export function BulkTransformationProgress({
  jobId,
  datasetId,
  onComplete,
  onCancel,
  pollInterval = 2000,
  className = ''
}: BulkTransformationProgressProps) {
  const [progress, setProgress] = useState<BulkTransformationProgressResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  // Poll for progress updates
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;
    let isMounted = true;

    const fetchProgress = async () => {
      try {
        const token = await getAuthToken();
        const response = await TransformationService.getBulkJobStatus(
          datasetId,
          jobId,
          token
        );

        if (!isMounted) return;

        setProgress(response);
        setError(null);

        // Check if job is complete
        const terminalStatuses = ['completed', 'failed', 'cancelled', 'partially_completed'];
        if (terminalStatuses.includes(response.status)) {
          if (intervalId) {
            clearInterval(intervalId);
          }
          onComplete(response);
        }
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : 'Failed to fetch progress');
      }
    };

    // Initial fetch
    fetchProgress();

    // Start polling
    intervalId = setInterval(fetchProgress, pollInterval);

    return () => {
      isMounted = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [jobId, datasetId, pollInterval, onComplete]);

  // Handle cancel
  const handleCancel = useCallback(async () => {
    setIsCancelling(true);
    try {
      const token = await getAuthToken();
      await TransformationService.cancelBulkJob(datasetId, jobId, token);
      onCancel?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel job');
    } finally {
      setIsCancelling(false);
    }
  }, [datasetId, jobId, onCancel]);

  // Handle retry
  const handleRetry = useCallback(async () => {
    setIsRetrying(true);
    try {
      const token = await getAuthToken();
      await TransformationService.retryBulkJob(datasetId, jobId, token);
      setError(null);
      // Progress polling will pick up the new status
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry job');
    } finally {
      setIsRetrying(false);
    }
  }, [datasetId, jobId]);

  const statusInfo = progress ? getStatusInfo(progress.status) : getStatusInfo('pending');
  const isTerminal = progress && ['completed', 'failed', 'cancelled', 'partially_completed'].includes(progress.status);
  const canCancel = progress && ['pending', 'running'].includes(progress.status);
  const canRetry = progress && progress.status === 'failed';

  return (
    <div className={`bg-card rounded-lg border border-border shadow-lg ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-border bg-muted flex items-center justify-between">
        <div className="flex items-center gap-3">
          {!isTerminal && (
            <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
          )}
          {progress?.status === 'completed' && (
            <CheckCircle className="w-5 h-5 text-green-500" />
          )}
          {progress?.status === 'failed' && (
            <XCircle className="w-5 h-5 text-red-500" />
          )}
          {progress?.status === 'partially_completed' && (
            <AlertTriangle className="w-5 h-5 text-yellow-500" />
          )}
          <h2 className="text-lg font-semibold text-foreground">
            Bulk Transformation Progress
          </h2>
        </div>
        <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
      </div>

      {/* Progress bar */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-muted-foreground">
            {progress?.processed_columns ?? 0} of {progress?.total_columns ?? 0} columns
          </span>
          <span className="text-sm font-medium">
            {Math.round(progress?.percentage_complete ?? 0)}%
          </span>
        </div>
        <Progress value={progress?.percentage_complete ?? 0} className="h-3" />
      </div>

      {/* Statistics */}
      <div className="p-4 border-b border-border grid grid-cols-2 gap-4">
        <div className="flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-green-500" />
          <span className="text-sm text-muted-foreground">Successful:</span>
          <span className="font-medium">{progress?.successful_columns ?? 0}</span>
        </div>
        <div className="flex items-center gap-2">
          <XCircle className="w-4 h-4 text-red-500" />
          <span className="text-sm text-muted-foreground">Failed:</span>
          <span className="font-medium">{progress?.failed_columns ?? 0}</span>
        </div>
        {progress?.current_column && !isTerminal && (
          <div className="col-span-2 flex items-center gap-2">
            <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
            <span className="text-sm text-muted-foreground">Processing:</span>
            <span className="font-medium text-blue-600 truncate">{progress.current_column}</span>
          </div>
        )}
        {progress?.estimated_remaining_seconds !== undefined && progress.estimated_remaining_seconds !== null && !isTerminal && (
          <div className="col-span-2 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-muted-foreground">Est. remaining:</span>
            <span className="font-medium">{formatTime(progress.estimated_remaining_seconds)}</span>
          </div>
        )}
      </div>

      {/* Error message */}
      {(error || progress?.error_message) && (
        <div className="p-4 border-b border-border">
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-red-700">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Error</p>
              <p className="text-sm">{error || progress?.error_message}</p>
            </div>
          </div>
        </div>
      )}

      {/* Results summary */}
      {progress?.result && (
        <div className="p-4 border-b border-border">
          <h3 className="font-medium text-foreground mb-2">Results</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total rows affected:</span>
              <span className="font-medium">{progress.result.total_rows_affected.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total time:</span>
              <span className="font-medium">{formatTime(progress.result.total_time_ms / 1000)}</span>
            </div>
            {progress.result.successful_columns.length > 0 && (
              <div>
                <p className="text-muted-foreground mb-1">Successful columns:</p>
                <div className="flex flex-wrap gap-1">
                  {progress.result.successful_columns.slice(0, 10).map(col => (
                    <Badge key={col} variant="secondary" className="text-xs bg-green-100 text-green-700">
                      {col}
                    </Badge>
                  ))}
                  {progress.result.successful_columns.length > 10 && (
                    <Badge variant="secondary" className="text-xs">
                      +{progress.result.successful_columns.length - 10} more
                    </Badge>
                  )}
                </div>
              </div>
            )}
            {progress.result.failed_columns.length > 0 && (
              <div>
                <p className="text-muted-foreground mb-1">Failed columns:</p>
                <div className="space-y-1">
                  {progress.result.failed_columns.slice(0, 5).map(({ column_name, error: colError }) => (
                    <div key={column_name} className="text-xs bg-red-50 p-2 rounded">
                      <span className="font-medium text-red-700">{column_name}:</span>
                      <span className="text-red-600 ml-1">{colError}</span>
                    </div>
                  ))}
                  {progress.result.failed_columns.length > 5 && (
                    <p className="text-xs text-muted-foreground">
                      +{progress.result.failed_columns.length - 5} more failed
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="p-4 flex gap-2">
        {canCancel && (
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={isCancelling}
            className="flex-1"
          >
            {isCancelling ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <X className="w-4 h-4 mr-2" />
            )}
            Cancel
          </Button>
        )}
        {canRetry && (
          <Button
            onClick={handleRetry}
            disabled={isRetrying}
            className="flex-1"
          >
            {isRetrying ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RotateCcw className="w-4 h-4 mr-2" />
            )}
            Retry
          </Button>
        )}
        {isTerminal && !canRetry && (
          <Button
            variant="outline"
            onClick={() => onComplete(progress!)}
            className="flex-1"
          >
            Close
          </Button>
        )}
      </div>
    </div>
  );
}

export default BulkTransformationProgress;
