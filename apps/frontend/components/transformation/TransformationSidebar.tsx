'use client';

import React, { useState } from 'react';
import { Search, ChevronDown, ChevronRight } from 'lucide-react';
import type { TransformationTypeMeta } from '@/lib/services/pipelineApi';

interface TransformationCategory {
  name: string;
  transformations: TransformationTypeMeta[];
}

const CATEGORY_ICONS: Record<string, string> = { 'Data Cleaning': '🧹', 'Missing Values': '🔍' };

/** The registry's types grouped by category, filtered by the search term. The list
 * comes from GET /transformations/available (#855): a hand-kept list here advertised
 * 18 types while the engine runs 4, so most menu entries failed (#499's class). */
export function groupByCategory(types: TransformationTypeMeta[], search: string): TransformationCategory[] {
  const term = search.toLowerCase();
  const groups = new Map<string, TransformationTypeMeta[]>();
  for (const t of types) {
    const text = `${t.label} ${t.description ?? ''}`.toLowerCase();
    if (!text.includes(term)) continue;
    groups.set(t.category, [...(groups.get(t.category) ?? []), t]);
  }
  return [...groups].map(([name, transformations]) => ({ name, transformations }));
}

interface TransformationSidebarProps {
  /** The executable transformation types, from GET /transformations/available.
   * `null` means that request failed, which the sidebar says rather than showing
   * an empty menu (#855). */
  types?: TransformationTypeMeta[] | null;
  /**
   * Keyboard/click affordance for adding a transformation without dragging.
   * When provided, each transformation card becomes an activatable button so
   * keyboard-only users can add steps (WCAG 2.1.1). Drag-and-drop still works.
   * Carries the registry's display label so the chain step matches the sidebar.
   */
  onAdd?: (transformationType: string, label: string) => void;
}

export default function TransformationSidebar(props: TransformationSidebarProps = {}) {
  const { types = [], onAdd } = props;
  const [searchTerm, setSearchTerm] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggleCategory = (categoryName: string) => {
    const next = new Set(collapsed);
    if (!next.delete(categoryName)) next.add(categoryName);
    setCollapsed(next);
  };

  const filteredCategories = groupByCategory(types ?? [], searchTerm);

  return (
    <div className="w-80 bg-muted border-r flex flex-col">
      <div className="p-4 border-b bg-card">
        <h2 className="text-lg font-semibold mb-3">Transformations</h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search transformations..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {types === null && (
          <p role="alert" className="p-4 text-sm text-destructive">
            Could not load the transformations. Reload the page to try again.
          </p>
        )}
        {filteredCategories.map((category) => (
          <CategorySection
            key={category.name}
            category={category}
            collapsed={collapsed.has(category.name)}
            onToggle={toggleCategory}
            onAdd={onAdd}
          />
        ))}
      </div>

      <div className="p-4 bg-card border-t">
        <p className="text-xs text-muted-foreground text-center">
          Click or drag a transformation to add it
        </p>
      </div>
    </div>
  );
}
function onDragStart(event: React.DragEvent, transformationType: string) {
  event.dataTransfer.setData('transformationType', transformationType);
  event.dataTransfer.effectAllowed = 'move';
}

function CategorySection(props: {
  category: TransformationCategory;
  collapsed: boolean;
  onToggle(name: string): void;
  onAdd?(transformationType: string, label: string): void;
}) {
  const { category, collapsed, onToggle, onAdd } = props;
  const Chevron = collapsed ? ChevronRight : ChevronDown;
  return (
    <div className="border-b">
      <button
        onClick={() => onToggle(category.name)}
        aria-expanded={!collapsed}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-muted transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xl">{CATEGORY_ICONS[category.name] ?? '⚙️'}</span>
          <span className="font-medium">{category.name}</span>
        </div>
        <Chevron className="w-4 h-4 text-muted-foreground" />
      </button>

      {!collapsed && (
        <div className="px-2 py-2">
          {category.transformations.map((transformation) => (
            <button
              type="button"
              key={transformation.type}
              draggable
              onDragStart={(e) => onDragStart(e, transformation.type)}
              onClick={() => onAdd?.(transformation.type, transformation.label)}
              aria-label={`Add ${transformation.label}`}
              className="w-full text-left p-3 mb-2 bg-card rounded-lg border border-border cursor-move hover:border-blue-400 hover:shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <div className="font-medium text-sm">{transformation.label}</div>
              <div className="text-xs text-muted-foreground mt-1">
                {transformation.description}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
