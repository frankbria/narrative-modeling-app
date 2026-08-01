'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { List, type RowComponentProps } from 'react-window';
import { useDebounce } from '@/lib/hooks/useDebounce';
import { getAuthToken } from '@/lib/auth-helpers';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, CheckSquare, Square, Database, Calendar, Hash, Type } from 'lucide-react';
import { validateDatasetId } from '@/lib/utils/sanitize';

/**
 * Column data structure from the API
 */
interface Column {
  name: string;
  type: 'numeric' | 'categorical' | 'datetime' | 'text';
  unique_count: number;
  null_count: number;
  total_rows: number;
}

/**
 * Props for the ColumnSelector component
 */
interface ColumnSelectorProps {
  datasetId: string;
  selectedColumns: Set<string>;
  onSelectionChange: (columns: Set<string>) => void;
  className?: string;
}

/**
 * Get icon and color based on column data type
 */
function getColumnTypeIndicator(type: Column['type']) {
  switch (type) {
    case 'numeric':
      return {
        icon: Hash,
        color: 'text-blue-500',
        bgColor: 'bg-blue-50',
        label: 'Numeric'
      };
    case 'categorical':
      return {
        icon: Type,
        color: 'text-green-500',
        bgColor: 'bg-green-50',
        label: 'Categorical'
      };
    case 'datetime':
      return {
        icon: Calendar,
        color: 'text-purple-500',
        bgColor: 'bg-purple-50',
        label: 'DateTime'
      };
    case 'text':
      return {
        icon: Database,
        color: 'text-orange-500',
        bgColor: 'bg-orange-50',
        label: 'Text'
      };
    default:
      return {
        icon: Database,
        color: 'text-gray-500',
        bgColor: 'bg-gray-50',
        label: 'Unknown'
      };
  }
}

/**
 * Calculate missing values percentage
 */
function getMissingPercentage(nullCount: number, totalRows: number): number {
  if (totalRows === 0) return 0;
  return Math.round((nullCount / totalRows) * 100);
}

/** Row height in px, shared by the list and its row component. */
const ITEM_HEIGHT = 80;

/**
 * Per-row data handed to ColumnListItem through react-window's `rowProps`.
 */
interface ColumnRowProps {
  columns: Column[];
  selectedColumns: Set<string>;
  focusedIndex: number;
  onToggleColumn: (columnName: string) => void;
  onListKeyDown: (e: React.KeyboardEvent) => void;
}

/**
 * Render a single column item in the virtualized list.
 *
 * Defined at module scope rather than inside ColumnSelector: react-window v2
 * takes the row renderer as a `rowComponent` prop, and a component created
 * during render gets a new identity every render, remounting every visible row
 * (react-hooks/static-components, an error since #373). Everything it used to
 * close over now arrives via `rowProps`.
 *
 * Not wrapped in memo(): v2 does `useMemo(() => memo(rowComponent, cmp), [rowComponent])`
 * internally, so the library already memoizes rows — and a MemoExoticComponent is
 * not structurally assignable to the plain function type `rowComponent` requires.
 */
