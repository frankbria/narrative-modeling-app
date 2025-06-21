'use client';

import React, { useState } from 'react';
import { Search, ChevronDown, ChevronRight } from 'lucide-react';

interface TransformationCategory {
  name: string;
  icon: string;
  transformations: {
    type: string;
    label: string;
    description: string;
  }[];
}

const categories: TransformationCategory[] = [
  {
    name: 'Data Cleaning',
    icon: '🧹',
    transformations: [
      {
        type: 'remove_duplicates',
        label: 'Remove Duplicates',
        description: 'Remove duplicate rows from dataset',
      },
      {
        type: 'trim_whitespace',
        label: 'Trim Whitespace',
        description: 'Remove leading/trailing spaces',
      },
      {
        type: 'fix_casing',
        label: 'Fix Casing',
        description: 'Standardize text casing',
      },
      {
        type: 'remove_special_chars',
        label: 'Remove Special Characters',
        description: 'Clean special characters from text',
      },
    ],
  },
  {
    name: 'Missing Values',
    icon: '🔍',
    transformations: [
      {
        type: 'drop_missing',
        label: 'Drop Missing',
        description: 'Remove rows with missing values',
      },
      {
        type: 'fill_forward',
        label: 'Forward Fill',
        description: 'Fill with previous value',
      },
      {
        type: 'fill_backward',
        label: 'Backward Fill',
        description: 'Fill with next value',
      },
      {
        type: 'fill_mean',
        label: 'Fill with Mean',
        description: 'Replace with column mean',
      },
      {
        type: 'fill_median',
        label: 'Fill with Median',
        description: 'Replace with column median',
      },
      {
        type: 'fill_mode',
        label: 'Fill with Mode',
        description: 'Replace with most common value',
      },
    ],
  },
  {
    name: 'Type Conversion',
    icon: '🔄',
    transformations: [
      {
        type: 'to_numeric',
        label: 'To Numeric',
        description: 'Convert to number type',
      },
      {
        type: 'to_string',
        label: 'To String',
        description: 'Convert to text type',
      },
      {
        type: 'to_datetime',
        label: 'To DateTime',
        description: 'Parse as date/time',
      },
      {
        type: 'to_boolean',
        label: 'To Boolean',
        description: 'Convert to true/false',
      },
    ],
  },
  {
    name: 'Feature Engineering',
    icon: '⚙️',
    transformations: [
      {
        type: 'one_hot_encode',
        label: 'One-Hot Encode',
        description: 'Create dummy variables',
      },
      {
        type: 'label_encode',
        label: 'Label Encode',
        description: 'Convert categories to numbers',
      },
      {
        type: 'extract_date_parts',
        label: 'Extract Date Parts',
        description: 'Get year, month, day, etc.',
      },
      {
        type: 'create_bins',
        label: 'Create Bins',
        description: 'Discretize continuous values',
      },
    ],
  },
];

export default function TransformationSidebar() {
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(categories.map((c) => c.name))
  );

  const toggleCategory = (categoryName: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(categoryName)) {
      newExpanded.delete(categoryName);
    } else {
      newExpanded.add(categoryName);
    }
    setExpandedCategories(newExpanded);
  };

  const filteredCategories = categories
    .map((category) => ({
      ...category,
      transformations: category.transformations.filter(
        (t) =>
          t.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
          t.description.toLowerCase().includes(searchTerm.toLowerCase())
      ),
    }))
    .filter((category) => category.transformations.length > 0);

  const onDragStart = (event: React.DragEvent, transformationType: string) => {
    event.dataTransfer.setData('transformationType', transformationType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="w-80 bg-gray-50 border-r flex flex-col">
      <div className="p-4 border-b bg-white">
        <h2 className="text-lg font-semibold mb-3">Transformations</h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search transformations..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {filteredCategories.map((category) => (
          <div key={category.name} className="border-b">
            <button
              onClick={() => toggleCategory(category.name)}
              className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="text-xl">{category.icon}</span>
                <span className="font-medium">{category.name}</span>
              </div>
              {expandedCategories.has(category.name) ? (
                <ChevronDown className="w-4 h-4 text-gray-600" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-600" />
              )}
            </button>

            {expandedCategories.has(category.name) && (
              <div className="px-2 py-2">
                {category.transformations.map((transformation) => (
                  <div
                    key={transformation.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, transformation.type)}
                    className="p-3 mb-2 bg-white rounded-lg border border-gray-200 cursor-move hover:border-blue-400 hover:shadow-sm transition-all"
                  >
                    <div className="font-medium text-sm">{transformation.label}</div>
                    <div className="text-xs text-gray-600 mt-1">
                      {transformation.description}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="p-4 bg-white border-t">
        <p className="text-xs text-gray-500 text-center">
          Drag transformations to the canvas
        </p>
      </div>
    </div>
  );
}