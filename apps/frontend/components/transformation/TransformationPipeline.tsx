'use client';

import React, { useState, useCallback, useEffect } from 'react';
import {
  ReactFlow,
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
import type { TransformationStep } from '@/lib/types/recipe';
import { getAuthToken } from '@/lib/auth-helpers';
import TransformationSidebar from './TransformationSidebar';
import TransformationNode, { TransformationFlowNode, TransformationNodeData } from './TransformationNode';
import { TransformationChainView, TransformationStep as ChainStep } from './TransformationChainView';
import { TransformationConfigDialog, TransformationConfig } from './TransformationConfigDialog';
import PreviewPanel from './PreviewPanel';
import RecipeManager from './RecipeManager';
import { Save, Play, Undo, Redo, Code, CheckCircle, Eye, List } from 'lucide-react';

interface TransformationPipelineProps {
  datasetId: string;
  onComplete?: (transformedDatasetId: string) => void;
  onUnsavedChanges?: (hasChanges: boolean) => void;
  /**
   * Whether to render the built-in Visual/Chain view toggle (issue #275).
   * Default `true` — the standalone `/prepare` route relies on it for its
   * keyboard path. Set `false` when an embedding page already provides its own
   * view switching (e.g. `/datasets/[id]/prepare`) to avoid a duplicate toggle;
   * in that mode the pipeline shows the visual canvas and the host controls views.
   */
  showViewToggle?: boolean;
}

// React Flow's NodeTypes registry expects components keyed by a generic
// NodeProps signature; our node component is typed for its specific node data,
// so the registry object is cast to NodeTypes (xyflow's documented pattern).
const nodeTypes = {
  transformation: TransformationNode,
} as NodeTypes;

export default function TransformationPipeline({
  datasetId,
  onComplete,
  onUnsavedChanges,
  showViewToggle = true
}: TransformationPipelineProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<TransformationFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [showRecipeManager, setShowRecipeManager] = useState(false);
  const [transformedDatasetId, setTransformedDatasetId] = useState<string | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  // Default to the accessible Chain view so keyboard-only users get a fully
  // operable path (add/reorder/edit/delete) without touching the drag-only
  // React Flow canvas (issue #275, WCAG 2.1.1). The Visual canvas stays one
  // keyboard-operable toggle away. When the toggle is suppressed (embedded in a
  // host that owns view switching), fall back to the visual canvas.
  const [viewMode, setViewMode] = useState<'chain' | 'visual'>(
    showViewToggle ? 'chain' : 'visual'
  );
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [transformationTypes, setTransformationTypes] = useState<Record<string, unknown>[]>([]);
  const [availableColumns, setAvailableColumns] = useState<string[]>([]);

  // Load initial data preview
  useEffect(() => {
    loadPreview();
  }, [datasetId]);

  // Load transformation-type metadata + column names so the Chain view's Edit
  // action can open a keyboard-accessible parameter dialog (mirrors the wiring
  // in app/datasets/[id]/prepare/page.tsx). Best-effort: the pipeline still
  // works without it (dialog degrades to "no parameters needed").
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const token = await getAuthToken();
        const typesResponse = await fetch(`${API_URL}/transformations/available`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (typesResponse.ok) {
          const typesData = await typesResponse.json();
          setTransformationTypes(typesData.transformations || []);
        }

        const columnsResponse = await fetch(`${API_URL}/data/${datasetId}/preview`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (columnsResponse.ok) {
          const columnsData = await columnsResponse.json();
          if (Array.isArray(columnsData.columns)) {
            setAvailableColumns(
              columnsData.columns.map((col: { name: string }) => col.name)
            );
          }
        }
      } catch (error) {
        console.error('Failed to load transformation metadata:', error);
      }
    };

    if (datasetId) {
      fetchMetadata();
    }
  }, [datasetId]);

  // Notify parent of unsaved changes
  useEffect(() => {
    if (onUnsavedChanges) {
      onUnsavedChanges(hasUnsavedChanges);
    }
  }, [hasUnsavedChanges, onUnsavedChanges]);

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
      setHasUnsavedChanges(true);
    },
    [setEdges]
  );

  // Append a new transformation node. `position` is optional so the same code
  // serves both drag-drop (drop coordinates) and the keyboard/click Add path
  // (auto-laid-out column, issue #275).
  const addTransformation = useCallback(
    (transformationType: string, position?: { x: number; y: number }) => {
      if (!transformationType) return;

      setNodes((nds) => {
        const newNode: TransformationFlowNode = {
          id: `node-${Date.now()}-${nds.length + 1}`,
          type: 'transformation',
          position: position ?? { x: 250, y: 80 + nds.length * 120 },
          data: {
            type: transformationType,
            label: transformationType.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
            parameters: {},
          },
        };
        return nds.concat(newNode);
      });
      setHasUnsavedChanges(true);
    },
    [setNodes]
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const transformationType = event.dataTransfer.getData('transformationType');
      if (!transformationType) return;

      const reactFlowBounds = event.currentTarget.getBoundingClientRect();
      addTransformation(transformationType, {
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });
    },
    [addTransformation]
  );

  // Chain view operates over the same React Flow `nodes` (single source of
  // truth) mapped to the linear step shape the accessible list expects.
  const chainSteps: ChainStep[] = nodes.map((node) => ({
    id: node.id,
    type: node.data.type,
    label: node.data.label,
    parameters: node.data.parameters as ChainStep['parameters'],
  }));

  const handleChainReorder = useCallback(
    (startIndex: number, endIndex: number) => {
      setNodes((nds) => {
        const next = [...nds];
        const [moved] = next.splice(startIndex, 1);
        next.splice(endIndex, 0, moved);
        return next;
      });
      setHasUnsavedChanges(true);
    },
    [setNodes]
  );

  const handleChainDelete = useCallback(
    (index: number) => {
      setNodes((nds) => {
        const removed = nds[index];
        if (removed) {
          setEdges((eds) =>
            eds.filter((e) => e.source !== removed.id && e.target !== removed.id)
          );
        }
        return nds.filter((_, i) => i !== index);
      });
      setHasUnsavedChanges(true);
    },
    [setNodes, setEdges]
  );

  const handleChainEdit = useCallback((index: number) => {
    setEditingIndex(index);
  }, []);

  const handleSaveEdit = useCallback(
    (config: TransformationConfig) => {
      if (editingIndex === null) return;
      setNodes((nds) =>
        nds.map((node, i) =>
          i === editingIndex
            ? { ...node, data: { ...node.data, parameters: config.parameters } }
            : node
        )
      );
      setEditingIndex(null);
      setHasUnsavedChanges(true);
    },
    [editingIndex, setNodes]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const handleNodeClick = useCallback((event: React.MouseEvent, node: TransformationFlowNode) => {
    setSelectedNode(node.id);
  }, []);

  const handleNodeUpdate = useCallback((nodeId: string, data: TransformationNodeData) => {
    setNodes((nds) =>
      nds.map((node) => (node.id === nodeId ? { ...node, data } : node))
    );
    setHasUnsavedChanges(true);
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
        setHasUnsavedChanges(false);
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

  const handleLoadRecipe = async (recipe: { transformations: TransformationStep[] }) => {
    // Convert recipe transformations to nodes
    const newNodes: TransformationFlowNode[] = recipe.transformations.map((transform: TransformationStep, index: number) => ({
      id: `node-${index + 1}`,
      type: 'transformation',
      position: { x: 250, y: 100 + index * 150 },
      data: {
        type: transform.type,
        label: transform.type.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()),
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
      <TransformationSidebar onAdd={addTransformation} />

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
            {/* View toggle — keyboard-operable; both views always reachable (#275) */}
            {showViewToggle && (
              <div
                className="flex border rounded-lg p-1 bg-gray-100 mr-2"
                role="group"
                aria-label="Pipeline view"
              >
                <button
                  type="button"
                  onClick={() => setViewMode('chain')}
                  aria-pressed={viewMode === 'chain'}
                  className={`px-3 py-1.5 rounded flex items-center gap-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    viewMode === 'chain' ? 'bg-white shadow-sm font-medium' : 'text-gray-600'
                  }`}
                >
                  <List className="w-4 h-4" />
                  Chain
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('visual')}
                  aria-pressed={viewMode === 'visual'}
                  className={`px-3 py-1.5 rounded flex items-center gap-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    viewMode === 'visual' ? 'bg-white shadow-sm font-medium' : 'text-gray-600'
                  }`}
                >
                  <Eye className="w-4 h-4" />
                  Visual
                </button>
              </div>
            )}
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

        {/* Canvas/Chain and Preview */}
        <div className="flex-1 flex">
          <div className="flex-1 relative">
            {viewMode === 'chain' ? (
              <div className="h-full overflow-y-auto p-4">
                <TransformationChainView
                  transformations={chainSteps}
                  onReorder={handleChainReorder}
                  onEdit={handleChainEdit}
                  onDelete={handleChainDelete}
                />
              </div>
            ) : (
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
            )}
          </div>

          {/* Preview Panel */}
          <PreviewPanel preview={preview} loading={loading} />
        </div>
      </div>

      {/* Edit-parameters dialog (keyboard-accessible) for the Chain view */}
      {editingIndex !== null && nodes[editingIndex] && (() => {
        const editingType = nodes[editingIndex].data.type;
        const typeMeta = transformationTypes.find((t) => t.type === editingType);
        return (
          <TransformationConfigDialog
            open={editingIndex !== null}
            onOpenChange={(open) => {
              if (!open) setEditingIndex(null);
            }}
            transformationType={editingType}
            transformationLabel={
              (typeMeta?.label as string | undefined) ?? nodes[editingIndex].data.label
            }
            transformationDescription={(typeMeta?.description as string | undefined) ?? ''}
            parametersSchema={
              (typeMeta?.parameters_schema as Record<string, unknown> | undefined) ?? {}
            }
            existingConfig={{
              type: editingType,
              label: nodes[editingIndex].data.label,
              parameters: nodes[editingIndex].data.parameters,
            }}
            availableColumns={availableColumns}
            datasetId={datasetId}
            onAdd={handleSaveEdit}
          />
        );
      })()}

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