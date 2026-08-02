'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Search } from 'lucide-react';

interface Column {
  name: string;
  type: string;
  nullCount?: number;
  uniqueCount?: number;
}

interface ColumnPaletteProps {
  columns: Column[];
}

const typeColors: Record<string, string> = {
  numeric: 'bg-blue-100 text-blue-800 border-blue-200',
  text: 'bg-green-100 text-green-800 border-green-200',
  boolean: 'bg-purple-100 text-purple-800 border-purple-200',
  datetime: 'bg-orange-100 text-orange-800 border-orange-200',
  categorical: 'bg-pink-100 text-pink-800 border-pink-200',
};

export default function ColumnPalette({ columns }: ColumnPaletteProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  // Group columns by type
  const groupedColumns = columns.reduce<Record<string, Column[]>>((acc, col) => {
    const type = col.type || 'other';
    if (!acc[type]) {
      acc[type] = [];
    }
    acc[type].push(col);
    return acc;
  }, {});

  // Filter columns by search term
  const filteredColumns = searchTerm
    ? columns.filter((col) =>
        col.name.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : null;

  const handleDragStart = (e: React.DragEvent, column: Column) => {
    e.dataTransfer.setData('nodeType', 'column');
    e.dataTransfer.setData('nodeValue', column.name);
    e.dataTransfer.setData('nodeLabel', column.name);
    e.dataTransfer.effectAllowed = 'move';
  };

  const renderColumn = (column: Column) => (
    <div
      key={column.name}
      className={`p-2 rounded cursor-move border hover:opacity-80 transition-opacity ${
        typeColors[column.type] || 'bg-muted text-foreground border-border'
      }`}
      draggable
      onDragStart={(e) => handleDragStart(e, column)}
    >
      <div className="text-sm font-medium truncate">{column.name}</div>
      <div className="text-xs opacity-70 flex items-center gap-2">
        <span>{column.type}</span>
        {column.nullCount !== undefined && column.nullCount > 0 && (
          <span className="text-amber-600">({column.nullCount} nulls)</span>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full text-left font-medium text-foreground hover:text-foreground"
      >
        {isExpanded ? (
          <ChevronDown className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
        <span>Columns ({columns.length})</span>
      </button>

      {isExpanded && (
        <div className="space-y-3">
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search columns..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-sm border rounded-lg"
            />
          </div>

          {/* Columns */}
          {filteredColumns ? (
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {filteredColumns.length > 0 ? (
                filteredColumns.map(renderColumn)
              ) : (
                <p className="text-sm text-muted-foreground text-center py-2">
                  No columns match your search
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {Object.entries(groupedColumns).map(([type, cols]) => (
                <div key={type}>
                  <h4 className="text-xs uppercase text-muted-foreground font-medium mb-1.5">
                    {type} ({cols.length})
                  </h4>
                  <div className="space-y-1.5">
                    {cols.map(renderColumn)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
