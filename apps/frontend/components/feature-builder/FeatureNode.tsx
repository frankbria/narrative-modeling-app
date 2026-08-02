'use client';

import React, { memo, useState } from 'react';
import { Handle, Position, Node, NodeProps } from '@xyflow/react';
import { Settings, X, AlertCircle } from 'lucide-react';

export type FeatureNodeData = {
  nodeType: 'column' | 'operation' | 'function' | 'constant' | 'conditional';
  value: string | number | boolean | null;
  label: string;
  parameters: Record<string, unknown>;
  onDelete?: (id: string) => void;
  onUpdate?: (id: string, data: Partial<FeatureNodeData>) => void;
  error?: string;
};

export type FeatureNode = Node<
  FeatureNodeData,
  'column' | 'operation' | 'function' | 'constant' | 'conditional'
>;

const nodeColors: Record<string, { bg: string; border: string; text: string }> = {
  column: { bg: 'bg-blue-50 dark:bg-blue-950/40', border: 'border-blue-300 dark:border-blue-800', text: 'text-blue-800 dark:text-blue-200' },
  operation: { bg: 'bg-green-50 dark:bg-green-950/40', border: 'border-green-300 dark:border-green-800', text: 'text-green-800 dark:text-green-200' },
  function: { bg: 'bg-orange-50 dark:bg-orange-950/40', border: 'border-orange-300 dark:border-orange-800', text: 'text-orange-800 dark:text-orange-200' },
  constant: { bg: 'bg-purple-50 dark:bg-purple-950/40', border: 'border-purple-300 dark:border-purple-800', text: 'text-purple-800 dark:text-purple-200' },
  conditional: { bg: 'bg-yellow-50 dark:bg-yellow-950/40', border: 'border-yellow-300 dark:border-yellow-800', text: 'text-yellow-800 dark:text-yellow-200' },
};

