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
import type { TransformationStep } from '@/lib/types/recipe';
import TransformationSidebar from './TransformationSidebar';
import TransformationNode, { TransformationFlowNode, TransformationNodeData } from './TransformationNode';
import { TransformationChainView, TransformationStep as ChainStep } from './TransformationChainView';
import { TransformationConfigDialog, TransformationConfig } from './TransformationConfigDialog';
import PreviewPanel from './PreviewPanel';
import RecipeManager from './RecipeManager';
import PipelineToolbar, { type PipelineView } from './PipelineToolbar';
import {
  PipelineApplyError,
  applyPipeline,
  exportPipelineCode,
  fetchDatasetRows,
  fetchTransformationTypes,
  previewPipeline,
  saveRecipe,
  type PipelinePreview,
  type PipelineStep,
  type PreviewTable,
  type TransformationTypeMeta,
} from '@/lib/services/pipelineApi';

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

/** The outcome of the last preview/apply/save, for the user rather than the console. */
function ActionStatus(props: { error: string | null; notice: string | null }) {
  const { error, notice } = props;
  if (error) {
    return (
      <div role="alert" data-testid="pipeline-error" className="mx-4 mt-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        {error}
      </div>
    );
  }
  return notice ? (
    <div role="status" className="mx-4 mt-3 rounded-md border border-border bg-muted px-3 py-2 text-sm text-foreground">
      {notice}
    </div>
  ) : null;
}

interface PipelineMetadata {
  /** `null` when GET /transformations/available failed, so the sidebar can say so. */
  types: TransformationTypeMeta[] | null;
  rows: PreviewTable | null;
}

/** Each half is best-effort: the pipeline stays usable without either. */
async function loadMetadata(datasetId: string): Promise<PipelineMetadata> {
  const [types, rows] = await Promise.all([
    fetchTransformationTypes().catch(() => null),
    fetchDatasetRows(datasetId).catch(() => null),
  ]);
  return { types, rows };
}

/** The loaded metadata, with what is not loaded yet as empty. */
function metadataView(metadata: PipelineMetadata | null | undefined) {
  const { types = [], rows = null } = metadata ?? {};
  return { types, rows, columns: rows?.columns ?? [] };
}

/** What the preview panel shows: the last action's preview for this dataset, else,
 * before any preview runs, the dataset's own rows. Tagging the override with its
 * dataset means switching datasets discards it by derivation. */
function currentPreview(
  override: { datasetId: string; data: PipelinePreview } | null,
  datasetId: string,
  rows: PreviewTable | null,
): PipelinePreview | null {
  if (override?.datasetId === datasetId) return override.data;
  return rows && { before: rows, after: null, summary: null };
}

/** The node ids an apply that stopped part-way already applied: the first `applied`
 * nodes, which are in the dataset's history now and must not be sent again. */
function appliedNodeIds(err: unknown, nodes: TransformationFlowNode[]): Set<string> {
  const applied = err instanceof PipelineApplyError ? err.applied : 0;
  return new Set(nodes.slice(0, applied).map((n) => n.id));
}

