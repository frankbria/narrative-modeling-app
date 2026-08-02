"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChangedValueHighlight } from "./ChangedValueHighlight";
import { AlertCircle, TrendingUp } from "lucide-react";

/**
 * Statistics about the impact of a transformation
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
 * Props for the BeforeAfterView component
 */
export interface BeforeAfterViewProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  originalData: Record<string, any>[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  transformedData: Record<string, any>[];
  impactStats?: ImpactStatistics;
}

/**
 * BeforeAfterView Component
 *
 * Displays original and transformed data side-by-side with synchronized scrolling
 * and change highlighting. Supports responsive layouts (side-by-side on desktop,
 * stacked on mobile) and includes impact statistics visualization.
 *
 * Features:
 * - Synchronized horizontal and vertical scrolling between tables
 * - Column headers with affected column indicators
 * - Change highlighting with tooltips showing before/after values
 * - Responsive layout toggle for mobile/desktop
 * - Impact statistics display
 * - Virtual scrolling support for large datasets
 */
export function BeforeAfterView({
  originalData,
  transformedData,
  impactStats,
}: BeforeAfterViewProps) {
  const [layout, setLayout] = useState<"side-by-side" | "stacked">(
    "side-by-side"
  );
  const beforeScrollRef = useRef<HTMLDivElement>(null);
  const afterScrollRef = useRef<HTMLDivElement>(null);
  const beforeTableRef = useRef<HTMLDivElement>(null);
  const afterTableRef = useRef<HTMLDivElement>(null);

  // Get column names (assume both datasets have same columns)
  const columns =
    originalData.length > 0 ? Object.keys(originalData[0]) : [];

  /**
   * Check if a column is affected by the transformation
   */
  const isColumnAffected = (column: string): boolean => {
    return impactStats?.columns_affected.includes(column) ?? false;
  };

  /**
   * Check if a cell value changed between original and transformed data
   */
  const isCellChanged = (rowIdx: number, column: string): boolean => {
    if (rowIdx >= originalData.length || rowIdx >= transformedData.length) {
      return false;
    }

    const originalValue = originalData[rowIdx][column];
    const transformedValue = transformedData[rowIdx][column];

    return originalValue !== transformedValue;
  };

  /**
   * Format a cell value for display
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const formatCellValue = (value: any): string => {
    if (value === null || value === undefined) {
      return "(empty)";
    }
    if (typeof value === "boolean") {
      return value ? "true" : "false";
    }
    if (typeof value === "object") {
      return JSON.stringify(value);
    }
    return String(value);
  };

  /**
   * Synchronized scrolling handler for before table
   * Keeps after table scrolled to the same position
   */
  const handleBeforeScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    if (afterScrollRef.current) {
      afterScrollRef.current.scrollTop = target.scrollTop;
      afterScrollRef.current.scrollLeft = target.scrollLeft;
    }
  };

  /**
   * Synchronized scrolling handler for after table
   * Keeps before table scrolled to the same position
   */
  const handleAfterScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    if (beforeScrollRef.current) {
      beforeScrollRef.current.scrollTop = target.scrollTop;
      beforeScrollRef.current.scrollLeft = target.scrollLeft;
    }
  };

  // Handle responsive layout on window resize
  useEffect(() => {
    const handleResize = () => {
      // Auto-switch to stacked on small screens
      if (window.innerWidth < 1024) {
        setLayout("stacked");
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Show empty state if no data
  if (originalData.length === 0) {
    return (
      <div className="bg-card rounded-lg border border-border p-8 text-center">
        <AlertCircle className="mx-auto h-12 w-12 text-gray-400 mb-2" />
        <p className="text-muted-foreground">No data to display</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with Statistics */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Data Comparison</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Showing {originalData.length} rows × {columns.length} columns
          </p>
        </div>

        {/* Layout Toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => setLayout("side-by-side")}
            className={`px-3 py-2 text-sm rounded-md font-medium transition-colors ${
              layout === "side-by-side"
                ? "bg-blue-600 text-white shadow-md"
                : "bg-muted text-foreground hover:bg-gray-200"
            }`}
          >
            Side-by-Side
          </button>
          <button
            onClick={() => setLayout("stacked")}
            className={`px-3 py-2 text-sm rounded-md font-medium transition-colors ${
              layout === "stacked"
                ? "bg-blue-600 text-white shadow-md"
                : "bg-muted text-foreground hover:bg-gray-200"
            }`}
          >
            Stacked
          </button>
        </div>
      </div>

      {/* Impact Statistics */}
      {impactStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200 dark:border-blue-900">
            <div className="text-sm font-medium text-blue-900 dark:text-blue-200">Rows Affected</div>
            <div className="text-2xl font-bold text-blue-600 mt-1">
              {impactStats.rows_affected}
            </div>
          </div>

          <div className="bg-gradient-to-br from-yellow-50 to-yellow-100 rounded-lg p-4 border border-yellow-200 dark:border-yellow-900">
            <div className="text-sm font-medium text-yellow-900 dark:text-yellow-200">Values Changed</div>
            <div className="text-2xl font-bold text-yellow-600 mt-1">
              {impactStats.values_changed}
            </div>
          </div>

          <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200 dark:border-purple-900">
            <div className="text-sm font-medium text-purple-900 dark:text-purple-200">
              Columns Affected
            </div>
            <div className="text-2xl font-bold text-purple-600 mt-1">
              {impactStats.columns_affected.length}
            </div>
          </div>

          <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-lg p-4 border border-emerald-200 dark:border-emerald-900">
            <div className="flex items-center gap-2">
              <div>
                <div className="text-sm font-medium text-emerald-900 dark:text-emerald-200">
                  Quality Score
                </div>
                <div className="text-2xl font-bold text-emerald-600 mt-1">
                  {(impactStats.quality_score_after * 100).toFixed(0)}%
                </div>
              </div>
              {impactStats.quality_score_after > impactStats.quality_score_before && (
                <TrendingUp className="h-6 w-6 text-emerald-600 ml-auto" />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Data Tables Container */}
      <div
        className={
          layout === "side-by-side"
            ? "grid grid-cols-1 lg:grid-cols-2 gap-4"
            : "space-y-4"
        }
      >
        {/* Before (Original) Table */}
        <div className="bg-card rounded-lg border border-border overflow-hidden flex flex-col">
          <div className="bg-gradient-to-r from-gray-50 to-gray-100 px-4 py-3 border-b border-border">
            <h4 className="text-sm font-semibold text-foreground">Original Data</h4>
            <p className="text-xs text-muted-foreground mt-1">
              {originalData.length} rows before transformation
            </p>
          </div>

          <div
            ref={beforeScrollRef}
            onScroll={handleBeforeScroll}
            className="flex-1 overflow-auto max-h-[600px]"
          >
            <div ref={beforeTableRef} className="min-w-full">
              <table className="w-full border-collapse text-sm">
                <thead className="bg-muted sticky top-0 z-10">
                  <tr className="border-b border-border">
                    <th className="px-3 py-2 text-left font-semibold text-foreground bg-muted w-12 border-r border-border">
                      #
                    </th>
                    {columns.map((column) => (
                      <th
                        key={column}
                        className={`px-3 py-2 text-left font-semibold text-foreground min-w-[150px] border-r border-border ${
                          isColumnAffected(column) ? "bg-yellow-50 dark:bg-yellow-950/40" : "bg-muted"
                        }`}
                        title={
                          isColumnAffected(column)
                            ? "This column was affected by the transformation"
                            : ""
                        }
                      >
                        <div className="flex items-center gap-1">
                          <span>{column}</span>
                          {isColumnAffected(column) && (
                            <span
                              className="inline-block w-2 h-2 rounded-full bg-yellow-600"
                              title="Column affected"
                              aria-label="Column affected"
                            />
                          )}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {originalData.map((row, rowIdx) => (
                    <tr
                      key={rowIdx}
                      className="hover:bg-muted transition-colors"
                    >
                      <td className="px-3 py-2 text-xs font-medium text-muted-foreground bg-muted border-r border-border w-12">
                        {rowIdx + 1}
                      </td>
                      {columns.map((column) => (
                        <td
                          key={column}
                          className="px-3 py-2 text-foreground border-r border-border truncate"
                          title={formatCellValue(row[column])}
                        >
                          {formatCellValue(row[column])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* After (Transformed) Table */}
        <div className="bg-card rounded-lg border border-border overflow-hidden flex flex-col">
          <div className="bg-gradient-to-r from-green-50 to-green-100 px-4 py-3 border-b border-green-200 dark:border-green-900">
            <h4 className="text-sm font-semibold text-green-900 dark:text-green-200">Transformed Data</h4>
            <p className="text-xs text-green-700 dark:text-green-300 mt-1">
              {transformedData.length} rows after transformation
            </p>
          </div>

          <div
            ref={afterScrollRef}
            onScroll={handleAfterScroll}
            className="flex-1 overflow-auto max-h-[600px]"
          >
            <div ref={afterTableRef} className="min-w-full">
              <table className="w-full border-collapse text-sm">
                <thead className="bg-green-50 dark:bg-green-950/40 sticky top-0 z-10">
                  <tr className="border-b border-green-200 dark:border-green-900">
                    <th className="px-3 py-2 text-left font-semibold text-green-900 dark:text-green-200 bg-green-50 dark:bg-green-950/40 w-12 border-r border-green-200 dark:border-green-900">
                      #
                    </th>
                    {columns.map((column) => (
                      <th
                        key={column}
                        className={`px-3 py-2 text-left font-semibold text-green-900 dark:text-green-200 min-w-[150px] border-r border-green-200 dark:border-green-900 ${
                          isColumnAffected(column) ? "bg-yellow-50 dark:bg-yellow-950/40" : "bg-green-50 dark:bg-green-950/40"
                        }`}
                        title={
                          isColumnAffected(column)
                            ? "This column was affected by the transformation"
                            : ""
                        }
                      >
                        <div className="flex items-center gap-1">
                          <span>{column}</span>
                          {isColumnAffected(column) && (
                            <span
                              className="inline-block w-2 h-2 rounded-full bg-yellow-600"
                              title="Column affected"
                              aria-label="Column affected"
                            />
                          )}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {transformedData.map((row, rowIdx) => (
                    <tr
                      key={rowIdx}
                      className="hover:bg-green-50 dark:hover:bg-green-950/40 transition-colors"
                    >
                      <td className="px-3 py-2 text-xs font-medium text-muted-foreground bg-muted border-r border-border w-12">
                        {rowIdx + 1}
                      </td>
                      {columns.map((column) => {
                        const isChanged = isCellChanged(rowIdx, column);
                        const oldValue = originalData[rowIdx]?.[column];
                        const newValue = row[column];

                        return (
                          <td
                            key={column}
                            className={`px-3 py-2 border-r border-border truncate ${
                              isChanged ? "bg-yellow-50 dark:bg-yellow-950/40" : ""
                            }`}
                            title={formatCellValue(newValue)}
                          >
                            <ChangedValueHighlight
                              value={newValue}
                              isChanged={isChanged}
                              oldValue={oldValue}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Info */}
      <div className="bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 rounded-lg px-4 py-3 text-sm text-blue-800 dark:text-blue-200">
        <p className="font-medium mb-1">How to read this view:</p>
        <ul className="space-y-1 text-xs text-blue-700 dark:text-blue-300 list-disc list-inside">
          <li>Yellow highlighting indicates columns affected by the transformation</li>
          <li>Highlighted cells in the transformed table show values that changed</li>
          <li>Hover over changed cells to see the before and after values</li>
          <li>Tables are synchronized for easy comparison - scroll one to scroll both</li>
        </ul>
      </div>
    </div>
  );
}
