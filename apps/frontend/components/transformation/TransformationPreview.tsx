'use client';

import React, { useState, useEffect } from 'react';
import { useDebounce } from '@/lib/hooks/useDebounce';
import type { TransformationStep, ParameterValue } from '@/lib/types/recipe';
import { getAuthToken } from '@/lib/auth-helpers';

// Child components (will be created by other agents)
import { BeforeAfterView } from './BeforeAfterView';
import { ImpactStats } from './ImpactStats';
import { PreviewControls } from './PreviewControls';

/**
 * Props interface for TransformationPreview component
 */
export interface TransformationPreviewProps {
  /** Dataset ID to preview transformations on */
  datasetId: string;
  /** Array of transformation operations to preview */
  operations: TransformationStep[];
  /** Sample size for preview (default: 100) */
  sampleSize?: number;
  /** Callback when sample size changes */
  onSampleSizeChange?: (size: number) => void;
}

/**
 * Impact statistics interface matching ImpactStats component expectations
 */
export interface ImpactStatistics {
  rows_affected: number;
  values_changed: number;
  columns_affected: string[];
  quality_score_before: number;
  quality_score_after: number;
  value_distributions?: Record<
    string,
    { before: Record<string, number>; after: Record<string, number> }
  >;
}

/**
 * Preview result structure from the transformation service
 */
export interface PreviewResult {
  original_data: Array<Record<string, ParameterValue>>;
  transformed_data: Array<Record<string, ParameterValue>>;
  impact_stats: ImpactStatistics;
  warnings: string[];
}

/**
 * Preview response from the API
 */
export interface PreviewResponse {
  success: boolean;
  preview_result?: PreviewResult;
  error?: string;
}

/**
 * TransformationPreview Component
 *
 * Main orchestration component that coordinates all child components for displaying
 * transformation previews. Manages state, data fetching, and error handling.
 *
 * Features:
 * - Debounced preview updates (300ms delay)
 * - Loading and error states
 * - Sample size controls
 * - Warning display
 * - Integration with child components (BeforeAfterView, ImpactStats, PreviewControls)
 *
 * @example
 * ```tsx
 * <TransformationPreview
 *   datasetId="dataset-123"
 *   operations={[
 *     { type: 'remove_duplicates', parameters: {} },
 *     { type: 'normalize', parameters: { method: 'minmax' } }
 *   ]}
 *   sampleSize={100}
 *   onSampleSizeChange={(size) => console.log('New size:', size)}
 * />
 * ```
 */