function ColumnListItem({
  index,
  style,
  ariaAttributes,
  columns,
  selectedColumns,
  focusedIndex,
  onToggleColumn,
  onListKeyDown,
}: RowComponentProps<ColumnRowProps>) {
  const column = columns[index];
  if (!column) return null;

  const isSelected = selectedColumns.has(column.name);
  const isFocused = index === focusedIndex;
  const typeIndicator = getColumnTypeIndicator(column.type);
  const TypeIcon = typeIndicator.icon;
  const missingPercent = getMissingPercentage(column.null_count, column.total_rows);

  return (
    <div
      style={style}
      className="px-2"
      {...ariaAttributes}
      role="option"
      aria-selected={isSelected}
      tabIndex={isFocused ? 0 : -1}
      onKeyDown={onListKeyDown}
    >
      <div
        className={`
          p-3 flex items-start gap-3 rounded-lg border transition-all
          ${isFocused ? 'ring-2 ring-blue-500 border-blue-400' : 'border-gray-200 hover:border-gray-300'}
          ${isSelected ? 'bg-blue-50 border-blue-300' : 'bg-white hover:bg-gray-50'}
          cursor-pointer
        `}
        onClick={() => onToggleColumn(column.name)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggleColumn(column.name);
          }
        }}
      >
        {/* Checkbox */}
        <div className="pt-0.5 flex-shrink-0">
          <Checkbox
            checked={isSelected}
            onCheckedChange={() => onToggleColumn(column.name)}
            aria-label={`Select ${column.name}`}
            tabIndex={-1}
          />
        </div>

        {/* Column info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <TypeIcon
              className={`w-4 h-4 flex-shrink-0 ${typeIndicator.color}`}
              aria-hidden="true"
            />
            <span className="font-medium text-sm truncate">{column.name}</span>
          </div>

          {/* Column statistics */}
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-600">
            <span
              className={`px-2 py-1 rounded-full ${typeIndicator.bgColor} ${typeIndicator.color}`}
            >
              {typeIndicator.label}
            </span>
            <span className="px-2 py-1 bg-gray-100 rounded-full">
              {column.unique_count.toLocaleString()} unique
            </span>
            {missingPercent > 0 && (
              <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full">
                {missingPercent}% missing
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * ColumnSelector Component
 *
 * A searchable multi-select column list with keyboard navigation,
 * column statistics display, and virtualization for large datasets.
 *
 * Features:
 * - Search/filter with 300ms debounce
 * - Checkbox selection for multiple columns
 * - Visual indicators for column data types
 * - Select All / Deselect All actions
 * - Column statistics (missing values %, unique count)
 * - Virtualized list for 1000+ columns performance
 * - Keyboard navigation (Arrow keys, Space, Escape)
 * - Accessibility-first design with ARIA labels
 */
export function ColumnSelector({
  datasetId,
  selectedColumns,
  onSelectionChange,
  className = ''
}: ColumnSelectorProps) {
  // State management
  const [columns, setColumns] = useState<Column[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  // Debounce search term
  const debouncedSearchTerm = useDebounce(searchTerm, 300);

  // Refs for keyboard navigation
  const searchInputRef = useRef<HTMLInputElement>(null);

  /**
   * Fetch columns from the dataset preview endpoint with retry logic
   */
  useEffect(() => {
    const fetchColumns = async (retryCount = 0) => {
      setIsLoading(true);
      setError(null);

      try {
        // Validate datasetId to prevent path traversal
        const validatedId = validateDatasetId(datasetId);
        if (!validatedId) {
          throw new Error('Invalid dataset ID format');
        }

        const token = await getAuthToken();
        if (!token) {
          throw new Error('Authentication failed');
        }

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        const response = await fetch(`${apiUrl}/data/${validatedId}/preview`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch columns: ${response.statusText}`);
        }

        const data = await response.json();

        // Extract column information from the preview
        // Assuming the API returns { columns: Column[], data: any[] }
        if (data.columns && Array.isArray(data.columns)) {
          setColumns(data.columns);
          setIsLoading(false);
        } else {
          throw new Error('Invalid data structure from API');
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to fetch columns';

        // Retry logic: retry up to 3 times with exponential backoff (disabled in tests)
        const shouldRetry = retryCount < 3 &&
                           errorMessage !== 'Invalid dataset ID format' &&
                           errorMessage !== 'Authentication failed' &&
                           process.env.NODE_ENV !== 'test';

        if (shouldRetry) {
          const retryDelay = Math.pow(2, retryCount) * 1000; // 1s, 2s, 4s
          console.warn(`Retrying column fetch (attempt ${retryCount + 1}/3) after ${retryDelay}ms`);
          setTimeout(() => fetchColumns(retryCount + 1), retryDelay);
          // Don't set loading to false or set error during retry
          return;
        }

        // Final failure or non-retriable error
        setError(errorMessage);
        setIsLoading(false);
        console.error('Error fetching columns:', err);
      } finally {
        // Only set loading to false if we're not retrying
        // If we returned early for retry, finally block doesn't set loading to false
      }
    };

    if (datasetId) {
      fetchColumns();
    }
  }, [datasetId]);

  /**
   * Filter columns based on search term
   */
  const filteredColumns = useMemo(() => {
    if (!debouncedSearchTerm) return columns;

    const term = debouncedSearchTerm.toLowerCase();
    return columns.filter(
      col =>
        col.name.toLowerCase().includes(term) ||
        col.type.toLowerCase().includes(term)
    );
  }, [columns, debouncedSearchTerm]);

  /**
   * Check if all visible columns are selected
   */
  const areAllSelected = useMemo(() => {
    if (filteredColumns.length === 0) return false;
    return filteredColumns.every(col => selectedColumns.has(col.name));
  }, [filteredColumns, selectedColumns]);

  /**
   * Handle individual column selection
   */
  const handleToggleColumn = useCallback((columnName: string) => {
    const newSelection = new Set(selectedColumns);
    if (newSelection.has(columnName)) {
      newSelection.delete(columnName);
    } else {
      newSelection.add(columnName);
    }
    onSelectionChange(newSelection);
  }, [selectedColumns, onSelectionChange]);

  /**
   * Select all visible columns
   */
  const handleSelectAll = useCallback(() => {
    const newSelection = new Set(selectedColumns);
    filteredColumns.forEach(col => {
      newSelection.add(col.name);
    });
    onSelectionChange(newSelection);
  }, [selectedColumns, filteredColumns, onSelectionChange]);

  /**
   * Deselect all visible columns
   */
  const handleDeselectAll = useCallback(() => {
    const newSelection = new Set(selectedColumns);
    filteredColumns.forEach(col => {
      newSelection.delete(col.name);
    });
    onSelectionChange(newSelection);
  }, [selectedColumns, filteredColumns, onSelectionChange]);

  /**
   * Handle keyboard navigation in the column list
   */
  const handleListKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (filteredColumns.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex(prev =>
          prev < filteredColumns.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex(prev => (prev > 0 ? prev - 1 : 0));
        break;
      case ' ':
        e.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < filteredColumns.length) {
          handleToggleColumn(filteredColumns[focusedIndex].name);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setSearchTerm('');
        setFocusedIndex(-1);
        searchInputRef.current?.focus();
        break;
      default:
        break;
    }
  }, [filteredColumns, focusedIndex, handleToggleColumn]);


  return (
    <div className={`flex flex-col h-full bg-white rounded-lg border border-gray-200 ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Select Columns</h2>

        {/* Search input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 pointer-events-none" />
          <Input
            ref={searchInputRef}
            type="text"
            placeholder="Search by name or type..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setFocusedIndex(0);
            }}
            className="pl-10 pr-4 py-2"
            aria-label="Search columns"
            aria-describedby="search-hint"
            aria-expanded={filteredColumns.length > 0}
          />
          <span id="search-hint" className="sr-only">
            Type to filter columns, use arrow keys to navigate, Space to select/deselect, Escape to clear
          </span>
        </div>
      </div>

      {/* Column count info */}
      <div className="px-4 pt-3 pb-2 bg-gray-50 border-b border-gray-200 text-sm text-gray-600 flex justify-between items-center">
        <span>
          {selectedColumns.size} of {columns.length} selected
          {debouncedSearchTerm && ` (${filteredColumns.length} visible)`}
        </span>
      </div>

      {/* Select All / Deselect All buttons */}
      <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handleSelectAll}
          disabled={areAllSelected || filteredColumns.length === 0}
          className="flex-1 text-xs"
          aria-label={`Select all ${filteredColumns.length} columns`}
        >
          <CheckSquare className="w-3 h-3 mr-1" />
          Select All
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleDeselectAll}
          disabled={selectedColumns.size === 0}
          className="flex-1 text-xs"
          aria-label="Deselect all columns"
        >
          <Square className="w-3 h-3 mr-1" />
          Deselect All
        </Button>
      </div>

      {/* Column list container */}
      <div className="flex-1 min-h-0" role="listbox" aria-multiselectable="true">
        {isLoading ? (
          <div className="p-4 text-center text-gray-500">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border border-gray-300 border-t-blue-500 mb-2" />
            <p className="text-sm">Loading columns...</p>
          </div>
        ) : error ? (
          <div className="p-4 text-center text-red-600">
            <p className="text-sm font-medium">Failed to load columns</p>
            <p className="text-xs mt-1">{error}</p>
          </div>
        ) : filteredColumns.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <p className="text-sm">
              {debouncedSearchTerm ? 'No columns match your search' : 'No columns available'}
            </p>
          </div>
        ) : (
          <List
            style={{ height: 400 }}
            rowCount={filteredColumns.length}
            rowHeight={ITEM_HEIGHT}
            rowComponent={ColumnListItem}
            rowProps={{
              columns: filteredColumns,
              selectedColumns,
              focusedIndex,
              onToggleColumn: handleToggleColumn,
              onListKeyDown: handleListKeyDown,
            }}
          />
        )}
      </div>

      {/* Footer info */}
      <div className="px-4 py-3 border-t border-gray-200 bg-gray-50 text-xs text-gray-500">
        <p>
          Use arrow keys to navigate, Space to select, Escape to clear search
        </p>
      </div>
    </div>
  );
}

export default ColumnSelector;
