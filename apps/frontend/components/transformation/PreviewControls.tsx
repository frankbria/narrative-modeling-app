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
  loading?: boolean;
}

const SAMPLE_SIZE_OPTIONS = [10, 50, 100, 500, 1000];

export function PreviewControls({
  sampleSize,
  onSampleSizeChange,
  onRefresh,
  loading = false,
}: PreviewControlsProps) {
  const [lastUpdated, setLastUpdated] = React.useState<Date | null>(null);

  // Update timestamp on load completion
  React.useEffect(() => {
    if (!loading) {
      setLastUpdated(new Date());
    }
  }, [loading]);

  const handleExport = () => {
    // TODO: Implement CSV export functionality
    console.log('Export preview data');
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
    <div className="flex items-center justify-between bg-white border rounded-lg p-4 shadow-sm gap-4">
      {/* Sample Size Selector */}
      <div className="flex items-center gap-2">
        <label
          htmlFor="sample-size"
          className="text-sm font-medium text-gray-700 whitespace-nowrap"
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
          <span className="text-xs text-gray-500 whitespace-nowrap">
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
          disabled={loading}
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
