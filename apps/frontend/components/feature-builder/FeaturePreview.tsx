'use client';

import React, { useState } from 'react';
import { AlertCircle, CheckCircle, AlertTriangle, BarChart2, Table, Loader2 } from 'lucide-react';

interface Statistics {
  mean?: number | null;
  median?: number | null;
  std?: number | null;
  min?: number | null;
  max?: number | null;
  null_count: number;
  unique_count: number;
  total_count: number;
}

interface DistributionBin {
  bin_start: number;
  bin_end: number;
  count: number;
  label: string;
}

export interface PreviewData {
  success: boolean;
  values: unknown[];
  statistics: Statistics | null;
  distribution: DistributionBin[];
  formula: string | null;
  input_columns: string[];
  inferred_type: string;
  sample_data: Record<string, any>[] | null;
  error: string | null;
  warnings: string[];
}

export interface ValidationResult {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  inferred_type: string | null;
  potential_issues: string[];
}

interface FeaturePreviewProps {
  preview: PreviewData | null;
  loading: boolean;
  validationResult: ValidationResult | null;
}

type ViewMode = 'stats' | 'distribution' | 'table';

export default function FeaturePreview({
  preview,
  loading,
  validationResult,
}: FeaturePreviewProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('stats');

  if (loading) {
    return (
      <div className="w-80 bg-gray-50 border-l p-4 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-2" />
          <p className="text-gray-600">Computing preview...</p>
        </div>
      </div>
    );
  }

  if (!preview && !validationResult) {
    return (
      <div className="w-80 bg-gray-50 border-l p-4">
        <div className="text-center text-gray-500 mt-8">
          <BarChart2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="font-medium">No Preview Yet</p>
          <p className="text-sm mt-1">Click Preview to see the computed feature values</p>
        </div>
      </div>
    );
  }

  const formatNumber = (num: number | null | undefined): string => {
    if (num === null || num === undefined) return '-';
    if (Number.isInteger(num)) return num.toString();
    return num.toFixed(4);
  };

  const renderValidation = () => {
    if (!validationResult) return null;

    return (
      <div className="mb-4 p-3 rounded-lg border bg-white">
        <div className="flex items-center gap-2 mb-2">
          {validationResult.is_valid ? (
            <>
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className="font-medium text-green-800">Valid Expression</span>
            </>
          ) : (
            <>
              <AlertCircle className="w-5 h-5 text-red-600" />
              <span className="font-medium text-red-800">Invalid Expression</span>
            </>
          )}
        </div>

        {validationResult.errors.length > 0 && (
          <div className="text-sm text-red-600 space-y-1">
            {validationResult.errors.map((error, i) => (
              <div key={i} className="flex items-start gap-1">
                <span className="text-red-400">-</span>
                <span>{error}</span>
              </div>
            ))}
          </div>
        )}

        {validationResult.warnings.length > 0 && (
          <div className="text-sm text-amber-600 space-y-1 mt-2">
            {validationResult.warnings.map((warning, i) => (
              <div key={i} className="flex items-start gap-1">
                <AlertTriangle className="w-3 h-3 mt-0.5" />
                <span>{warning}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderStats = () => {
    if (!preview?.statistics) return null;
    const stats = preview.statistics;

    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="p-2 bg-white rounded border">
            <div className="text-gray-500 text-xs">Mean</div>
            <div className="font-mono">{formatNumber(stats.mean)}</div>
          </div>
          <div className="p-2 bg-white rounded border">
            <div className="text-gray-500 text-xs">Median</div>
            <div className="font-mono">{formatNumber(stats.median)}</div>
          </div>
          <div className="p-2 bg-white rounded border">
            <div className="text-gray-500 text-xs">Std Dev</div>
            <div className="font-mono">{formatNumber(stats.std)}</div>
          </div>
          <div className="p-2 bg-white rounded border">
            <div className="text-gray-500 text-xs">Min / Max</div>
            <div className="font-mono text-xs">
              {formatNumber(stats.min)} / {formatNumber(stats.max)}
            </div>
          </div>
          <div className="p-2 bg-white rounded border">
            <div className="text-gray-500 text-xs">Null Count</div>
            <div className="font-mono">{stats.null_count}</div>
          </div>
          <div className="p-2 bg-white rounded border">
            <div className="text-gray-500 text-xs">Unique</div>
            <div className="font-mono">{stats.unique_count}</div>
          </div>
        </div>

        <div className="p-2 bg-white rounded border text-sm">
          <div className="text-gray-500 text-xs mb-1">Sample Values</div>
          <div className="font-mono text-xs max-h-32 overflow-y-auto">
            {preview.values.slice(0, 10).map((val, i) => (
              <span key={i} className="inline-block bg-gray-100 px-1.5 py-0.5 rounded mr-1 mb-1">
                {val === null ? 'null' : String(val)}
              </span>
            ))}
            {preview.values.length > 10 && (
              <span className="text-gray-400">...+{preview.values.length - 10} more</span>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderDistribution = () => {
    if (!preview?.distribution || preview.distribution.length === 0) {
      return (
        <div className="text-center text-gray-500 py-8">
          No distribution data available
        </div>
      );
    }

    const maxCount = Math.max(...preview.distribution.map(b => b.count));
    // Guard against division by zero - use at least 1 for the denominator
    const safeMax = maxCount === 0 ? 1 : maxCount;

    return (
      <div className="space-y-2">
        {preview.distribution.map((bin, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <div className="w-20 text-xs text-gray-500 truncate" title={bin.label}>
              {bin.label}
            </div>
            <div className="flex-1 h-4 bg-gray-200 rounded overflow-hidden">
              <div
                className="h-full bg-blue-500"
                style={{ width: `${(bin.count / safeMax) * 100}%` }}
              />
            </div>
            <div className="w-12 text-xs text-right text-gray-600">
              {bin.count}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderTable = () => {
    if (!preview?.sample_data || preview.sample_data.length === 0) {
      return (
        <div className="text-center text-gray-500 py-8">
          No sample data available
        </div>
      );
    }

    const columns = Object.keys(preview.sample_data[0]);

    return (
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-100">
              {columns.map((col) => (
                <th
                  key={col}
                  className={`px-2 py-1 text-left font-medium truncate ${
                    col === '_computed_feature' ? 'bg-blue-100 text-blue-800' : ''
                  }`}
                >
                  {col === '_computed_feature' ? 'Result' : col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.sample_data.slice(0, 10).map((row, i) => (
              <tr key={i} className="border-b">
                {columns.map((col) => (
                  <td
                    key={col}
                    className={`px-2 py-1 truncate max-w-[100px] ${
                      col === '_computed_feature' ? 'bg-blue-50 font-medium' : ''
                    }`}
                  >
                    {row[col] === null ? (
                      <span className="text-gray-400">null</span>
                    ) : (
                      String(row[col])
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="w-80 bg-gray-50 border-l overflow-y-auto">
      <div className="p-4">
        <h3 className="font-semibold text-gray-800 mb-3">Preview</h3>

        {/* Error display */}
        {preview?.error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-red-800">Preview Failed</p>
                <p className="text-sm text-red-600 mt-1">{preview.error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Warnings */}
        {preview?.warnings && preview.warnings.length > 0 && (
          <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-amber-800">Warnings</p>
                <ul className="text-sm text-amber-600 mt-1 list-disc list-inside">
                  {preview.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Validation result */}
        {renderValidation()}

        {/* Formula */}
        {preview?.formula && (
          <div className="mb-4 p-3 rounded-lg bg-white border">
            <div className="text-xs text-gray-500 mb-1">Formula</div>
            <code className="text-sm font-mono text-gray-800 break-all">
              {preview.formula}
            </code>
          </div>
        )}

        {/* View mode tabs */}
        {preview?.success && (
          <>
            <div className="flex border-b mb-4">
              <button
                onClick={() => setViewMode('stats')}
                className={`flex-1 px-3 py-2 text-sm ${
                  viewMode === 'stats'
                    ? 'border-b-2 border-blue-600 text-blue-600 font-medium'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Statistics
              </button>
              <button
                onClick={() => setViewMode('distribution')}
                className={`flex-1 px-3 py-2 text-sm ${
                  viewMode === 'distribution'
                    ? 'border-b-2 border-blue-600 text-blue-600 font-medium'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Distribution
              </button>
              <button
                onClick={() => setViewMode('table')}
                className={`flex-1 px-3 py-2 text-sm ${
                  viewMode === 'table'
                    ? 'border-b-2 border-blue-600 text-blue-600 font-medium'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Table
              </button>
            </div>

            {/* View content */}
            {viewMode === 'stats' && renderStats()}
            {viewMode === 'distribution' && renderDistribution()}
            {viewMode === 'table' && renderTable()}
          </>
        )}
      </div>
    </div>
  );
}
