import React, { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  Node,
  Edge,
  Connection,
  NodeChange,
  EdgeChange,
  Handle,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface TransformationPipelineProps {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: (nodes: Node[]) => void;
  onEdgesChange: (edges: Edge[]) => void;
  onNodeSelect: (node: Node | null) => void;
}

// Custom node component for transformations
const TransformationNode = ({ data, selected }: { data: any; selected: boolean }) => {
  const getNodeColor = () => {
    const typeColors = {
      remove_duplicates: '#ef4444',
      fill_missing: '#3b82f6',
      trim_whitespace: '#10b981',
      to_numeric: '#f59e0b',
      one_hot_encode: '#8b5cf6',
      formula: '#ec4899',
      default: '#6b7280'
    };
    return typeColors[data.type] || typeColors.default;
  };

  return (
    <div
      className={`px-4 py-2 shadow-lg rounded-lg border-2 ${
        selected ? 'border-blue-500' : 'border-gray-300'
      }`}
      style={{ backgroundColor: getNodeColor() + '20', borderColor: getNodeColor() }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: '#555' }}
      />
      <div className="font-semibold text-sm">{data.label}</div>
      {data.description && (
        <div className="text-xs text-gray-600 mt-1">{data.description}</div>
      )}
      {data.parameters && Object.keys(data.parameters).length > 0 && (
        <div className="text-xs text-gray-500 mt-1">
          {Object.entries(data.parameters).map(([key, value]) => (
            <div key={key}>{key}: {String(value)}</div>
          ))}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: '#555' }}
      />
    </div>
  );
};

const nodeTypes = {
  transformation: TransformationNode,
};

export function TransformationPipeline({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodeSelect,
}: TransformationPipelineProps) {
  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const updatedNodes = applyNodeChanges(changes, nodes);
      onNodesChange(updatedNodes);
    },
    [nodes, onNodesChange]
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const updatedEdges = applyEdgeChanges(changes, edges);
      onEdgesChange(updatedEdges);
    },
    [edges, onEdgesChange]
  );

  const handleConnect = useCallback(
    (params: Connection) => {
      const newEdges = addEdge(params, edges);
      onEdgesChange(newEdges);
    },
    [edges, onEdgesChange]
  );

  const handleNodeClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
      onNodeSelect(node);
    },
    [onNodeSelect]
  );

  const handlePaneClick = useCallback(() => {
    onNodeSelect(null);
  }, [onNodeSelect]);

  return (
    <div className="flex-1 bg-gray-50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={handleConnect}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        nodeTypes={nodeTypes}
        fitView
        className="bg-gray-50"
      >
        <Background color="#aaa" gap={16} />
        <Controls />
        <MiniMap 
          nodeStrokeColor={(node) => {
            const typeColors = {
              remove_duplicates: '#ef4444',
              fill_missing: '#3b82f6',
              trim_whitespace: '#10b981',
              to_numeric: '#f59e0b',
              one_hot_encode: '#8b5cf6',
              formula: '#ec4899',
              default: '#6b7280'
            };
            return typeColors[node.data?.type] || typeColors.default;
          }}
          nodeColor={(node) => {
            const typeColors = {
              remove_duplicates: '#ef4444',
              fill_missing: '#3b82f6',
              trim_whitespace: '#10b981',
              to_numeric: '#f59e0b',
              one_hot_encode: '#8b5cf6',
              formula: '#ec4899',
              default: '#6b7280'
            };
            return (typeColors[node.data?.type] || typeColors.default) + '40';
          }}
          pannable
          zoomable
        />
      </ReactFlow>
    </div>
  );
}