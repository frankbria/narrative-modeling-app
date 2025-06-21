'use client';

import React, { useState, useCallback, useEffect } from 'react';
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
import TransformationSidebar from './TransformationSidebar';
import TransformationNode from './TransformationNode';
import PreviewPanel from './PreviewPanel';
import RecipeManager from './RecipeManager';
import { Save, Play, Undo, Redo, Code, CheckCircle } from 'lucide-react';

interface TransformationPipelineProps {
  datasetId: string;
  onComplete?: (transformedDatasetId: string) => void;
}

const nodeTypes: NodeTypes = {
  transformation: TransformationNode,
};

export default function TransformationPipeline({ 
  datasetId, 
  onComplete 
}: TransformationPipelineProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [showRecipeManager, setShowRecipeManager] = useState(false);
  const [transformedDatasetId, setTransformedDatasetId] = useState<string | null>(null);

  // Load initial data preview
  useEffect(() => {
    loadPreview();
  }, [datasetId]);

  const loadPreview = async () => {
    try {
      const token = await getAuthToken();
      const response = await fetch(
        `${API_URL}/datasets/${datasetId}/preview?rows=100`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setPreview(data);
      }
    } catch (error) {
      console.error('Failed to load preview:', error);
    }
  };

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

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const transformationType = event.dataTransfer.getData('transformationType');
      if (!transformationType) return;

      const reactFlowBounds = event.currentTarget.getBoundingClientRect();
      const position = {
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      };

      const newNode: Node = {
        id: `node-${nodes.length + 1}`,
        type: 'transformation',
        position,
        data: {
          type: transformationType,
          label: transformationType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          parameters: {},
        },
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [nodes, setNodes]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const handleNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.id);
  }, []);

  const handleNodeUpdate = useCallback((nodeId: string, data: any) => {
    setNodes((nds) =>
      nds.map((node) => (node.id === nodeId ? { ...node, data } : node))
    );
  }, [setNodes]);

  const handlePreviewTransformation = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      const pipeline = nodes.map((node) => ({
        type: node.data.type,
        parameters: node.data.parameters,
      }));

      const response = await fetch(`${API_URL}/transformations/preview`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          dataset_id: datasetId,
          transformations: pipeline,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setPreview(data);
      }
    } catch (error) {
      console.error('Failed to preview transformation:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleApplyTransformations = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      const pipeline = nodes.map((node) => ({
        type: node.data.type,
        parameters: node.data.parameters,
      }));

      const response = await fetch(`${API_URL}/transformations/apply`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          dataset_id: datasetId,
          transformations: pipeline,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setTransformedDatasetId(data.transformed_dataset_id);
        if (onComplete) {
          onComplete(data.transformed_dataset_id);
        }
      }
    } catch (error) {
      console.error('Failed to apply transformations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveRecipe = async (name: string, description: string) => {
    try {
      const token = await getAuthToken();
      const pipeline = nodes.map((node) => ({
        type: node.data.type,
        parameters: node.data.parameters,
      }));

      const response = await fetch(`${API_URL}/recipes/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          name,
          description,
          transformations: pipeline,
          dataset_id: datasetId,
        }),
      });

      if (response.ok) {
        setShowRecipeManager(false);
      }
    } catch (error) {
      console.error('Failed to save recipe:', error);
    }
  };

  const handleLoadRecipe = async (recipe: any) => {
    // Convert recipe transformations to nodes
    const newNodes: Node[] = recipe.transformations.map((transform: any, index: number) => ({
      id: `node-${index + 1}`,
      type: 'transformation',
      position: { x: 250, y: 100 + index * 150 },
      data: {
        type: transform.type,
        label: transform.type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        parameters: transform.parameters,
      },
    }));

    // Create edges to connect nodes in sequence
    const newEdges: Edge[] = newNodes.slice(0, -1).map((node, index) => ({
      id: `edge-${index}`,
      source: node.id,
      target: newNodes[index + 1].id,
      markerEnd: {
        type: MarkerType.ArrowClosed,
      },
    }));

    setNodes(newNodes);
    setEdges(newEdges);
    setShowRecipeManager(false);
  };

  const handleExportCode = async () => {
    try {
      const token = await getAuthToken();
      const pipeline = nodes.map((node) => ({
        type: node.data.type,
        parameters: node.data.parameters,
      }));

      const response = await fetch(`${API_URL}/transformations/export-code`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          transformations: pipeline,
        }),
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'transformation_pipeline.py';
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Failed to export code:', error);
    }
  };

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <TransformationSidebar />

      {/* Main Canvas */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="bg-white border-b p-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={handlePreviewTransformation}
              disabled={loading || nodes.length === 0}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              Preview
            </button>
            <button
              onClick={handleApplyTransformations}
              disabled={loading || nodes.length === 0}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <CheckCircle className="w-4 h-4" />
              Apply & Continue
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowRecipeManager(true)}
              className="p-2 hover:bg-gray-100 rounded"
              title="Manage Recipes"
            >
              <Save className="w-5 h-5" />
            </button>
            <button
              disabled={historyIndex <= 0}
              className="p-2 hover:bg-gray-100 rounded disabled:opacity-50"
              title="Undo"
            >
              <Undo className="w-5 h-5" />
            </button>
            <button
              disabled={historyIndex >= history.length - 1}
              className="p-2 hover:bg-gray-100 rounded disabled:opacity-50"
              title="Redo"
            >
              <Redo className="w-5 h-5" />
            </button>
            <button
              onClick={handleExportCode}
              className="p-2 hover:bg-gray-100 rounded"
              title="Export as Code"
            >
              <Code className="w-5 h-5" />
            </button>
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
          </div>

          {/* Preview Panel */}
          <PreviewPanel preview={preview} loading={loading} />
        </div>
      </div>

      {/* Recipe Manager Modal */}
      {showRecipeManager && (
        <RecipeManager
          onClose={() => setShowRecipeManager(false)}
          onSave={handleSaveRecipe}
          onLoad={handleLoadRecipe}
          datasetId={datasetId}
        />
      )}
    </div>
  );
}