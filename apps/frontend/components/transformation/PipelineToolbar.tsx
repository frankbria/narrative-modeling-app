'use client';

import React from 'react';
import { Save, Play, Undo, Redo, Code, CheckCircle, Eye, List } from 'lucide-react';

export type PipelineView = 'chain' | 'visual';

interface PipelineToolbarProps {
  /** Preview and Apply are disabled while an action runs or the pipeline is empty. */
  busy: boolean;
  onPreview: VoidFunction;
  onApply: VoidFunction;
  /** Render the Visual/Chain toggle (#275); an embedding page may own view switching. */
  showViewToggle: boolean;
  viewMode: PipelineView;
  onViewChange(view: PipelineView): void;
  onRecipes: VoidFunction;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: VoidFunction;
  onRedo: VoidFunction;
  onExport: VoidFunction;
}

export default function PipelineToolbar(props: PipelineToolbarProps) {
  const { busy, onPreview, onApply, showViewToggle, viewMode, onViewChange } = props;
  const { onRecipes, canUndo, canRedo, onUndo, onRedo, onExport } = props;
  return (
    <div className="bg-card border-b p-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <button
          onClick={onPreview}
          disabled={busy}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <Play className="w-4 h-4" />
          Preview
        </button>
        <button
          onClick={onApply}
          disabled={busy}
          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <CheckCircle className="w-4 h-4" />
          Apply & Continue
        </button>
      </div>

      <div className="flex items-center gap-2">
        {showViewToggle && <ViewToggle viewMode={viewMode} onViewChange={onViewChange} />}
        <button onClick={onRecipes} className="p-2 hover:bg-muted rounded" title="Manage Recipes">
          <Save className="w-5 h-5" />
        </button>
        <button onClick={onUndo} disabled={!canUndo} className="p-2 hover:bg-muted rounded disabled:opacity-50" title="Undo">
          <Undo className="w-5 h-5" />
        </button>
        <button onClick={onRedo} disabled={!canRedo} className="p-2 hover:bg-muted rounded disabled:opacity-50" title="Redo">
          <Redo className="w-5 h-5" />
        </button>
        <button onClick={onExport} className="p-2 hover:bg-muted rounded" title="Export as Code">
          <Code className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

/** Keyboard-operable view toggle; both views are always reachable (#275). */
function ViewToggle(props: { viewMode: PipelineView; onViewChange(view: PipelineView): void }) {
  const { viewMode, onViewChange } = props;
  return (
    <div className="flex border rounded-lg p-1 bg-muted mr-2" role="group" aria-label="Pipeline view">
      <ViewButton view="chain" current={viewMode} onSelect={onViewChange} icon={List} label="Chain" />
      <ViewButton view="visual" current={viewMode} onSelect={onViewChange} icon={Eye} label="Visual" />
    </div>
  );
}

function ViewButton(props: {
  view: PipelineView;
  current: PipelineView;
  onSelect(view: PipelineView): void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  const { view, current, onSelect, icon: Icon, label } = props;
  const selected = view === current;
  return (
    <button
      type="button"
      onClick={() => onSelect(view)}
      aria-pressed={selected}
      className={`px-3 py-1.5 rounded flex items-center gap-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
        selected ? 'bg-card shadow-sm font-medium' : 'text-muted-foreground'
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}
