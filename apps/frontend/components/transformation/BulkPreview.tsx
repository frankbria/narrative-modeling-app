'use client';

import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import type { BulkTransformationPreviewResponse, ColumnPreviewResult } from '@/lib/services/transformation';

/**
 * Props for the BulkPreview component
 */
interface BulkPreviewProps {
  previewData: BulkTransformationPreviewResponse | null;
  isLoading?: boolean;
  className?: string;
}

/**
 * Single column preview detail component
 */
function ColumnPreviewDetail({ preview }: { preview: ColumnPreviewResult }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border border-border rounded-lg overflow-hidden mb-2">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 bg-muted hover:bg-muted transition-colors"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          )}
          {preview.success ? (
            <CheckCircle className="w-4 h-4 text-green-500" />
          ) : (
            <XCircle className="w-4 h-4 text-red-500" />
          )}
          <span className="font-medium text-sm">{preview.column_name}</span>
        </div>
        <div className="flex items-center gap-2">
          {preview.affected_rows > 0 && (
            <Badge variant="secondary" className="text-xs">
              {preview.affected_rows.toLocaleString()} rows affected
            </Badge>
          )}
          {preview.warnings.length > 0 && (
            <Badge variant="outline" className="text-xs text-yellow-600 border-yellow-300 dark:border-yellow-800">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {preview.warnings.length}
            </Badge>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="p-3 border-t border-border bg-card">
          {preview.error ? (
            <div className="p-2 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded text-red-700 dark:text-red-300 text-sm">
              {preview.error}
            </div>
          ) : (
            <div className="space-y-3">
              {/* Statistics comparison */}
              {preview.stats_before && preview.stats_after && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Before</p>
                    <div className="bg-muted p-2 rounded text-xs space-y-1">
                      {Object.entries(preview.stats_before).slice(0, 5).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="text-muted-foreground">{key}:</span>
                          <span className="font-mono">
                            {typeof value === 'number' ? value.toLocaleString() : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">After</p>
                    <div className="bg-green-50 dark:bg-green-950/40 p-2 rounded text-xs space-y-1">
                      {Object.entries(preview.stats_after).slice(0, 5).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="text-muted-foreground">{key}:</span>
                          <span className="font-mono">
                            {typeof value === 'number' ? value.toLocaleString() : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Preview data */}
              {preview.preview_data && preview.preview_data.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Sample Data</p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="bg-muted">
                          <th className="px-2 py-1 text-left font-medium text-muted-foreground">Row</th>
                          <th className="px-2 py-1 text-left font-medium text-muted-foreground">Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.preview_data.slice(0, 5).map((row, idx) => (
                          <tr key={idx} className="border-t border-gray-100">
                            <td className="px-2 py-1 text-muted-foreground">{idx + 1}</td>
                            <td className="px-2 py-1 font-mono">
                              {row[preview.column_name] !== null && row[preview.column_name] !== undefined
                                ? String(row[preview.column_name])
                                : <span className="text-gray-400 italic">null</span>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Warnings */}
              {preview.warnings.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-yellow-600 mb-1 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Warnings
                  </p>
                  <ul className="text-xs text-yellow-700 dark:text-yellow-300 space-y-1">
                    {preview.warnings.map((warning, idx) => (
                      <li key={idx} className="bg-yellow-50 dark:bg-yellow-950/40 p-1 rounded">
                        {warning}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * BulkPreview Component
 *
 * Displays preview results for bulk transformation operations including:
 * - Summary of affected columns and rows
 * - Per-column preview with before/after statistics
 * - Sample data preview for each column
 * - Warnings and errors per column
 */
export function BulkPreview({
  previewData,
  isLoading = false,
  className = ''
}: BulkPreviewProps) {
  const [activeTab, setActiveTab] = useState<'all' | 'successful' | 'failed'>('all');

  if (isLoading) {
    return (
      <div className={`bg-card rounded-lg border border-border ${className}`}>
        <div className="p-8 text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-border border-t-blue-500 mb-4" />
          <p className="text-sm text-muted-foreground">Generating preview...</p>
        </div>
      </div>
    );
  }

  if (!previewData) {
    return (
      <div className={`bg-card rounded-lg border border-border ${className}`}>
        <div className="p-8 text-center text-muted-foreground">
          <p className="text-sm">Select columns and a transformation to preview</p>
        </div>
      </div>
    );
  }

  // Filter previews based on tab
  const filteredPreviews = previewData.column_previews.filter(preview => {
    if (activeTab === 'successful') return preview.success;
    if (activeTab === 'failed') return !preview.success;
    return true;
  });

  return (
    <div className={`bg-card rounded-lg border border-border ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-border bg-muted">
        <h2 className="text-lg font-semibold text-foreground mb-2">Preview Results</h2>

        {/* Summary stats */}
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-1">
            <span className="text-muted-foreground">Total columns:</span>
            <span className="font-medium">{previewData.total_columns}</span>
          </div>
          <div className="flex items-center gap-1">
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span className="text-muted-foreground">Successful:</span>
            <span className="font-medium text-green-600">{previewData.successful_previews}</span>
          </div>
          <div className="flex items-center gap-1">
            <XCircle className="w-4 h-4 text-red-500" />
            <span className="text-muted-foreground">Failed:</span>
            <span className="font-medium text-red-600">{previewData.failed_previews}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-muted-foreground">Est. rows affected:</span>
            <span className="font-medium">{previewData.total_estimated_rows_affected.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Global error */}
      {previewData.error && (
        <div className="p-4 border-b border-border">
          <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg flex items-start gap-2 text-red-700 dark:text-red-300">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Error</p>
              <p className="text-sm">{previewData.error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Global warnings */}
      {previewData.warnings && previewData.warnings.length > 0 && (
        <div className="p-4 border-b border-border">
          <div className="p-3 bg-yellow-50 dark:bg-yellow-950/40 border border-yellow-200 dark:border-yellow-900 rounded-lg">
            <p className="font-medium text-yellow-700 dark:text-yellow-300 flex items-center gap-1 mb-1">
              <AlertTriangle className="w-4 h-4" />
              Warnings
            </p>
            <ul className="text-sm text-yellow-700 dark:text-yellow-300 list-disc list-inside">
              {previewData.warnings.map((warning, idx) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Column previews */}
      <div className="p-4">
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
          <TabsList className="mb-4">
            <TabsTrigger value="all">
              All ({previewData.total_columns})
            </TabsTrigger>
            <TabsTrigger value="successful">
              Successful ({previewData.successful_previews})
            </TabsTrigger>
            <TabsTrigger value="failed">
              Failed ({previewData.failed_previews})
            </TabsTrigger>
          </TabsList>

          <TabsContent value={activeTab} className="mt-0">
            {filteredPreviews.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No columns to display
              </p>
            ) : (
              <div className="max-h-96 overflow-y-auto">
                {filteredPreviews.map(preview => (
                  <ColumnPreviewDetail key={preview.column_name} preview={preview} />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default BulkPreview;
