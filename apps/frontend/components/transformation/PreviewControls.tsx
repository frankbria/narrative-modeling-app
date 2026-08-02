'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { RefreshCw, Download } from 'lucide-react';

export interface PreviewControlsProps {
  sampleSize: number;
  onSampleSizeChange: (size: number) => void;
  onRefresh?: () => void;
  /** Invoked when the Export button is clicked; export is disabled when omitted */
  onExport?: () => void;
  loading?: boolean;
}

const SAMPLE_SIZE_OPTIONS = [10, 50, 100, 500, 1000];

export function PreviewControls({
  sampleSize,
  onSampleSizeChange,
  onRefresh,
  onExport,
  loading = false,
}: PreviewControlsProps) {
  // Seeded, not null: the old effect ran on mount too, so a component that mounts
  // already-loaded shows a timestamp immediately rather than only after the next load.
  const [lastUpdated, setLastUpdated] = React.useState<Date | null>(() =>
    loading ? null : new Date(),
  );
  const [wasLoading, setWasLoading] = React.useState(loading);

  // Not a data load — this stamps the time a load finished. React's documented
  // way to adjust state from a prop change is to do it during render rather than
  // in an effect, which also avoids the extra render pass the effect caused.
  if (wasLoading !== loading) {
    setWasLoading(loading);
    if (!loading) {
      setLastUpdated(new Date());
    }
  }

  const handleExport = () => {
    onExport?.();
  };

  const formatTimestamp = (date: Date | null): string => {
    if (!date) return '';
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffSeconds < 60) return 'Just now';
    if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
    if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`;
    return date.toLocaleString();
  };

  return (
    <div className="flex items-center justify-between bg-card border rounded-lg p-4 shadow-sm gap-4">
      {/* Sample Size Selector */}
      <div className="flex items-center gap-2">
        <label
          htmlFor="sample-size"
          className="text-sm font-medium text-foreground whitespace-nowrap"
        >
          Sample Size:
        </label>
        <Select
          value={String(sampleSize)}
          onValueChange={(value) => onSampleSizeChange(Number(value))}
          disabled={loading}
        >
          <SelectTrigger className="w-24">
            <SelectValue placeholder="Select size" />
          </SelectTrigger>
          <SelectContent>
            {SAMPLE_SIZE_OPTIONS.map((size) => (
              <SelectItem key={size} value={String(size)}>
                {size} rows
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Right-side Controls */}
      <div className="flex items-center gap-3 ml-auto">
        {/* Last Updated */}
        {lastUpdated && (
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            Updated {formatTimestamp(lastUpdated)}
          </span>
        )}

        {/* Refresh Button */}
        {onRefresh && (
          <Button
            onClick={onRefresh}
            disabled={loading}
            variant="outline"
            size="sm"
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`}
            />
            {loading ? 'Refreshing...' : 'Refresh'}
          </Button>
        )}

        {/* Export Button */}
        <Button
          onClick={handleExport}
          disabled={loading || !onExport}
          variant="outline"
          size="sm"
        >
          <Download className="h-4 w-4 mr-2" />
          Export
        </Button>
      </div>
    </div>
  );
}