export function TransformationPreview({
  datasetId,
  operations,
  sampleSize = 100,
  onSampleSizeChange,
}: TransformationPreviewProps) {
  // State management
  const [previewData, setPreviewData] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localSampleSize, setLocalSampleSize] = useState(sampleSize);

  // Debounce operations changes (300ms)
  const debouncedOperations = useDebounce(operations, 300);
  const debouncedSampleSize = useDebounce(localSampleSize, 300);

  // Fetch preview when debounced values change
  useEffect(() => {
    if (!datasetId || debouncedOperations.length === 0) {
      setPreviewData(null);
      return;
    }

    // AbortController to cancel fetch on cleanup
    const abortController = new AbortController();
    let isMounted = true;

    const fetchPreview = async () => {
      if (!isMounted) return;

      setLoading(true);
      setError(null);

      try {
        const token = await getAuthToken();

        // Build transformation steps for the API
        const transformations = debouncedOperations.map((op) => ({
          type: op.type,
          parameters: op.parameters || {},
        }));

        // Call the service method with abort signal
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/transformations/pipeline/preview`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token && { Authorization: `Bearer ${token}` }),
            },
            body: JSON.stringify({
              dataset_id: datasetId,
              transformations,
              sample_size: debouncedSampleSize,
            }),
            signal: abortController.signal,
          }
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(
            errorData.detail || 'Failed to generate preview'
          );
        }

        const data = (await response.json()) as PreviewResponse;

        // Only update state if component is still mounted
        if (isMounted) {
          setPreviewData(data);
        }
      } catch (err) {
        // Ignore abort errors
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }

        // Only update state if component is still mounted
        if (isMounted) {
          setError(
            err instanceof Error ? err.message : 'Failed to generate preview'
          );
          setPreviewData(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchPreview();

    // Cleanup function
    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [datasetId, debouncedOperations, debouncedSampleSize]);

  // Handle sample size change
  const handleSampleSizeChange = (newSize: number) => {
    setLocalSampleSize(newSize);
    onSampleSizeChange?.(newSize);
  };

  // Handle retry on error
  const handleRetry = () => {
    setError(null);
    // Re-trigger useEffect by updating state
    setLocalSampleSize((prev) => prev);
  };

  // Export the current transformed preview as a CSV.
  // Uses RFC 4180-style field quoting and the Blob/anchor download pattern from
  // SelectedFeatureSet.tsx (LF line endings, matching that established convention).
  const transformedData = previewData?.preview_result?.transformed_data;

  const handleExport =
    transformedData && transformedData.length > 0
      ? () => {
          const escapeCsvField = (value: ParameterValue): string => {
            // Serialize arrays/objects as JSON so complex cells stay meaningful
            // instead of becoming "1,2,3" or "[object Object]".
            const field =
              value === null || value === undefined
                ? ''
                : typeof value === 'object'
                  ? JSON.stringify(value)
                  : String(value);
            if (
              field.includes(',') ||
              field.includes('"') ||
              field.includes('\n') ||
              field.includes('\r')
            ) {
              return `"${field.replace(/"/g, '""')}"`;
            }
            return field;
          };

          // Column set is the union of keys across rows, preserving first-seen order.
          const columns: string[] = [];
          const seen = new Set<string>();
          for (const row of transformedData) {
            for (const key of Object.keys(row)) {
              if (!seen.has(key)) {
                seen.add(key);
                columns.push(key);
              }
            }
          }

          const headerLine = columns.map(escapeCsvField).join(',');
          const dataLines = transformedData.map((row) =>
            columns.map((col) => escapeCsvField(row[col])).join(',')
          );
          const csv = [headerLine, ...dataLines].join('\n');

          const blob = new Blob([csv], { type: 'text/csv' });
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `transformation-preview-${datasetId}.csv`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(url);
        }
      : undefined;

  return (
    <div className="space-y-4">
      {/* Preview Controls */}
      <PreviewControls
        sampleSize={localSampleSize}
        onSampleSizeChange={handleSampleSizeChange}
        onRefresh={handleRetry}
        onExport={handleExport}
        loading={loading}
      />

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
          <span className="ml-2 text-gray-600">Generating preview...</span>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-red-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Preview Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
              <button
                onClick={handleRetry}
                className="mt-2 text-sm font-medium text-red-800 hover:text-red-900"
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Preview Data */}
      {previewData?.success && previewData.preview_result && !loading && (
        <>
          {/* Impact Statistics Dashboard */}
          <ImpactStats impactStats={previewData.preview_result.impact_stats} />

          {/* Before/After Comparison View */}
          <BeforeAfterView
            originalData={previewData.preview_result.original_data}
            transformedData={previewData.preview_result.transformed_data}
            impactStats={previewData.preview_result.impact_stats}
          />

          {/* Warnings */}
          {previewData.preview_result.warnings.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
              <h4 className="text-sm font-medium text-yellow-800">Warnings</h4>
              <ul className="mt-2 text-sm text-yellow-700 list-disc list-inside">
                {previewData.preview_result.warnings.map((warning, idx) => (
                  <li key={idx}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {/* No operations message */}
      {operations.length === 0 && !loading && (
        <div className="text-center p-8 text-gray-500">
          Add transformation operations to see a preview
        </div>
      )}
    </div>
  );
}
