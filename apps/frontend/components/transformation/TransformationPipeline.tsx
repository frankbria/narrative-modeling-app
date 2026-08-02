'use client';

import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
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

/** Shape of a transformation type as returned by GET /transformations/available. */
interface TransformationTypeMeta {
  type: string;
  label?: string;
  description?: string;
  parameters_schema?: Record<string, unknown>;
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
  const [loading, setLoading] = useState(false);
  // Undo/redo history over structural snapshots of the pipeline (#281).
  const [history, setHistory] = useState<
    Array<{ nodes: TransformationFlowNode[]; edges: Edge[] }>
  >([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  // Ref mirror of the index so the recording effect reads a fresh value
  // without depending on (and re-running for) historyIndex.
  const historyIndexRef = useRef(-1);
  // Guards the recording effect from re-capturing a snapshot that undo/redo
  // just restored (which would otherwise create a feedback loop).
  const isRestoringHistoryRef = useRef(false);
  // Last signature actually recorded; dedupes no-op re-runs (e.g. StrictMode's
  // dev double-mount) so an identical snapshot is never appended twice.
  const lastRecordedSignatureRef = useRef<string | null>(null);
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
  // Monotonic counter for collision-free node IDs (mirrors FeatureBuilder);
  // Date.now()+length can collide on rapid adds within the same millisecond.
  const nodeIdCounterRef = useRef(0);

  const { data: previewData } = useAsyncData(
    async () => {
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/datasets/${datasetId}/preview?rows=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      // A failed preview was only logged before; the pipeline stays usable.
      if (!response.ok) return null;
      return response.json();
    },
    [datasetId],
    { enabled: !!datasetId },
  );
  // Running a transformation preview replaces the initial dataset preview, so
  // the action's result is held separately and tagged with its dataset — the
  // load shows through until an action overrides it, and switching datasets
  // discards the override by derivation.
  const [previewOverride, setPreviewOverride] = useState<{
    datasetId: string;
    data: unknown;
  } | null>(null);
  const preview =
    previewOverride && previewOverride.datasetId === datasetId
      ? previewOverride.data
      : previewData ?? null;
  const setPreview = (data: unknown) => setPreviewOverride({ datasetId, data });

  // Transformation-type metadata + column names so the Chain view's Edit action
  // can open a keyboard-accessible parameter dialog (mirrors the wiring in
  // app/datasets/[id]/prepare/page.tsx). Best-effort: the pipeline still works
  // without it (dialog degrades to "no parameters needed").
  const { data: metadata } = useAsyncData(
    async () => {
      const token = await getAuthToken();

      let types: TransformationTypeMeta[] = [];
      const typesResponse = await fetch(`${API_URL}/transformations/available`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (typesResponse.ok) {
        types = (await typesResponse.json()).transformations || [];
      }

      let columns: string[] = [];
      const columnsResponse = await fetch(`${API_URL}/data/${datasetId}/preview`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (columnsResponse.ok) {
        const columnsData = await columnsResponse.json();
        if (Array.isArray(columnsData.columns)) {
          columns = columnsData.columns.map((col: { name: string }) => col.name);
        }
      }

      return { types, columns };
    },
    [datasetId],
    { enabled: !!datasetId },
  );
  const transformationTypes = metadata?.types ?? [];
  const availableColumns = metadata?.columns ?? [];

  // Reset the pipeline + undo history when the dataset changes, so switching
  // datasets on a reused component instance (the /prepare routes key only on
  // the route, not datasetId) can't leak one dataset's steps/history into
  // another via Undo (#281 — undo/redo is now live, so this leak is reachable).
  // Split deliberately: the state half is a prop-driven reset, which React's
  // docs put in render, while the ref half must stay in an effect — writing refs
  // during render is what react-hooks/refs forbids. Both still key on datasetId,
  // so they run for the same change.
  const [pipelineDataset, setPipelineDataset] = useState(datasetId);
  if (pipelineDataset !== datasetId) {
    setPipelineDataset(datasetId);
    setNodes([]);
    setEdges([]);
    setHistory([]);
    setHistoryIndex(-1);
  }

  useEffect(() => {
    historyIndexRef.current = -1;
    lastRecordedSignatureRef.current = null;
    isRestoringHistoryRef.current = false;
    nodeIdCounterRef.current = 0;
  }, [datasetId]);

  // Notify parent of unsaved changes
  useEffect(() => {
    if (onUnsavedChanges) {
      onUnsavedChanges(hasUnsavedChanges);
    }
  }, [hasUnsavedChanges, onUnsavedChanges]);

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
  // (auto-laid-out column, issue #275). `displayLabel` carries the sidebar's
  // curated label; drag-drop omits it and falls back to a type-derived label.
  const addTransformation = useCallback(
    (transformationType: string, displayLabel?: string, position?: { x: number; y: number }) => {
      if (!transformationType) return;

      nodeIdCounterRef.current += 1;
      const id = `node-${nodeIdCounterRef.current}`;
      const label =
        displayLabel ??
        transformationType.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
      setNodes((nds) => {
        const newNode: TransformationFlowNode = {
          id,
          type: 'transformation',
          position: position ?? { x: 250, y: 80 + nds.length * 120 },
          data: { type: transformationType, label, parameters: {} },
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
      addTransformation(transformationType, undefined, {
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });
    },
    [addTransformation]
  );

  // Chain view operates over the same React Flow `nodes` (single source of
  // truth) mapped to the linear step shape the accessible list expects.
  const chainSteps: ChainStep[] = useMemo(
    () =>
      nodes.map((node) => ({
        id: node.id,
        type: node.data.type,
        label: node.data.label,
        parameters: node.data.parameters as ChainStep['parameters'],
      })),
    [nodes]
  );

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
      // Read + mutate inside one functional update so the removed node is taken
      // from the current slice (no stale-closure snapshot) and the callback
      // stays stable (no `nodes` dep).
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

  const editingNode = editingIndex !== null ? nodes[editingIndex] ?? null : null;
  // TransformationConfigDialog resets its form whenever `existingConfig`'s
  // identity changes. Key this memo on the node id ALONE (not the params
  // object, whose identity churns on every setNodes) so the dialog's form
  // isn't wiped when an unrelated step is added while it's open. Params are
  // captured at open-time, which is correct: the open dialog owns the edits.
  const editingConfig = useMemo(
    () =>
      editingNode
        ? {
            type: editingNode.data.type,
            label: editingNode.data.label,
            parameters: editingNode.data.parameters,
          }
        : null,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [editingNode?.id]
  );
  const editingTypeMeta = editingNode
    ? transformationTypes.find((t) => t.type === editingNode.data.type)
    : undefined;

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

  // Structural signature of the pipeline — node type/label/params + edge
  // endpoints, but NOT node positions, so dragging a node around the canvas
  // never records an undo entry (#281).
  const structuralSignature = useMemo(
    () =>
      JSON.stringify({
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.data.type,
          label: n.data.label,
          parameters: n.data.parameters,
        })),
        edges: edges.map((e) => ({ source: e.source, target: e.target })),
      }),
    [nodes, edges]
  );

  // Record a snapshot whenever the structure changes, truncating any redo tail.
  // Skips the capture that undo/redo itself triggers via isRestoringHistoryRef.
  useEffect(() => {
    if (isRestoringHistoryRef.current) {
      isRestoringHistoryRef.current = false;
      lastRecordedSignatureRef.current = structuralSignature;
      return;
    }
    if (structuralSignature === lastRecordedSignatureRef.current) return;
    setHistory((prev) => {
      const truncated = prev.slice(0, historyIndexRef.current + 1);
      return [...truncated, { nodes, edges }];
    });
    historyIndexRef.current += 1;
    setHistoryIndex(historyIndexRef.current);
    lastRecordedSignatureRef.current = structuralSignature;
    // Intentionally keyed on the structural signature only; nodes/edges are
    // read fresh from the closure of the render that changed the signature.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structuralSignature]);

  // Restore a snapshot's structure while keeping the live canvas positions of
  // any node that still exists. Position-only drags are intentionally not
  // undoable, so undo/redo must not yank an unrelated node back to where it
  // sat when the snapshot was recorded (codex review).
  const restoreSnapshot = useCallback(
    (target: { nodes: TransformationFlowNode[]; edges: Edge[] }) => {
      isRestoringHistoryRef.current = true;
      const currentPositions = new Map(nodes.map((n) => [n.id, n.position]));
      setNodes(
        target.nodes.map((n) => {
          const pos = currentPositions.get(n.id);
          return pos ? { ...n, position: pos } : n;
        })
      );
      setEdges(target.edges);
      setHasUnsavedChanges(true);
    },
    [nodes, setNodes, setEdges]
  );

  const handleUndo = useCallback(() => {
    if (historyIndexRef.current <= 0) return;
    restoreSnapshot(history[historyIndexRef.current - 1]);
    historyIndexRef.current -= 1;
    setHistoryIndex(historyIndexRef.current);
  }, [history, restoreSnapshot]);

  const handleRedo = useCallback(() => {
    if (historyIndexRef.current >= history.length - 1) return;
    restoreSnapshot(history[historyIndexRef.current + 1]);
    historyIndexRef.current += 1;
    setHistoryIndex(historyIndexRef.current);
  }, [history, restoreSnapshot]);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <TransformationSidebar onAdd={addTransformation} />

      {/* Main Canvas */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="bg-card border-b p-4 flex items-center justify-between">
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
                className="flex border rounded-lg p-1 bg-muted mr-2"
                role="group"
                aria-label="Pipeline view"
              >
                <button
                  type="button"
                  onClick={() => setViewMode('chain')}
                  aria-pressed={viewMode === 'chain'}
                  className={`px-3 py-1.5 rounded flex items-center gap-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    viewMode === 'chain' ? 'bg-card shadow-sm font-medium' : 'text-muted-foreground'
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
                    viewMode === 'visual' ? 'bg-card shadow-sm font-medium' : 'text-muted-foreground'
                  }`}
                >
                  <Eye className="w-4 h-4" />
                  Visual
                </button>
              </div>
            )}
            <button
              onClick={() => setShowRecipeManager(true)}
              className="p-2 hover:bg-muted rounded"
              title="Manage Recipes"
            >
              <Save className="w-5 h-5" />
            </button>
            <button
              onClick={handleUndo}
              disabled={historyIndex <= 0}
              className="p-2 hover:bg-muted rounded disabled:opacity-50"
              title="Undo"
            >
              <Undo className="w-5 h-5" />
            </button>
            <button
              onClick={handleRedo}
              disabled={historyIndex >= history.length - 1}
              className="p-2 hover:bg-muted rounded disabled:opacity-50"
              title="Redo"
            >
              <Redo className="w-5 h-5" />
            </button>
            <button
              onClick={handleExportCode}
              className="p-2 hover:bg-muted rounded"
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
      {editingNode && editingConfig && (
        <TransformationConfigDialog
          open={true}
          onOpenChange={(open) => {
            if (!open) setEditingIndex(null);
          }}
          transformationType={editingNode.data.type}
          transformationLabel={editingTypeMeta?.label ?? editingNode.data.label}
          transformationDescription={editingTypeMeta?.description ?? ''}
          parametersSchema={editingTypeMeta?.parameters_schema ?? {}}
          existingConfig={editingConfig}
          availableColumns={availableColumns}
          datasetId={datasetId}
          onAdd={handleSaveEdit}
        />
      )}

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