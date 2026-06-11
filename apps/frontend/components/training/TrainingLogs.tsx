'use client';

import { useEffect, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { modelService, TrainingLogEntry } from '@/lib/services/model';

/** Fetch up to this many log entries per poll. */
const LOG_FETCH_LIMIT = 500;

type LevelFilter = 'all' | 'warning' | 'error';

interface TrainingLogsProps {
  modelId: string;
  /** Log poll interval in ms while the job is active. */
  pollInterval?: number;
  maxHeight?: string;
  /** Scroll to the newest entry when new logs arrive. */
  autoScroll?: boolean;
  /** When false (terminal job) polling stops after one final fetch. */
  isActive?: boolean;
}

const LEVEL_STYLES: Record<TrainingLogEntry['level'], string> = {
  info: 'text-gray-600',
  warning: 'text-amber-700',
  error: 'text-red-700',
};

function matchesFilter(entry: TrainingLogEntry, filter: LevelFilter): boolean {
  if (filter === 'all') return true;
  if (filter === 'warning') return entry.level === 'warning' || entry.level === 'error';
  return entry.level === 'error';
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
}

/**
 * Live training log viewer.
 *
 * Polls `GET /ml/{model_id}/logs` every `pollInterval` ms while `isActive`,
 * otherwise performs a single fetch (terminal job). Level filtering is applied
 * client-side so the All / Warnings + Errors / Errors toggles are instant.
 */
export function TrainingLogs({
  modelId,
  pollInterval = 5000,
  maxHeight = '16rem',
  autoScroll = true,
  isActive = true,
}: TrainingLogsProps) {
  const [logs, setLogs] = useState<TrainingLogEntry[]>([]);
  const [filter, setFilter] = useState<LevelFilter>('all');
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let isMounted = true;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const fetchLogs = async () => {
      try {
        const response = await modelService.getTrainingLogs(modelId, {
          limit: LOG_FETCH_LIMIT,
        });
        if (!isMounted) return;
        setLogs(response.logs);
      } catch {
        // Logs are auxiliary; a failed poll keeps the previous entries and the
        // next interval tick (or the progress panel's connection warning)
        // surfaces persistent connectivity problems.
      }
    };

    // Always fetch once — including a final fetch when the job just ended.
    fetchLogs();

    if (isActive) {
      intervalId = setInterval(fetchLogs, pollInterval);
    }

    return () => {
      isMounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [modelId, pollInterval, isActive]);

  // Keep the newest entry visible as logs stream in.
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const visibleLogs = logs.filter((entry) => matchesFilter(entry, filter));

  const filterButton = (value: LevelFilter, label: string) => (
    <Button
      variant={filter === value ? 'secondary' : 'ghost'}
      size="sm"
      onClick={() => setFilter(value)}
    >
      {label}
    </Button>
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1">
        {filterButton('all', 'All')}
        {filterButton('warning', 'Warnings + Errors')}
        {filterButton('error', 'Errors only')}
      </div>

      <div
        ref={containerRef}
        className="overflow-y-auto rounded-md border border-gray-200 bg-gray-50 p-3 font-mono text-xs"
        style={{ maxHeight }}
      >
        {visibleLogs.length === 0 ? (
          <p className="text-gray-500 font-sans">No log entries yet.</p>
        ) : (
          <ul className="space-y-1">
            {visibleLogs.map((entry, index) => (
              <li
                key={`${entry.timestamp}-${index}`}
                className="flex items-start gap-2"
              >
                <span className="text-gray-400 shrink-0">
                  {formatTimestamp(entry.timestamp)}
                </span>
                {entry.stage && (
                  <Badge variant="outline" className="shrink-0 font-sans">
                    {entry.stage}
                  </Badge>
                )}
                <span className={LEVEL_STYLES[entry.level]}>{entry.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default TrainingLogs;
