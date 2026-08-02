'use client';

import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

interface PreviewPanelProps {
  preview: any;
  loading: boolean;
}

export default function PreviewPanel({ preview, loading }: PreviewPanelProps) {
  const [showBefore, setShowBefore] = useState(true);

  if (loading) {
    return (
      <div className="w-96 bg-card border-l flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-sm text-muted-foreground">Loading preview...</p>
        </div>
      </div>
    );
  }

  if (!preview) {
    return (
      <div className="w-96 bg-card border-l flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <Eye className="w-12 h-12 mx-auto mb-2 opacity-20" />
          <p className="text-sm">No preview available</p>
          <p className="text-xs mt-1">Add transformations to see results</p>
        </div>
      </div>
    );
  }

  const data = showBefore ? preview.before : preview.after;
  const columns = data?.columns || [];
  const rows = data?.data || [];

  return (
    <div className="w-96 bg-card border-l flex flex-col">
      <div className="p-4 border-b">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold">Preview</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowBefore(true)}
              className={`px-3 py-1 text-sm rounded ${
                showBefore
                  ? 'bg-blue-600 text-white'
                  : 'bg-muted text-foreground hover:bg-gray-200'
              }`}
            >
              Before
            </button>
            <button
              onClick={() => setShowBefore(false)}
              className={`px-3 py-1 text-sm rounded ${
                !showBefore
                  ? 'bg-blue-600 text-white'
                  : 'bg-muted text-foreground hover:bg-gray-200'
              }`}
            >
              After
            </button>
          </div>
        </div>
        {preview.summary && (
          <div className="text-xs text-muted-foreground">
            <p>Rows: {preview.summary.rows_before} → {preview.summary.rows_after}</p>
            <p>Columns: {preview.summary.cols_before} → {preview.summary.cols_after}</p>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-auto">
        {columns.length > 0 ? (
          <table className="w-full text-xs">
            <thead className="bg-muted sticky top-0">
              <tr>
                {columns.map((col: string, idx: number) => (
                  <th
                    key={idx}
                    className="px-2 py-2 text-left font-medium text-foreground border-b"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any[], rowIdx: number) => (
                <tr key={rowIdx} className="border-b hover:bg-muted">
                  {row.map((cell: any, cellIdx: number) => (
                    <td key={cellIdx} className="px-2 py-2">
                      {cell === null || cell === undefined ? (
                        <span className="text-gray-400 italic">null</span>
                      ) : (
                        String(cell)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-4 text-center text-muted-foreground">
            <p>No data to display</p>
          </div>
        )}
      </div>

      <div className="p-2 border-t bg-muted text-xs text-muted-foreground text-center">
        Showing first 100 rows
      </div>
    </div>
  );
}