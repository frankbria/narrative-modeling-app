/**
 * Example usage of the ColumnSelector component
 * This file demonstrates how to integrate ColumnSelector into a larger component
 */

'use client';

import React, { useState } from 'react';
import { ColumnSelector } from './ColumnSelector';
import { Button } from '@/components/ui/button';

/**
 * Simple example: Basic column selection
 */
export function ColumnSelectorBasicExample() {
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set());

  const handleApply = () => {
    console.log('Selected columns:', Array.from(selectedColumns));
  };

  return (
    <div className="w-full h-screen flex flex-col">
      <div className="p-4 border-b">
        <h1 className="text-2xl font-bold">Select Columns</h1>
        <p className="text-gray-600">Choose which columns to include in your analysis</p>
      </div>

      <div className="flex-1 flex gap-4 p-4">
        <div className="w-96">
          <ColumnSelector
            datasetId="my-dataset-id"
            selectedColumns={selectedColumns}
            onSelectionChange={setSelectedColumns}
          />
        </div>

        <div className="flex-1 flex flex-col">
          <div className="bg-gray-50 p-4 rounded-lg flex-1">
            <h2 className="font-bold mb-2">Summary</h2>
            <p className="text-sm text-gray-600 mb-4">
              {selectedColumns.size} columns selected
            </p>
            {selectedColumns.size > 0 && (
              <div>
                <p className="text-sm font-medium mb-2">Selected columns:</p>
                <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                  {Array.from(selectedColumns).map(col => (
                    <li key={col}>{col}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="mt-4 flex gap-2">
            <Button
              onClick={handleApply}
              disabled={selectedColumns.size === 0}
              className="flex-1"
            >
              Continue ({selectedColumns.size} columns)
            </Button>
            <Button variant="outline" className="flex-1">
              Cancel
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Advanced example: Column selection with filtering and preview
 */
export function ColumnSelectorAdvancedExample() {
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set());
  const [previewData, setPreviewData] = useState<Record<string, any>[]>([]);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  const handleSelectionChange = (columns: Set<string>) => {
    setSelectedColumns(columns);
    // Optionally fetch preview for selected columns
    if (columns.size > 0) {
      loadPreview(columns);
    } else {
      setPreviewData([]);
    }
  };

  const loadPreview = async (columns: Set<string>) => {
    setIsLoadingPreview(true);
    try {
      // Simulate API call to get preview data
      const response = await fetch('/api/v1/data/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          columns: Array.from(columns)
        })
      });
      const data = await response.json();
      setPreviewData(data.rows || []);
    } catch (error) {
      console.error('Failed to load preview:', error);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  return (
    <div className="w-full h-screen flex flex-col">
      <div className="p-4 border-b bg-gradient-to-r from-blue-50 to-purple-50">
        <h1 className="text-2xl font-bold text-gray-900">Data Preparation</h1>
        <p className="text-gray-600">Step 1: Select columns to analyze</p>
      </div>

      <div className="flex-1 flex gap-4 p-4 overflow-hidden">
        {/* Sidebar: Column Selector */}
        <div className="w-96 flex flex-col">
          <div className="bg-white rounded-lg shadow flex-1 flex flex-col">
            <ColumnSelector
              datasetId="advanced-dataset"
              selectedColumns={selectedColumns}
              onSelectionChange={handleSelectionChange}
              className="flex-1"
            />
          </div>

          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <h3 className="font-medium text-sm mb-2">Tip</h3>
            <p className="text-xs text-gray-600">
              Select columns to see a preview of your data. Use the search box to quickly find columns.
            </p>
          </div>
        </div>

        {/* Main: Preview */}
        <div className="flex-1 flex flex-col">
          <div className="bg-white rounded-lg shadow flex-1 overflow-hidden flex flex-col">
            <div className="p-4 border-b">
              <h2 className="font-bold">
                Preview ({selectedColumns.size} columns)
              </h2>
            </div>

            {isLoadingPreview ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border border-gray-300 border-t-blue-500 mb-2" />
                  <p className="text-sm text-gray-600">Loading preview...</p>
                </div>
              </div>
            ) : selectedColumns.size === 0 ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <p className="text-gray-500">Select columns to see preview</p>
                </div>
              </div>
            ) : previewData.length === 0 ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <p className="text-gray-500">No preview data available</p>
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-gray-50 border-b">
                    <tr>
                      {Array.from(selectedColumns).map(col => (
                        <th
                          key={col}
                          className="px-4 py-2 text-left font-medium text-gray-700 truncate"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.slice(0, 10).map((row, idx) => (
                      <tr key={idx} className="border-b hover:bg-gray-50">
                        {Array.from(selectedColumns).map(col => (
                          <td
                            key={col}
                            className="px-4 py-2 text-gray-600 truncate"
                          >
                            {String(row[col] ?? '-')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="mt-4 flex gap-2 justify-end">
            <Button variant="outline">Back</Button>
            <Button
              disabled={selectedColumns.size === 0}
              className="px-8"
            >
              Next Step
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Example: Column selection with pre-selected columns
 */
export function ColumnSelectorWithPreselectExample() {
  const defaultColumns = new Set(['user_id', 'email', 'created_at']);
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(defaultColumns);

  return (
    <div className="w-96">
      <div className="mb-4">
        <h3 className="font-bold mb-2">Pre-selected Columns</h3>
        <p className="text-sm text-gray-600">
          These columns are recommended for analysis. You can add or remove columns as needed.
        </p>
      </div>

      <ColumnSelector
        datasetId="dataset-with-defaults"
        selectedColumns={selectedColumns}
        onSelectionChange={setSelectedColumns}
        className="h-96"
      />
    </div>
  );
}

/**
 * Example: Responsive layout for mobile
 */
export function ColumnSelectorResponsiveExample() {
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set());
  const [showPreview, setShowPreview] = useState(false);

  return (
    <div className="w-full h-screen flex flex-col md:flex-row gap-4 p-4">
      {/* Column Selector - Full width on mobile, sidebar on desktop */}
      <div className="w-full md:w-80 h-96 md:h-auto">
        <ColumnSelector
          datasetId="responsive-dataset"
          selectedColumns={selectedColumns}
          onSelectionChange={setSelectedColumns}
        />
      </div>

      {/* Summary - Below selector on mobile, beside on desktop */}
      <div className="flex-1 bg-white rounded-lg p-4 border">
        <h2 className="font-bold mb-4">
          Selected Columns ({selectedColumns.size})
        </h2>
        {selectedColumns.size === 0 ? (
          <p className="text-gray-500">No columns selected</p>
        ) : (
          <ul className="space-y-2">
            {Array.from(selectedColumns).map(col => (
              <li
                key={col}
                className="px-3 py-2 bg-blue-50 rounded-lg text-sm font-medium"
              >
                {col}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
