'use client';

import { useState, useMemo, useCallback, useRef, memo } from 'react';
import { FixedSizeList as List } from 'react-window';
import { useDebounce } from '@/lib/hooks/useDebounce';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, CheckSquare, Square, Database, Calendar, Hash, Type, AlertTriangle } from 'lucide-react';
import type { ColumnMetadata } from '@/lib/services/transformation';

/**
 * Props for the BulkColumnSelector component
 */
interface BulkColumnSelectorProps {
  columns: ColumnMetadata[];
  selectedColumns: Set<string>;
  onSelectionChange: (columns: Set<string>) => void;
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}

/**
 * Get icon and color based on column field type
 */
function getColumnTypeIndicator(fieldType: string) {
  switch (fieldType) {
    case 'numeric':
      return {
        icon: Hash,
        color: 'text-blue-500',
        bgColor: 'bg-blue-50',
        label: 'Numeric'
      };
    case 'categorical':
    case 'text':
      return {
        icon: Type,
        color: 'text-green-500',
        bgColor: 'bg-green-50',
        label: fieldType.charAt(0).toUpperCase() + fieldType.slice(1)
      };
    case 'datetime':
      return {
        icon: Calendar,
        color: 'text-purple-500',
        bgColor: 'bg-purple-50',
        label: 'DateTime'
      };
    case 'boolean':
      return {
        icon: CheckSquare,
        color: 'text-orange-500',
        bgColor: 'bg-orange-50',
        label: 'Boolean'
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
 * BulkColumnSelector Component
 *
 * Multi-select column list for bulk transformation operations with:
 * - Search/filter with debounce
 * - Checkbox selection with Shift+click for range selection
 * - Ctrl+click for toggle selection
 * - Select All / Deselect All actions
 * - Column metadata display (type, missing values, unique values)
 * - Virtualized list for performance with many columns
 */
export function BulkColumnSelector({
  columns,
  selectedColumns,
  onSelectionChange,
  isLoading = false,
  error = null,
  className = ''
}: BulkColumnSelectorProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(null);

  const debouncedSearchTerm = useDebounce(searchTerm, 300);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<List<unknown>>(null);

  // Filter columns based on search term
  const filteredColumns = useMemo(() => {
    if (!debouncedSearchTerm) return columns;

    const term = debouncedSearchTerm.toLowerCase();
    return columns.filter(
      col =>
        col.column_name.toLowerCase().includes(term) ||
        col.field_type.toLowerCase().includes(term)
    );
  }, [columns, debouncedSearchTerm]);

  // Check if all visible columns are selected
  const areAllSelected = useMemo(() => {
    if (filteredColumns.length === 0) return false;
    return filteredColumns.every(col => selectedColumns.has(col.column_name));
  }, [filteredColumns, selectedColumns]);

  // Handle individual column selection
  const handleToggleColumn = useCallback((columnName: string, index: number, event?: React.MouseEvent) => {
    const newSelection = new Set(selectedColumns);

    if (event?.shiftKey && lastSelectedIndex !== null) {
      // Shift+click: select range
      const start = Math.min(lastSelectedIndex, index);
      const end = Math.max(lastSelectedIndex, index);
      for (let i = start; i <= end; i++) {
        newSelection.add(filteredColumns[i].column_name);
      }
    } else if (event?.ctrlKey || event?.metaKey) {
      // Ctrl/Cmd+click: toggle single
      if (newSelection.has(columnName)) {
        newSelection.delete(columnName);
      } else {
        newSelection.add(columnName);
      }
    } else {
      // Normal click: toggle single
      if (newSelection.has(columnName)) {
        newSelection.delete(columnName);
      } else {
        newSelection.add(columnName);
      }
    }

    setLastSelectedIndex(index);
    onSelectionChange(newSelection);
  }, [selectedColumns, lastSelectedIndex, filteredColumns, onSelectionChange]);

  // Select all visible columns
  const handleSelectAll = useCallback(() => {
    const newSelection = new Set(selectedColumns);
    filteredColumns.forEach(col => {
      newSelection.add(col.column_name);
    });
    onSelectionChange(newSelection);
  }, [selectedColumns, filteredColumns, onSelectionChange]);

  // Deselect all visible columns
  const handleDeselectAll = useCallback(() => {
    const newSelection = new Set(selectedColumns);
    filteredColumns.forEach(col => {
      newSelection.delete(col.column_name);
    });
    onSelectionChange(newSelection);
  }, [selectedColumns, filteredColumns, onSelectionChange]);

  // Handle keyboard navigation
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
          handleToggleColumn(filteredColumns[focusedIndex].column_name, focusedIndex);
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

  // Render a single column item in the virtualized list
  const ColumnListItem = memo(({ index, style }: { index: number; style: React.CSSProperties }) => {
    const column = filteredColumns[index];
    if (!column) return null;

    const isSelected = selectedColumns.has(column.column_name);
    const isFocused = index === focusedIndex;
    const typeIndicator = getColumnTypeIndicator(column.field_type);
    const TypeIcon = typeIndicator.icon;

    return (
      <div
        style={style}
        className="px-2"
        role="option"
        aria-selected={isSelected}
        tabIndex={isFocused ? 0 : -1}
        onKeyDown={handleListKeyDown}
      >
        <div
          className={`
            p-3 flex items-start gap-3 rounded-lg border transition-all
            ${isFocused ? 'ring-2 ring-blue-500 border-blue-400' : 'border-gray-200 hover:border-gray-300'}
            ${isSelected ? 'bg-blue-50 border-blue-300' : 'bg-white hover:bg-gray-50'}
            cursor-pointer
          `}
          onClick={(e) => handleToggleColumn(column.column_name, index, e)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              handleToggleColumn(column.column_name, index);
            }
          }}
        >
          {/* Checkbox */}
          <div className="pt-0.5 flex-shrink-0">
            <Checkbox
              checked={isSelected}
              onCheckedChange={() => handleToggleColumn(column.column_name, index)}
              aria-label={`Select ${column.column_name}`}
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
              <span className="font-medium text-sm truncate">{column.column_name}</span>
            </div>

            {/* Column statistics */}
            <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-600">
              <span
                className={`px-2 py-1 rounded-full ${typeIndicator.bgColor} ${typeIndicator.color}`}
              >
                {typeIndicator.label}
              </span>
              <span className="px-2 py-1 bg-gray-100 rounded-full">
                {column.unique_values.toLocaleString()} unique
              </span>
              {column.missing_values > 0 && (
                <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  {column.missing_values.toLocaleString()} missing
                </span>
              )}
              {column.is_constant && (
                <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full">
                  Constant
                </span>
              )}
              {column.is_high_cardinality && (
                <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded-full">
                  High Cardinality
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  });

  ColumnListItem.displayName = 'ColumnListItem';

  const ITEM_HEIGHT = 88;

  return (
    <div className={`flex flex-col h-full bg-white rounded-lg border border-gray-200 ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Select Columns for Bulk Operation</h2>

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
          />
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
            ref={listRef}
            height={400}
            itemCount={filteredColumns.length}
            itemSize={ITEM_HEIGHT}
            width="100%"
            role="presentation"
          >
            {ColumnListItem}
          </List>
        )}
      </div>

      {/* Footer info */}
      <div className="px-4 py-3 border-t border-gray-200 bg-gray-50 text-xs text-gray-500">
        <p>
          Use Shift+click for range selection, Ctrl+click to toggle individual columns
        </p>
      </div>
    </div>
  );
}

export default BulkColumnSelector;
