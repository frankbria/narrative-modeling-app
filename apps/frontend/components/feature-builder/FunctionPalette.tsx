'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface Function {
  type: string;
  label: string;
  description: string;
}

const functions: Record<string, Function[]> = {
  mathematical: [
    { type: 'abs', label: 'abs', description: 'Absolute value' },
    { type: 'log', label: 'log', description: 'Natural logarithm' },
    { type: 'log10', label: 'log10', description: 'Base-10 log' },
    { type: 'sqrt', label: 'sqrt', description: 'Square root' },
    { type: 'exp', label: 'exp', description: 'Exponential' },
    { type: 'round', label: 'round', description: 'Round to decimals' },
    { type: 'ceil', label: 'ceil', description: 'Round up' },
    { type: 'floor', label: 'floor', description: 'Round down' },
  ],
  statistical: [
    { type: 'mean', label: 'mean', description: 'Mean value' },
    { type: 'median', label: 'median', description: 'Median value' },
    { type: 'std', label: 'std', description: 'Standard deviation' },
    { type: 'min', label: 'min', description: 'Minimum' },
    { type: 'max', label: 'max', description: 'Maximum' },
    { type: 'sum', label: 'sum', description: 'Sum' },
  ],
  string: [
    { type: 'upper', label: 'upper', description: 'To uppercase' },
    { type: 'lower', label: 'lower', description: 'To lowercase' },
    { type: 'trim', label: 'trim', description: 'Trim whitespace' },
    { type: 'length', label: 'length', description: 'String length' },
  ],
  date: [
    { type: 'year', label: 'year', description: 'Extract year' },
    { type: 'month', label: 'month', description: 'Extract month' },
    { type: 'day', label: 'day', description: 'Extract day' },
    { type: 'hour', label: 'hour', description: 'Extract hour' },
    { type: 'weekday', label: 'weekday', description: 'Day of week' },
  ],
  utility: [
    { type: 'to_numeric', label: 'toNum', description: 'Convert to number' },
    { type: 'to_string', label: 'toStr', description: 'Convert to string' },
    { type: 'fill_null', label: 'fillNull', description: 'Replace nulls' },
    { type: 'is_null', label: 'isNull', description: 'Check if null' },
  ],
};

/**
 * FunctionPalette component renders a searchable, categorized palette of functions
 * for the Visual Feature Builder.
 *
 * Functions are organized into categories (mathematical, statistical, string, date, utility)
 * with collapsible sections. Each function can be dragged onto the feature builder canvas.
 *
 * @returns A React element displaying the function palette with category toggles and drag-and-drop support
 *
 * @remarks
 * - Uses internal state to manage category expansion and main section visibility
 * - Mathematical category is expanded by default
 * - Each function item is draggable and sets dataTransfer data for nodeType, nodeValue, and nodeLabel
 * - Functions have tooltips showing their descriptions
 */
export default function FunctionPalette() {
  const [isExpanded, setIsExpanded] = useState(true);
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    mathematical: true,
    statistical: false,
    string: false,
    date: false,
    utility: false,
  });

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  };

  const handleDragStart = (e: React.DragEvent, func: Function) => {
    e.dataTransfer.setData('nodeType', 'function');
    e.dataTransfer.setData('nodeValue', func.type);
    e.dataTransfer.setData('nodeLabel', func.label);
    e.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="space-y-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full text-left font-medium text-gray-700 hover:text-gray-900"
      >
        {isExpanded ? (
          <ChevronDown className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
        <span>Functions</span>
      </button>

      {isExpanded && (
        <div className="space-y-2">
          {Object.entries(functions).map(([category, funcs]) => (
            <div key={category}>
              <button
                onClick={() => toggleCategory(category)}
                className="flex items-center gap-1 text-xs uppercase text-gray-500 font-medium hover:text-gray-700 mb-1"
              >
                {expandedCategories[category] ? (
                  <ChevronDown className="w-3 h-3" />
                ) : (
                  <ChevronRight className="w-3 h-3" />
                )}
                {category}
              </button>

              {expandedCategories[category] && (
                <div className="grid grid-cols-2 gap-1.5">
                  {funcs.map((func) => (
                    <div
                      key={func.type}
                      className="p-2 bg-orange-100 rounded cursor-move border border-orange-200 hover:bg-orange-200 transition-colors"
                      draggable
                      onDragStart={(e) => handleDragStart(e, func)}
                      title={func.description}
                    >
                      <span className="text-sm font-mono text-orange-800">{func.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
