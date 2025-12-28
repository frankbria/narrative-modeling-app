'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface Operation {
  type: string;
  symbol: string;
  label: string;
  description: string;
}

const operations: Record<string, Operation[]> = {
  arithmetic: [
    { type: 'add', symbol: '+', label: 'Add', description: 'Add two values' },
    { type: 'subtract', symbol: '-', label: 'Subtract', description: 'Subtract values' },
    { type: 'multiply', symbol: '*', label: 'Multiply', description: 'Multiply values' },
    { type: 'divide', symbol: '/', label: 'Divide', description: 'Divide values' },
    { type: 'modulo', symbol: '%', label: 'Modulo', description: 'Remainder' },
    { type: 'power', symbol: '^', label: 'Power', description: 'Raise to power' },
  ],
  comparison: [
    { type: 'equal', symbol: '==', label: 'Equal', description: 'Check equality' },
    { type: 'not_equal', symbol: '!=', label: 'Not Equal', description: 'Check inequality' },
    { type: 'greater_than', symbol: '>', label: 'Greater', description: 'Greater than' },
    { type: 'less_than', symbol: '<', label: 'Less', description: 'Less than' },
    { type: 'greater_than_or_equal', symbol: '>=', label: 'Greater/Equal', description: 'Greater or equal' },
    { type: 'less_than_or_equal', symbol: '<=', label: 'Less/Equal', description: 'Less or equal' },
  ],
  logical: [
    { type: 'and', symbol: 'AND', label: 'And', description: 'Logical AND' },
    { type: 'or', symbol: 'OR', label: 'Or', description: 'Logical OR' },
    { type: 'not', symbol: 'NOT', label: 'Not', description: 'Logical NOT' },
  ],
};

export default function OperationPalette() {
  const [isExpanded, setIsExpanded] = useState(true);
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    arithmetic: true,
    comparison: false,
    logical: false,
  });

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  };

  const handleDragStart = (e: React.DragEvent, operation: Operation) => {
    e.dataTransfer.setData('nodeType', 'operation');
    e.dataTransfer.setData('nodeValue', operation.type);
    e.dataTransfer.setData('nodeLabel', operation.symbol);
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
        <span>Operations</span>
      </button>

      {isExpanded && (
        <div className="space-y-2">
          {Object.entries(operations).map(([category, ops]) => (
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
                <div className="grid grid-cols-3 gap-1.5">
                  {ops.map((op) => (
                    <div
                      key={op.type}
                      className="p-2 bg-green-100 rounded cursor-move border border-green-200 hover:bg-green-200 transition-colors text-center"
                      draggable
                      onDragStart={(e) => handleDragStart(e, op)}
                      title={op.description}
                    >
                      <span className="font-bold text-green-800">{op.symbol}</span>
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