const FeatureNode = memo(({ id, data, selected }: NodeProps<FeatureNode>) => {
  const [showSettings, setShowSettings] = useState(false);
  const [localValue, setLocalValue] = useState(data.value);

  const colors = nodeColors[data.nodeType] || nodeColors.constant;

  const handleValueChange = (newValue: string | number) => {
    setLocalValue(newValue);
    if (data.onUpdate) {
      data.onUpdate(id, { value: newValue });
    }
  };

  const handleParameterChange = (key: string, value: unknown) => {
    if (data.onUpdate) {
      data.onUpdate(id, {
        parameters: { ...data.parameters, [key]: value },
      });
    }
  };

  const getNodeContent = () => {
    switch (data.nodeType) {
      case 'column':
        return (
          <div className={`font-mono text-sm ${colors.text}`}>
            [{data.value}]
          </div>
        );
      case 'operation':
        return (
          <div className="font-bold text-lg">
            {getOperationSymbol(String(data.value))}
          </div>
        );
      case 'function':
        return (
          <div className={`font-mono text-sm ${colors.text}`}>
            {data.value}()
          </div>
        );
      case 'constant':
        return showSettings ? (
          <input
            type="number"
            value={localValue as number}
            onChange={(e) => handleValueChange(parseFloat(e.target.value) || 0)}
            className="w-20 px-2 py-1 text-sm border rounded text-center"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <div className="font-mono text-sm">{localValue}</div>
        );
      case 'conditional':
        return (
          <div className="font-mono text-sm">IF-THEN-ELSE</div>
        );
      default:
        return <div>{data.label}</div>;
    }
  };

  const getOperationSymbol = (op: string): string => {
    const symbols: Record<string, string> = {
      add: '+',
      subtract: '-',
      multiply: '*',
      divide: '/',
      modulo: '%',
      power: '^',
      equal: '==',
      not_equal: '!=',
      greater_than: '>',
      less_than: '<',
      greater_than_or_equal: '>=',
      less_than_or_equal: '<=',
      and: 'AND',
      or: 'OR',
      not: 'NOT',
    };
    return symbols[op] || op;
  };

  const getParameterInputs = () => {
    switch (data.nodeType) {
      case 'function':
        if (data.value === 'round') {
          return (
            <div className="space-y-2">
              <label className="block">
                <span className="text-xs font-medium">Decimals</span>
                <input
                  type="number"
                  min="0"
                  max="10"
                  className="w-full mt-1 px-2 py-1 text-xs border rounded"
                  value={(data.parameters.decimals as number | undefined) ?? 0}
                  onChange={(e) => handleParameterChange('decimals', parseInt(e.target.value))}
                  onClick={(e) => e.stopPropagation()}
                />
              </label>
            </div>
          );
        }
        if (data.value === 'fill_null') {
          return (
            <div className="space-y-2">
              <label className="block">
                <span className="text-xs font-medium">Fill Value</span>
                <input
                  type="text"
                  className="w-full mt-1 px-2 py-1 text-xs border rounded"
                  value={(data.parameters.fill_value as string | undefined) ?? ''}
                  onChange={(e) => handleParameterChange('fill_value', e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
              </label>
            </div>
          );
        }
        return null;
      default:
        return null;
    }
  };

  // Determine handle positions based on node type
  const getHandles = () => {
    switch (data.nodeType) {
      case 'column':
      case 'constant':
        // These are sources only (no inputs)
        return (
          <Handle
            type="source"
            position={Position.Right}
            className="w-3 h-3 !bg-gray-400"
          />
        );
      case 'operation':
        // Operations have inputs and outputs
        return (
          <>
            <Handle
              type="target"
              position={Position.Left}
              id="left"
              className="w-3 h-3 !bg-gray-400"
              style={{ top: '30%' }}
            />
            <Handle
              type="target"
              position={Position.Left}
              id="right"
              className="w-3 h-3 !bg-gray-400"
              style={{ top: '70%' }}
            />
            <Handle
              type="source"
              position={Position.Right}
              className="w-3 h-3 !bg-gray-400"
            />
          </>
        );
      case 'function':
        // Functions have one input and one output
        return (
          <>
            <Handle
              type="target"
              position={Position.Left}
              className="w-3 h-3 !bg-gray-400"
            />
            <Handle
              type="source"
              position={Position.Right}
              className="w-3 h-3 !bg-gray-400"
            />
          </>
        );
      case 'conditional':
        // Conditionals have 3 inputs (condition, if_true, if_false) and 1 output
        return (
          <>
            <Handle
              type="target"
              position={Position.Left}
              id="condition"
              className="w-3 h-3 !bg-yellow-400"
              style={{ top: '25%' }}
            />
            <Handle
              type="target"
              position={Position.Left}
              id="if_true"
              className="w-3 h-3 !bg-green-400"
              style={{ top: '50%' }}
            />
            <Handle
              type="target"
              position={Position.Left}
              id="if_false"
              className="w-3 h-3 !bg-red-400"
              style={{ top: '75%' }}
            />
            <Handle
              type="source"
              position={Position.Right}
              className="w-3 h-3 !bg-gray-400"
            />
          </>
        );
      default:
        return null;
    }
  };

  return (
    <div
      className={`rounded-lg shadow-md border-2 min-w-[120px] ${colors.bg} ${
        selected ? 'border-blue-500 ring-2 ring-blue-200' : colors.border
      }`}
    >
      {getHandles()}

      <div className="p-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-muted-foreground uppercase">{data.nodeType}</span>
          <div className="flex items-center gap-1">
            {(data.nodeType === 'constant' || data.nodeType === 'function') && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowSettings(!showSettings);
                }}
                className="p-1 hover:bg-card/50 rounded"
              >
                <Settings className="w-3 h-3 text-muted-foreground" />
              </button>
            )}
            {data.onDelete && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  data.onDelete!(id);
                }}
                className="p-1 hover:bg-card/50 rounded"
              >
                <X className="w-3 h-3 text-muted-foreground" />
              </button>
            )}
          </div>
        </div>

        <div className="text-center py-1">
          {getNodeContent()}
        </div>

        {data.error && (
          <div className="mt-2 flex items-center gap-1 text-xs text-red-600">
            <AlertCircle className="w-3 h-3" />
            {data.error}
          </div>
        )}

        {showSettings && (
          <div className="mt-2 pt-2 border-t border-border">
            {getParameterInputs() || (
              <p className="text-xs text-muted-foreground">No settings</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

FeatureNode.displayName = 'FeatureNode';

export default FeatureNode;
