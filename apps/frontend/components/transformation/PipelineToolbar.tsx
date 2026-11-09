'use client';

import React from 'react';
import { HugeiconsIcon, type IconSvgElement } from '@hugeicons/react';
import { CheckmarkCircle01Icon, FloppyDiskIcon, LeftToRightListBulletIcon, PlayIcon, Redo02Icon, SourceCodeIcon, Undo02Icon, ViewIcon } from '@hugeicons/core-free-icons';

export type PipelineView = 'chain' | 'visual';

interface PipelineToolbarProps {
  /** Preview and Apply are disabled while an action runs or the pipeline is empty. */
  busy: boolean;
  onPreview: VoidFunction;
  onApply: VoidFunction;
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
  const { busy, onPreview, onApply, viewMode, onViewChange } = props;
  const { onRecipes, canUndo, canRedo, onUndo, onRedo, onExport } = props;
  return (
    <div className="bg-card border-b p-4 flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-4">
        <button
          onClick={onPreview}
          disabled={busy}
          className="px-4 py-2 border border-input bg-card text-foreground rounded-lg font-semibold hover:bg-accent disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed flex items-center gap-2"
        >
          <HugeiconsIcon icon={PlayIcon} className="w-4 h-4" />
          Preview
        </button>
        <button
          onClick={onApply}
          disabled={busy}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg font-semibold hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed flex items-center gap-2"
        >
          <HugeiconsIcon icon={CheckmarkCircle01Icon} className="w-4 h-4" />
          Apply & Continue
        </button>
      </div>

      <div className="flex items-center gap-2">
        <ViewToggle viewMode={viewMode} onViewChange={onViewChange} />
        <button onClick={onRecipes} className="flex items-center gap-1 p-2 hover:bg-muted rounded" title="Manage Recipes" aria-label="Manage Recipes">
          <HugeiconsIcon icon={FloppyDiskIcon} className="w-5 h-5" />
          <span className="hidden text-sm @3xl:inline">Recipes</span>
        </button>
        <button onClick={onUndo} disabled={!canUndo} className="flex items-center gap-1 p-2 hover:bg-muted rounded disabled:opacity-50" title="Undo" aria-label="Undo">
          <HugeiconsIcon icon={Undo02Icon} className="w-5 h-5" />
          <span className="hidden text-sm @3xl:inline">Undo</span>
        </button>
        <button onClick={onRedo} disabled={!canRedo} className="flex items-center gap-1 p-2 hover:bg-muted rounded disabled:opacity-50" title="Redo" aria-label="Redo">
          <HugeiconsIcon icon={Redo02Icon} className="w-5 h-5" />
          <span className="hidden text-sm @3xl:inline">Redo</span>
        </button>
        <button onClick={onExport} className="flex items-center gap-1 p-2 hover:bg-muted rounded" title="Export as Code" aria-label="Export as Code">
          <HugeiconsIcon icon={SourceCodeIcon} className="w-5 h-5" />
          <span className="hidden text-sm @3xl:inline">Export</span>
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
      <ViewButton view="chain" current={viewMode} onSelect={onViewChange} icon={LeftToRightListBulletIcon} label="Chain" />
      <ViewButton view="visual" current={viewMode} onSelect={onViewChange} icon={ViewIcon} label="Visual" />
    </div>
  );
}

function ViewButton(props: {
  view: PipelineView;
  current: PipelineView;
  onSelect(view: PipelineView): void;
  icon: IconSvgElement;
  label: string;
}) {
  const { view, current, onSelect, icon: Icon, label } = props;
  const selected = view === current;
  return (
    <button
      type="button"
      onClick={() => onSelect(view)}
      aria-pressed={selected}
      className={`px-3 py-1.5 rounded flex items-center gap-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring ${
        selected ? 'bg-card shadow-sm font-medium' : 'text-muted-foreground'
      }`}
    >
      <HugeiconsIcon icon={Icon} className="w-4 h-4" />
      {label}
    </button>
  );
}
