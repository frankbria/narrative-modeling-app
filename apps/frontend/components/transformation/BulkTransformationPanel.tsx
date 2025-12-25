'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { Trash2, Play, Eye, AlertTriangle, Settings2 } from 'lucide-react';
import {
  TransformationService,
  BulkTransformationPreviewResponse,
  BulkTransformationJobResponse,
} from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';
import type { ParameterValue } from '@/lib/types/recipe';

/**
 * Props for the BulkTransformationPanel component
 */
interface BulkTransformationPanelProps {
  datasetId: string;
  selectedColumns: string[];
  onRemoveColumn: (column: string) => void;
  onClearAll: () => void;
  onPreview: (preview: BulkTransformationPreviewResponse) => void;
  onApply: (job: BulkTransformationJobResponse) => void;
  className?: string;
}

// Available transformation types for bulk operations
const transformationTypes = [
  { value: 'trim_whitespace', label: 'Trim Whitespace', description: 'Remove leading/trailing spaces' },
  { value: 'fill_mean', label: 'Fill with Mean', description: 'Replace missing values with column mean' },
  { value: 'fill_median', label: 'Fill with Median', description: 'Replace missing values with column median' },
  { value: 'fill_mode', label: 'Fill with Mode', description: 'Replace missing values with most common value' },
  { value: 'drop_missing', label: 'Drop Missing', description: 'Remove rows with missing values' },
  { value: 'to_numeric', label: 'To Numeric', description: 'Convert to numeric type' },
  { value: 'to_string', label: 'To String', description: 'Convert to text type' },
  { value: 'fix_casing', label: 'Fix Casing', description: 'Standardize text casing' },
  { value: 'remove_special_chars', label: 'Remove Special Characters', description: 'Clean special characters' },
];

/**
 * BulkTransformationPanel Component
 *
 * Configuration panel for bulk transformation operations including:
 * - Display selected columns with ability to remove
 * - Transformation type selection
 * - Error handling options (stop on error vs continue)
 * - Preview and Apply actions
 */
export function BulkTransformationPanel({
  datasetId,
  selectedColumns,
  onRemoveColumn,
  onClearAll,
  onPreview,
  onApply,
  className = ''
}: BulkTransformationPanelProps) {
  const [transformationType, setTransformationType] = useState<string>('');
  const [globalParameters, setGlobalParameters] = useState<Record<string, ParameterValue>>({});
  const [stopOnError, setStopOnError] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isApplyLoading, setIsApplyLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get selected transformation info
  const selectedTransformation = transformationTypes.find(t => t.value === transformationType);

  // Handle preview
  const handlePreview = useCallback(async () => {
    if (!transformationType || selectedColumns.length === 0) {
      setError('Please select columns and a transformation type');
      return;
    }

    setIsPreviewLoading(true);
    setError(null);

    try {
      const token = await getAuthToken();
      const response = await TransformationService.previewBulkTransformation(
        datasetId,
        {
          selected_columns: selectedColumns,
          transformation_type: transformationType,
          global_parameters: globalParameters,
          preview_rows: 10
        },
        token
      );

      onPreview(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview transformation');
    } finally {
      setIsPreviewLoading(false);
    }
  }, [datasetId, selectedColumns, transformationType, globalParameters, onPreview]);

  // Handle apply
  const handleApply = useCallback(async () => {
    if (!transformationType || selectedColumns.length === 0) {
      setError('Please select columns and a transformation type');
      return;
    }

    setIsApplyLoading(true);
    setError(null);

    try {
      const token = await getAuthToken();
      const response = await TransformationService.applyBulkTransformation(
        datasetId,
        {
          selected_columns: selectedColumns,
          transformation_type: transformationType,
          global_parameters: globalParameters,
          stop_on_error: stopOnError
        },
        token
      );

      onApply(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply transformation');
    } finally {
      setIsApplyLoading(false);
    }
  }, [datasetId, selectedColumns, transformationType, globalParameters, stopOnError, onApply]);

  return (
    <div className={`bg-white rounded-lg border border-gray-200 ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Bulk Transformation</h2>
          {selectedColumns.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearAll}
              className="text-gray-500 hover:text-red-600"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              Clear All
            </Button>
          )}
        </div>
      </div>

      {/* Selected columns */}
      <div className="p-4 border-b border-gray-200">
        <Label className="text-sm text-gray-700 mb-2 block">
          Selected Columns ({selectedColumns.length})
        </Label>
        {selectedColumns.length === 0 ? (
          <p className="text-sm text-gray-500 italic">No columns selected</p>
        ) : (
          <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
            {selectedColumns.map(column => (
              <span
                key={column}
                className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs"
              >
                {column}
                <button
                  onClick={() => onRemoveColumn(column)}
                  className="ml-1 hover:text-red-600 transition-colors"
                  aria-label={`Remove ${column}`}
                >
                  &times;
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Transformation selection */}
      <div className="p-4 border-b border-gray-200">
        <Label htmlFor="transformation-type" className="text-sm text-gray-700 mb-2 block">
          Transformation Type
        </Label>
        <Select value={transformationType} onValueChange={setTransformationType}>
          <SelectTrigger id="transformation-type">
            <SelectValue placeholder="Select transformation..." />
          </SelectTrigger>
          <SelectContent>
            {transformationTypes.map(t => (
              <SelectItem key={t.value} value={t.value}>
                <div>
                  <div className="font-medium">{t.label}</div>
                  <div className="text-xs text-gray-500">{t.description}</div>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {selectedTransformation && (
          <p className="mt-2 text-xs text-gray-600">
            <Settings2 className="w-3 h-3 inline mr-1" />
            {selectedTransformation.description}
          </p>
        )}
      </div>

      {/* Options */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <Label htmlFor="stop-on-error" className="text-sm text-gray-700">
              Stop on Error
            </Label>
            <p className="text-xs text-gray-500">
              Stop processing if any column fails
            </p>
          </div>
          <Switch
            id="stop-on-error"
            checked={stopOnError}
            onCheckedChange={setStopOnError}
          />
        </div>
      </div>

      {/* Summary */}
      {selectedColumns.length > 0 && transformationType && (
        <div className="p-4 border-b border-gray-200 bg-gray-50">
          <p className="text-sm text-gray-700">
            Will apply <strong>{selectedTransformation?.label}</strong> to{' '}
            <strong>{selectedColumns.length}</strong> column
            {selectedColumns.length !== 1 ? 's' : ''}
          </p>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="p-4 border-b border-gray-200">
          <div className="p-2 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="p-4 flex gap-2">
        <Button
          variant="outline"
          onClick={handlePreview}
          disabled={!transformationType || selectedColumns.length === 0 || isPreviewLoading}
          className="flex-1"
        >
          {isPreviewLoading ? (
            <div className="animate-spin rounded-full h-4 w-4 border border-gray-300 border-t-blue-500 mr-2" />
          ) : (
            <Eye className="w-4 h-4 mr-2" />
          )}
          Preview
        </Button>
        <Button
          onClick={handleApply}
          disabled={!transformationType || selectedColumns.length === 0 || isApplyLoading}
          className="flex-1"
        >
          {isApplyLoading ? (
            <div className="animate-spin rounded-full h-4 w-4 border border-gray-300 border-t-white mr-2" />
          ) : (
            <Play className="w-4 h-4 mr-2" />
          )}
          Apply
        </Button>
      </div>
    </div>
  );
}

export default BulkTransformationPanel;
