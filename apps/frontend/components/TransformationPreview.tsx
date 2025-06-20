import React from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Info, AlertCircle, CheckCircle2 } from 'lucide-react';

interface TransformationPreviewProps {
  previewData?: {
    success: boolean;
    preview_data?: any[];
    affected_rows?: number;
    affected_columns?: string[];
    stats_before?: any;
    stats_after?: any;
    error?: string;
    warnings?: string[];
  };
  selectedNode?: any;
}

export function TransformationPreview({
  previewData,
  selectedNode,
}: TransformationPreviewProps) {
  if (!selectedNode) {
    return (
      <div className="h-64 border-t bg-gray-50 flex items-center justify-center">
        <div className="text-center text-gray-500">
          <Info className="w-8 h-8 mx-auto mb-2" />
          <p>Select a transformation to preview its effects</p>
        </div>
      </div>
    );
  }

  if (!previewData) {
    return (
      <div className="h-64 border-t bg-white flex items-center justify-center">
        <div className="text-center text-gray-500">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-2"></div>
          <p>Loading preview...</p>
        </div>
      </div>
    );
  }

  if (!previewData.success) {
    return (
      <div className="h-64 border-t bg-white p-4">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {previewData.error || 'Failed to preview transformation'}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const getChangedCells = (before: any[], after: any[]) => {
    const changes = new Set<string>();
    if (!before || !after) return changes;
    
    after.forEach((row, rowIdx) => {
      Object.keys(row).forEach((col) => {
        if (before[rowIdx] && before[rowIdx][col] !== row[col]) {
          changes.add(`${rowIdx}-${col}`);
        }
      });
    });
    return changes;
  };

  const changedCells = previewData.preview_data && previewData.stats_before?.original_data
    ? getChangedCells(previewData.stats_before.original_data, previewData.preview_data)
    : new Set();

  return (
    <div className="h-64 border-t bg-white">
      <Tabs defaultValue="preview" className="h-full flex flex-col">
        <div className="border-b px-4">
          <TabsList className="h-10">
            <TabsTrigger value="preview">Preview</TabsTrigger>
            <TabsTrigger value="stats">Statistics</TabsTrigger>
            <TabsTrigger value="info">Info</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="preview" className="flex-1 p-0 m-0">
          <ScrollArea className="h-full">
            {previewData.preview_data && previewData.preview_data.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    {Object.keys(previewData.preview_data[0]).map((col) => (
                      <TableHead
                        key={col}
                        className={
                          previewData.affected_columns?.includes(col)
                            ? 'bg-blue-50'
                            : ''
                        }
                      >
                        {col}
                        {previewData.affected_columns?.includes(col) && (
                          <Badge variant="outline" className="ml-2 text-xs">
                            Modified
                          </Badge>
                        )}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previewData.preview_data.slice(0, 50).map((row, idx) => (
                    <TableRow key={idx}>
                      {Object.entries(row).map(([col, value]) => (
                        <TableCell
                          key={col}
                          className={
                            changedCells.has(`${idx}-${col}`)
                              ? 'bg-yellow-50'
                              : ''
                          }
                        >
                          {String(value ?? '')}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-4 text-center text-gray-500">
                No preview data available
              </div>
            )}
          </ScrollArea>
        </TabsContent>

        <TabsContent value="stats" className="flex-1 p-4 overflow-auto">
          <div className="space-y-4">
            {previewData.stats_before && (
              <div>
                <h3 className="font-semibold mb-2">Before Transformation</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>Rows: {previewData.stats_before.row_count}</div>
                  <div>Columns: {previewData.stats_before.column_count}</div>
                  {previewData.stats_before.missing_values && (
                    <div className="col-span-2">
                      Missing Values:
                      <ul className="ml-4">
                        {Object.entries(previewData.stats_before.missing_values)
                          .filter(([_, count]: [string, any]) => count > 0)
                          .map(([col, count]) => (
                            <li key={col}>
                              {col}: {String(count)}
                            </li>
                          ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {previewData.stats_after && (
              <div>
                <h3 className="font-semibold mb-2">After Transformation</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>Rows: {previewData.stats_after.row_count}</div>
                  <div>Columns: {previewData.stats_after.column_count}</div>
                  {previewData.stats_after.missing_values && (
                    <div className="col-span-2">
                      Missing Values:
                      <ul className="ml-4">
                        {Object.entries(previewData.stats_after.missing_values)
                          .filter(([_, count]: [string, any]) => count > 0)
                          .map(([col, count]) => (
                            <li key={col}>
                              {col}: {String(count)}
                            </li>
                          ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="info" className="flex-1 p-4">
          <div className="space-y-3">
            <div>
              <h3 className="font-semibold mb-1">Transformation</h3>
              <p className="text-sm text-gray-600">{selectedNode.data.label}</p>
            </div>

            {previewData.affected_rows !== undefined && (
              <div>
                <h3 className="font-semibold mb-1">Affected Rows</h3>
                <p className="text-sm text-gray-600">{previewData.affected_rows}</p>
              </div>
            )}

            {previewData.affected_columns && previewData.affected_columns.length > 0 && (
              <div>
                <h3 className="font-semibold mb-1">Affected Columns</h3>
                <div className="flex flex-wrap gap-1">
                  {previewData.affected_columns.map((col) => (
                    <Badge key={col} variant="secondary">
                      {col}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {previewData.warnings && previewData.warnings.length > 0 && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  {previewData.warnings.map((warning, idx) => (
                    <div key={idx}>{warning}</div>
                  ))}
                </AlertDescription>
              </Alert>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}