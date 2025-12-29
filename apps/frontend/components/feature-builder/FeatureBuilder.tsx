'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  MarkerType,
  NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import ColumnPalette from './ColumnPalette';
import OperationPalette from './OperationPalette';
import FunctionPalette from './FunctionPalette';
import FeatureNode from './FeatureNode';
import FeaturePreview from './FeaturePreview';
import FeatureMetadata from './FeatureMetadata';
import { Play, Save, Trash2, Eye } from 'lucide-react';

interface Column {
  name: string;
  type: string;
  nullCount?: number;
  uniqueCount?: number;
}

interface FeatureBuilderProps {
  datasetId: string;
  columns: Column[];
  onSave?: (featureId: string) => void;
  onClose?: () => void;
  initialFeature?: any;
}

const nodeTypes: NodeTypes = {
  column: FeatureNode,
  operation: FeatureNode,
  function: FeatureNode,
  constant: FeatureNode,
  conditional: FeatureNode,
};

export default function FeatureBuilder({
  datasetId,
  columns,
  onSave,
  onClose,
  initialFeature,
}: FeatureBuilderProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [showMetadata, setShowMetadata] = useState(false);
  const [featureName, setFeatureName] = useState('');
  const [featureDescription, setFeatureDescription] = useState('');
  const [featureTags, setFeatureTags] = useState<string[]>([]);
  // Use ref for node ID counter to avoid stale closure issues with rapid calls
  const nodeIdCounterRef = useRef(1);

  // Load initial feature if editing
  useEffect(() => {
    if (initialFeature) {
      setFeatureName(initialFeature.name);
      setFeatureDescription(initialFeature.description || '');
      setFeatureTags(initialFeature.tags || []);
      if (initialFeature.canvas_state) {
        setNodes(initialFeature.canvas_state.nodes || []);
        setEdges(initialFeature.canvas_state.edges || []);
      }
    }
  }, [initialFeature, setNodes, setEdges]);

  // Generate unique node IDs using ref to avoid duplicate IDs when called rapidly
  const generateNodeId = useCallback(() => {
    const id = `node-${nodeIdCounterRef.current}`;
    nodeIdCounterRef.current += 1;
    return id;
  }, []);

  const onConnect = useCallback(
    (params: Connection) => {
      const edge = {
        ...params,
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      };
      setEdges((eds) => addEdge(edge, eds));
    },
    [setEdges]
  );

  const handleNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.id);
  }, []);

  // Define handleNodeUpdate before onDrop to avoid stale closure
  const handleNodeUpdate = useCallback((nodeId: string, data: any) => {
    setNodes((nds) =>
      nds.map((node) => (node.id === nodeId ? { ...node, data: { ...node.data, ...data } } : node))
    );
  }, [setNodes]);

  // Define handleDeleteNode before onDrop to avoid stale closure
  const handleDeleteNode = useCallback((nodeId: string) => {
    setNodes((nds) => nds.filter((node) => node.id !== nodeId));
    setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
  }, [setNodes, setEdges]);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const nodeType = event.dataTransfer.getData('nodeType');
      const nodeValue = event.dataTransfer.getData('nodeValue');
      const nodeLabel = event.dataTransfer.getData('nodeLabel');

      if (!nodeType) return;

      const reactFlowBounds = event.currentTarget.getBoundingClientRect();
      const position = {
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      };

      const newNode: Node = {
        id: generateNodeId(),
        type: nodeType,
        position,
        data: {
          nodeType,
          value: nodeValue,
          label: nodeLabel || nodeValue,
          parameters: {},
          onDelete: handleDeleteNode,
          onUpdate: handleNodeUpdate,
        },
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [generateNodeId, setNodes, handleDeleteNode, handleNodeUpdate]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const buildExpressionTree = useCallback(() => {
    // Find root nodes (nodes with no incoming edges)
    const targetIds = new Set(edges.map(e => e.target));
    const rootNodes = nodes.filter(n => !targetIds.has(n.id));

    if (rootNodes.length === 0 && nodes.length > 0) {
      // If no root found, use first node
      return buildNodeTree(nodes[0].id);
    } else if (rootNodes.length === 1) {
      return buildNodeTree(rootNodes[0].id);
    } else if (rootNodes.length > 1) {
      // Multiple roots - return the first one
      return buildNodeTree(rootNodes[0].id);
    }
    return null;

    function buildNodeTree(nodeId: string): any {
      const node = nodes.find(n => n.id === nodeId);
      if (!node) return null;

      // Find children (nodes this node connects to)
      const childEdges = edges.filter(e => e.source === nodeId);
      const children = childEdges
        .map(e => buildNodeTree(e.target))
        .filter(Boolean);

      return {
        node_id: node.id,
        node_type: node.data.nodeType,
        value: node.data.value,
        children,
        parameters: node.data.parameters || {},
        position: node.position,
      };
    }
  }, [nodes, edges]);

  const handlePreview = async () => {
    const expressionTree = buildExpressionTree();
    if (!expressionTree) {
      alert('Please add at least one node to the canvas');
      return;
    }

    setLoading(true);
    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/datasets/${datasetId}/features/preview`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          expression_tree: expressionTree,
          sample_size: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setPreview(data);
      } else {
        const error = await response.json();
        alert(`Preview failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to preview feature:', error);
      alert('Failed to preview feature');
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    const expressionTree = buildExpressionTree();
    if (!expressionTree) {
      alert('Please add at least one node to the canvas');
      return;
    }

    setLoading(true);
    try {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/datasets/${datasetId}/features/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          expression_tree: expressionTree,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setValidationResult(data);
      }
    } catch (error) {
      console.error('Failed to validate feature:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!featureName.trim()) {
      alert('Please enter a feature name');
      return;
    }

    const expressionTree = buildExpressionTree();
    if (!expressionTree) {
      alert('Please add at least one node to the canvas');
      return;
    }

    setLoading(true);
    try {
      const token = await getAuthToken();
      const canvasState = { nodes, edges };

      const body = {
        name: featureName,
        description: featureDescription,
        tags: featureTags,
        expression_tree: expressionTree,
        output_type: 'numeric',
        canvas_state: canvasState,
      };

      const url = initialFeature
        ? `${API_URL}/datasets/${datasetId}/features/${initialFeature.feature_id}`
        : `${API_URL}/datasets/${datasetId}/features`;

      const method = initialFeature ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (response.ok) {
        const data = await response.json();
        if (onSave) {
          onSave(data.feature_id);
        }
      } else {
        const error = await response.json();
        alert(`Save failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to save feature:', error);
      alert('Failed to save feature');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    if (confirm('Clear all nodes from the canvas?')) {
      setNodes([]);
      setEdges([]);
      setPreview(null);
      setValidationResult(null);
    }
  };

  return (
    <div className="flex h-full">
      {/* Left Sidebar - Palettes */}
      <div className="w-64 bg-gray-50 border-r overflow-y-auto">
        <div className="p-4 space-y-4">
          <h2 className="text-lg font-semibold">Feature Builder</h2>

          <ColumnPalette columns={columns} />
          <OperationPalette />
          <FunctionPalette />

          {/* Constants */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-2">Constants</h3>
            <div
              className="p-2 bg-purple-100 rounded cursor-move border border-purple-200 hover:bg-purple-200 transition-colors"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('nodeType', 'constant');
                e.dataTransfer.setData('nodeValue', '0');
                e.dataTransfer.setData('nodeLabel', 'Constant');
              }}
            >
              <span className="text-sm">Number Constant</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Canvas */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="bg-white border-b p-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <input
              type="text"
              placeholder="Feature name..."
              value={featureName}
              onChange={(e) => setFeatureName(e.target.value)}
              className="px-3 py-2 border rounded-lg w-64"
            />
            <button
              onClick={handlePreview}
              disabled={loading || nodes.length === 0}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Eye className="w-4 h-4" />
              Preview
            </button>
            <button
              onClick={handleSave}
              disabled={loading || nodes.length === 0 || !featureName.trim()}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              Save
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleClear}
              disabled={nodes.length === 0}
              className="px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50 flex items-center gap-2"
            >
              <Trash2 className="w-4 h-4" />
              Clear
            </button>
            {onClose && (
              <button
                onClick={onClose}
                className="px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
            )}
          </div>
        </div>

        {/* Canvas and Preview */}
        <div className="flex-1 flex">
          <div className="flex-1 relative">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onNodeClick={handleNodeClick}
              nodeTypes={nodeTypes}
              fitView
            >
              <Background />
              <Controls />
              <MiniMap />
            </ReactFlow>

            {nodes.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="text-center text-gray-500">
                  <p className="text-lg font-medium">Drag nodes here to build your feature</p>
                  <p className="text-sm mt-2">Connect nodes to create expressions</p>
                </div>
              </div>
            )}
          </div>

          {/* Preview Panel */}
          <FeaturePreview
            preview={preview}
            loading={loading}
            validationResult={validationResult}
          />
        </div>
      </div>

      {/* Metadata Modal */}
      {showMetadata && (
        <FeatureMetadata
          name={featureName}
          description={featureDescription}
          tags={featureTags}
          onNameChange={setFeatureName}
          onDescriptionChange={setFeatureDescription}
          onTagsChange={setFeatureTags}
          onSave={handleSave}
          onClose={() => setShowMetadata(false)}
        />
      )}
    </div>
  );
}
