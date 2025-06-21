'use client';

import React, { memo, useState } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Settings, X } from 'lucide-react';

export interface TransformationNodeData {
  type: string;
  label: string;
  parameters: Record<string, any>;
  onDelete?: (id: string) => void;
  onUpdate?: (id: string, data: TransformationNodeData) => void;
}

const TransformationNode = memo(({ id, data, selected }: NodeProps<TransformationNodeData>) => {
  const [showSettings, setShowSettings] = useState(false);
  const [parameters, setParameters] = useState(data.parameters || {});

  const handleParameterChange = (key: string, value: any) => {
    const newParams = { ...parameters, [key]: value };
    setParameters(newParams);
    if (data.onUpdate) {
      data.onUpdate(id, { ...data, parameters: newParams });
    }
  };

  const getParameterInputs = () => {
    switch (data.type) {
      case 'fill_missing':
      case 'fill_mean':
      case 'fill_median':
      case 'fill_mode':
        return (
          <div className="space-y-2">
            <label className="block">
              <span className="text-xs font-medium">Columns</span>
              <input
                type="text"
                placeholder="col1, col2 or leave empty for all"
                className="w-full mt-1 px-2 py-1 text-xs border rounded"
                value={parameters.columns || ''}
                onChange={(e) => handleParameterChange('columns', e.target.value)}
              />
            </label>
          </div>
        );
      case 'one_hot_encode':
      case 'label_encode':
        return (
          <div className="space-y-2">
            <label className="block">
              <span className="text-xs font-medium">Columns</span>
              <input
                type="text"
                placeholder="Enter column names"
                className="w-full mt-1 px-2 py-1 text-xs border rounded"
                value={parameters.columns || ''}
                onChange={(e) => handleParameterChange('columns', e.target.value)}
              />
            </label>
          </div>
        );
      case 'create_bins':
        return (
          <div className="space-y-2">
            <label className="block">
              <span className="text-xs font-medium">Column</span>
              <input
                type="text"
                placeholder="Column name"
                className="w-full mt-1 px-2 py-1 text-xs border rounded"
                value={parameters.column || ''}
                onChange={(e) => handleParameterChange('column', e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium">Number of Bins</span>
              <input
                type="number"
                min="2"
                max="20"
                className="w-full mt-1 px-2 py-1 text-xs border rounded"
                value={parameters.bins || 5}
                onChange={(e) => handleParameterChange('bins', parseInt(e.target.value))}
              />
            </label>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div
      className={`bg-white rounded-lg shadow-md border-2 min-w-[200px] ${
        selected ? 'border-blue-500' : 'border-gray-200'
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-gray-400"
      />
      
      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold">{data.label}</h3>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-1 hover:bg-gray-100 rounded"
            >
              <Settings className="w-4 h-4 text-gray-600" />
            </button>
            {data.onDelete && (
              <button
                onClick={() => data.onDelete(id)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="w-4 h-4 text-gray-600" />
              </button>
            )}
          </div>
        </div>
        
        <div className="text-xs text-gray-500">
          Type: {data.type}
        </div>

        {showSettings && (
          <div className="mt-3 pt-3 border-t">
            {getParameterInputs() || (
              <p className="text-xs text-gray-500">No parameters available</p>
            )}
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-gray-400"
      />
    </div>
  );
});

TransformationNode.displayName = 'TransformationNode';

export default TransformationNode;