/** The Chain view's edit-parameters dialog (keyboard-accessible). */
function EditStepDialog(props: {
  node: TransformationFlowNode | undefined;
  config: TransformationConfig | null;
  types: TransformationTypeMeta[] | null;
  columns: string[];
  datasetId: string;
  onClose: VoidFunction;
  onSave(config: TransformationConfig): void;
}) {
  const { node, config, types, columns, datasetId, onClose, onSave } = props;
  if (!node || !config) return null;
  const meta = {
    label: node.data.label,
    description: '',
    parameters_schema: {},
    ...types?.find((t) => t.type === node.data.type),
  };
  return (
    <TransformationConfigDialog
      open={true}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      transformationType={node.data.type}
      transformationLabel={meta.label}
      transformationDescription={meta.description}
      parametersSchema={meta.parameters_schema}
      existingConfig={config}
      availableColumns={columns}
      datasetId={datasetId}
      onAdd={onSave}
    />
  );
}

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
  // What the last preview/apply/save said: shown to the user, never only logged (#855).
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  // Default to the accessible Chain view so keyboard-only users get a fully
  // operable path (add/reorder/edit/delete) without touching the drag-only
  // React Flow canvas (issue #275, WCAG 2.1.1). The Visual canvas stays one
  // keyboard-operable toggle away. When the toggle is suppressed (embedded in a
  // host that owns view switching), fall back to the visual canvas.
  const [viewMode, setViewMode] = useState<PipelineView>(
    showViewToggle ? 'chain' : 'visual'
  );
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  // Monotonic counter for collision-free node IDs (mirrors FeatureBuilder);
  // Date.now()+length can collide on rapid adds within the same millisecond.
  const nodeIdCounterRef = useRef(0);


  // Transformation-type metadata + column names so the Chain view's Edit action
  // can open a keyboard-accessible parameter dialog (mirrors the wiring in
  // app/datasets/[id]/prepare/page.tsx).
  const { data: metadata } = useAsyncData(() => loadMetadata(datasetId), [datasetId], {
    enabled: !!datasetId,
  });
  const { types: transformationTypes, rows: datasetRows, columns: availableColumns } = metadataView(metadata);

  // An action's preview replaces the dataset's own rows until the dataset changes.
  const [previewOverride, setPreviewOverride] = useState<{
    datasetId: string;
    data: PipelinePreview;
  } | null>(null);
  const preview = currentPreview(previewOverride, datasetId, datasetRows);

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

  const editingNode = nodes.find((_, i) => i === editingIndex);
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

  const pipelineSteps = (): PipelineStep[] =>
    nodes.map((node) => ({ type: node.data.type, parameters: node.data.parameters ?? {} }));

  /** Run one API action with the loading flag, surfacing its failure to the user. */
  const runAction = async (action: () => Promise<string | null>) => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      setNotice(await action());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handlePreviewTransformation = () =>
    runAction(async () => {
      const data = await previewPipeline(datasetId, pipelineSteps(), datasetRows);
      setPreviewOverride({ datasetId, data });
      return null;
    });

  /** Drop the nodes an apply already applied, so retrying sends only the rest. */
  const dropApplied = (err: unknown) => {
    const applied = appliedNodeIds(err, nodes);
    setNodes((nds) => nds.filter((n) => !applied.has(n.id)));
    setEdges((eds) => eds.filter((e) => !applied.has(e.source) && !applied.has(e.target)));
  };

  const handleApplyTransformations = () =>
    runAction(async () => {
      const steps = pipelineSteps();
      await applyPipeline(datasetId, steps).catch((err) => {
        dropApplied(err);
        throw err;
      });
      setHasUnsavedChanges(false);
      // Transformations move the same dataset to a new file; there is no new id.
      onComplete?.(datasetId);
      return `Applied ${steps.length} transformation${steps.length === 1 ? '' : 's'}`;
    });

  // The manager closes first, so the outcome shows on the page and not behind it.
  const handleSaveRecipe = (name: string, description: string) => {
    setShowRecipeManager(false);
    return runAction(async () => {
      await saveRecipe({ name, description, datasetId, steps: pipelineSteps() });
      return `Saved recipe "${name}"`;
    });
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

  const handleExportCode = () =>
    runAction(async () => {
      await exportPipelineCode(pipelineSteps());
      return null;
    });

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
      <TransformationSidebar types={transformationTypes} onAdd={addTransformation} />

      {/* Main Canvas */}
      <div className="flex-1 flex flex-col">
        <PipelineToolbar
          busy={loading || nodes.length === 0}
          onPreview={handlePreviewTransformation}
          onApply={handleApplyTransformations}
          showViewToggle={showViewToggle}
          viewMode={viewMode}
          onViewChange={setViewMode}
          onRecipes={() => setShowRecipeManager(true)}
          canUndo={historyIndex > 0}
          canRedo={historyIndex < history.length - 1}
          onUndo={handleUndo}
          onRedo={handleRedo}
          onExport={handleExportCode}
        />

        <ActionStatus error={error} notice={notice} />

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

      <EditStepDialog
        node={editingNode}
        config={editingConfig}
        types={transformationTypes}
        columns={availableColumns}
        datasetId={datasetId}
        onClose={() => setEditingIndex(null)}
        onSave={handleSaveEdit}
      />

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