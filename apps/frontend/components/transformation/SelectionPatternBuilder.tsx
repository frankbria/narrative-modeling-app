'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { Hash, Type, Calendar, ToggleLeft, Layers, Search, AlertTriangle } from 'lucide-react';
import {
  TransformationService,
  ColumnSelectionPatternRequest,
  ColumnMetadata
} from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';

/**
 * Props for the SelectionPatternBuilder component
 */
interface SelectionPatternBuilderProps {
  datasetId: string;
  onPatternApply: (columns: ColumnMetadata[]) => void;
  className?: string;
}

type PatternType = 'data_type' | 'name_pattern' | 'quality_metric';

/**
 * SelectionPatternBuilder Component
 *
 * A component for building column selection patterns including:
 * - By Data Type: Select numeric, text, datetime, boolean, categorical columns
 * - By Name Pattern: Regex or wildcard pattern matching on column names
 * - By Quality Metrics: Select columns based on missing values, cardinality, etc.
 */
export function SelectionPatternBuilder({
  datasetId,
  onPatternApply,
  className = ''
}: SelectionPatternBuilderProps) {
  const [activeTab, setActiveTab] = useState<PatternType>('data_type');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewColumns, setPreviewColumns] = useState<ColumnMetadata[] | null>(null);

  // Data type state
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());

  // Name pattern state
  const [namePattern, setNamePattern] = useState('');

  // Quality metric state
  const [selectedMetric, setSelectedMetric] = useState<string>('missing_values');
  const [metricOperator, setMetricOperator] = useState<string>('gt');
  const [metricThreshold, setMetricThreshold] = useState<number>(0);

  // Toggle data type selection
  const handleTypeToggle = useCallback((type: string) => {
    setSelectedTypes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(type)) {
        newSet.delete(type);
      } else {
        newSet.add(type);
      }
      return newSet;
    });
    setPreviewColumns(null);
    setError(null);
  }, []);

  // Build pattern request based on current state
  const buildPatternRequest = useCallback((): ColumnSelectionPatternRequest | null => {
    switch (activeTab) {
      case 'data_type':
        if (selectedTypes.size === 0) {
          setError('Please select at least one data type');
          return null;
        }
        return {
          pattern_type: 'data_type',
          criteria: { types: Array.from(selectedTypes) }
        };

      case 'name_pattern':
        if (!namePattern.trim()) {
          setError('Please enter a name pattern');
          return null;
        }
        return {
          pattern_type: 'name_pattern',
          criteria: { pattern: namePattern.trim() }
        };

      case 'quality_metric':
        return {
          pattern_type: 'quality_metric',
          criteria: {
            metric: selectedMetric,
            operator: metricOperator,
            threshold: metricThreshold
          }
        };

      default:
        return null;
    }
  }, [activeTab, selectedTypes, namePattern, selectedMetric, metricOperator, metricThreshold]);

  // Preview pattern results
  const handlePreview = useCallback(async () => {
    const pattern = buildPatternRequest();
    if (!pattern) return;

    setIsLoading(true);
    setError(null);

    try {
      const token = await getAuthToken();
      const response = await TransformationService.selectColumnsByPattern(
        datasetId,
        pattern,
        token
      );

      setPreviewColumns(response.columns);

      if (response.columns.length === 0) {
        setError('No columns match this pattern');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview pattern');
      setPreviewColumns(null);
    } finally {
      setIsLoading(false);
    }
  }, [datasetId, buildPatternRequest]);

  // Apply pattern and pass results to parent
  const handleApply = useCallback(() => {
    if (previewColumns && previewColumns.length > 0) {
      onPatternApply(previewColumns);
    }
  }, [previewColumns, onPatternApply]);

  const dataTypes = [
    { type: 'numeric', icon: Hash, label: 'Numeric', color: 'text-blue-500' },
    { type: 'text', icon: Type, label: 'Text', color: 'text-green-500' },
    { type: 'datetime', icon: Calendar, label: 'DateTime', color: 'text-purple-500' },
    { type: 'boolean', icon: ToggleLeft, label: 'Boolean', color: 'text-orange-500' },
    { type: 'categorical', icon: Layers, label: 'Categorical', color: 'text-teal-500' }
  ];

  return (
    <div className={`bg-card rounded-lg border border-border p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-foreground mb-4">Select Columns by Pattern</h3>

      <Tabs value={activeTab} onValueChange={(v) => {
        setActiveTab(v as PatternType);
        setPreviewColumns(null);
        setError(null);
      }}>
        <TabsList className="w-full mb-4">
          <TabsTrigger value="data_type" className="flex-1">By Type</TabsTrigger>
          <TabsTrigger value="name_pattern" className="flex-1">By Name</TabsTrigger>
          <TabsTrigger value="quality_metric" className="flex-1">By Quality</TabsTrigger>
        </TabsList>

        {/* By Data Type */}
        <TabsContent value="data_type" className="space-y-3">
          <p className="text-xs text-muted-foreground">Select column types to include:</p>
          <div className="grid grid-cols-2 gap-2">
            {dataTypes.map(({ type, icon: Icon, label, color }) => (
              <div
                key={type}
                className={`
                  flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-all
                  ${selectedTypes.has(type)
                    ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-300 dark:border-blue-800'
                    : 'bg-card border-border hover:border-border'}
                `}
                onClick={() => handleTypeToggle(type)}
                role="checkbox"
                aria-checked={selectedTypes.has(type)}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleTypeToggle(type);
                  }
                }}
              >
                <Checkbox
                  checked={selectedTypes.has(type)}
                  onCheckedChange={() => handleTypeToggle(type)}
                  tabIndex={-1}
                />
                <Icon className={`w-4 h-4 ${color}`} />
                <span className="text-sm">{label}</span>
              </div>
            ))}
          </div>
        </TabsContent>

        {/* By Name Pattern */}
        <TabsContent value="name_pattern" className="space-y-3">
          <div>
            <Label htmlFor="name-pattern" className="text-xs text-muted-foreground">
              Regular expression or wildcard pattern:
            </Label>
            <div className="relative mt-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <Input
                id="name-pattern"
                type="text"
                placeholder="e.g., ^price_, .*_id$, amount"
                value={namePattern}
                onChange={(e) => {
                  setNamePattern(e.target.value);
                  setPreviewColumns(null);
                  setError(null);
                }}
                className="pl-10"
              />
            </div>
          </div>
          <div className="text-xs text-muted-foreground space-y-1">
            <p><strong>Examples:</strong></p>
            <p><code className="bg-muted px-1 rounded">^price_</code> - columns starting with &quot;price_&quot;</p>
            <p><code className="bg-muted px-1 rounded">_id$</code> - columns ending with &quot;_id&quot;</p>
            <p><code className="bg-muted px-1 rounded">date</code> - columns containing &quot;date&quot;</p>
          </div>
        </TabsContent>

        {/* By Quality Metric */}
        <TabsContent value="quality_metric" className="space-y-3">
          <div>
            <Label htmlFor="metric-select" className="text-xs text-muted-foreground">
              Quality metric:
            </Label>
            <Select value={selectedMetric} onValueChange={setSelectedMetric}>
              <SelectTrigger id="metric-select" className="mt-1">
                <SelectValue placeholder="Select metric" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="missing_values">Missing Values</SelectItem>
                <SelectItem value="unique_values">Unique Values</SelectItem>
                <SelectItem value="is_constant">Is Constant</SelectItem>
                <SelectItem value="is_high_cardinality">High Cardinality</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {(selectedMetric === 'missing_values' || selectedMetric === 'unique_values') && (
            <>
              <div>
                <Label htmlFor="operator-select" className="text-xs text-muted-foreground">
                  Condition:
                </Label>
                <Select value={metricOperator} onValueChange={setMetricOperator}>
                  <SelectTrigger id="operator-select" className="mt-1">
                    <SelectValue placeholder="Select condition" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gt">Greater than</SelectItem>
                    <SelectItem value="gte">Greater than or equal</SelectItem>
                    <SelectItem value="lt">Less than</SelectItem>
                    <SelectItem value="lte">Less than or equal</SelectItem>
                    <SelectItem value="eq">Equal to</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="threshold-slider" className="text-xs text-muted-foreground">
                  Threshold: {metricThreshold}
                </Label>
                <Slider
                  id="threshold-slider"
                  value={[metricThreshold]}
                  onValueChange={(values) => {
                    setMetricThreshold(values[0]);
                    setPreviewColumns(null);
                    setError(null);
                  }}
                  min={0}
                  max={selectedMetric === 'missing_values' ? 1000 : 10000}
                  step={1}
                  className="mt-2"
                />
              </div>
            </>
          )}

          {selectedMetric === 'is_constant' && (
            <p className="text-xs text-muted-foreground">
              Select columns where all values are the same (constant).
            </p>
          )}

          {selectedMetric === 'is_high_cardinality' && (
            <p className="text-xs text-muted-foreground">
              Select columns with many unique values relative to row count.
            </p>
          )}
        </TabsContent>
      </Tabs>

      {/* Error message */}
      {error && (
        <div className="mt-3 p-2 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg flex items-center gap-2 text-red-700 dark:text-red-300 text-xs">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Preview results */}
      {previewColumns && previewColumns.length > 0 && (
        <div className="mt-3 p-2 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 rounded-lg">
          <p className="text-xs text-blue-700 dark:text-blue-300 font-medium mb-1">
            {previewColumns.length} column{previewColumns.length !== 1 ? 's' : ''} matched:
          </p>
          <div className="flex flex-wrap gap-1">
            {previewColumns.slice(0, 10).map(col => (
              <span key={col.column_name} className="px-2 py-1 bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 rounded text-xs">
                {col.column_name}
              </span>
            ))}
            {previewColumns.length > 10 && (
              <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 rounded text-xs">
                +{previewColumns.length - 10} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-4 flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handlePreview}
          disabled={isLoading}
          className="flex-1"
        >
          {isLoading ? (
            <div className="animate-spin rounded-full h-4 w-4 border border-border border-t-blue-500 mr-2" />
          ) : null}
          Preview
        </Button>
        <Button
          size="sm"
          onClick={handleApply}
          disabled={!previewColumns || previewColumns.length === 0}
          className="flex-1"
        >
          Apply Selection
        </Button>
      </div>
    </div>
  );
}

export default SelectionPatternBuilder;
