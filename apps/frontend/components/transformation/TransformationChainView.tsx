'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  GripVertical,
  Edit,
  Trash2,
  ChevronDown,
  ChevronRight,
  MoveUp,
  MoveDown,
} from 'lucide-react';

/**
 * Transformation Step interface matching backend structure
 */
export interface TransformationStep {
  id: string;
  type: string;
  label: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  parameters: Record<string, any>;
}

/**
 * Props for TransformationChainView component
 */
interface TransformationChainViewProps {
  transformations: TransformationStep[];
  onReorder: (startIndex: number, endIndex: number) => void;
  onEdit: (index: number) => void;
  onDelete: (index: number) => void;
  className?: string;
}

/**
 * TransformationChainView Component
 *
 * Linear, keyboard-accessible alternative to ReactFlow canvas showing
 * transformation pipeline as a vertical list with drag-to-reorder capability.
 *
 * Features:
 * - Vertical list of transformation steps
 * - Drag handles for reordering (HTML5 drag-and-drop)
 * - Edit/Delete buttons for each step
 * - Visual connectors between steps
 * - Collapse/expand for step details
 * - Keyboard navigation (Arrow keys to move, Delete key to remove, Enter to edit)
 * - ARIA live regions for screen reader updates
 * - Mobile-friendly (touch-friendly targets with 44px minimum)
 *
 * Keyboard shortcuts:
 * - Alt+Arrow Up/Down: Reorder steps
 * - Delete: Remove step
 * - Enter: Edit step
 * - Tab: Navigate between steps
 */
export function TransformationChainView({
  transformations,
  onReorder,
  onEdit,
  onDelete,
  className = '',
}: TransformationChainViewProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const [announcement, setAnnouncement] = useState<string>('');

  /**
   * Announce changes to screen readers
   */
  const announce = useCallback((message: string) => {
    setAnnouncement(message);
    // Clear announcement after a delay so it can be read again if needed
    setTimeout(() => setAnnouncement(''), 1000);
  }, []);

  /**
   * Handle drag start - mark the item being dragged
   */
  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', index.toString());
  };

  /**
   * Handle drag over - allow drop
   */
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  /**
   * Handle drop - reorder items
   */
  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    if (draggedIndex !== null && draggedIndex !== dropIndex) {
      onReorder(draggedIndex, dropIndex);
      announce(
        `Step moved from position ${draggedIndex + 1} to position ${dropIndex + 1}`
      );
    }
    setDraggedIndex(null);
  };

  /**
   * Handle drag end - clear drag state
   */
  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  /**
   * Handle keyboard shortcuts
   * Alt+Arrow Up/Down: Reorder
   * Delete: Remove
   * Enter: Edit
   */
  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    // Handle Alt+ArrowUp (move up)
    if (e.altKey && e.key === 'ArrowUp' && index > 0) {
      e.preventDefault();
      onReorder(index, index - 1);
      announce(`Step ${index + 1} moved up to position ${index}`);
      return;
    }

    // Handle Alt+ArrowDown (move down)
    if (
      e.altKey &&
      e.key === 'ArrowDown' &&
      index < transformations.length - 1
    ) {
      e.preventDefault();
      onReorder(index, index + 1);
      announce(`Step ${index + 1} moved down to position ${index + 2}`);
      return;
    }

    // Handle Delete (remove step)
    if (e.key === 'Delete') {
      e.preventDefault();
      onDelete(index);
      announce(`Step ${index + 1} deleted`);
      return;
    }

    // Handle Enter (edit step)
    if (e.key === 'Enter') {
      e.preventDefault();
      onEdit(index);
      announce(`Editing step ${index + 1}: ${transformations[index].label}`);
      return;
    }
  };

  /**
   * Toggle expand/collapse for step details
   */
  const toggleExpand = (stepId: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(stepId)) {
        next.delete(stepId);
      } else {
        next.add(stepId);
      }
      return next;
    });
  };

  /**
   * Handle move up button click
   */
  const handleMoveUp = (index: number) => {
    if (index > 0) {
      onReorder(index, index - 1);
      announce(`Step ${index + 1} moved up to position ${index}`);
    }
  };

  /**
   * Handle move down button click
   */
  const handleMoveDown = (index: number) => {
    if (index < transformations.length - 1) {
      onReorder(index, index + 1);
      announce(`Step ${index + 1} moved down to position ${index + 2}`);
    }
  };

  /**
   * Handle edit button click
   */
  const handleEditClick = (index: number) => {
    onEdit(index);
    announce(`Editing step ${index + 1}: ${transformations[index].label}`);
  };

  /**
   * Handle delete button click
   */
  const handleDeleteClick = (index: number) => {
    onDelete(index);
    announce(`Step ${index + 1} deleted`);
  };

  return (
    <div
      className={className}
      role="list"
      aria-label="Transformation pipeline steps"
    >
      {/* Empty state */}
      {transformations.length === 0 ? (
        <div className="flex items-center justify-center h-32 text-muted-foreground border border-dashed rounded-lg">
          <p className="text-center">
            No transformations added yet. Add transformations from the sidebar.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {transformations.map((step, index) => (
            <div key={step.id}>
              {/* Transformation Step Card */}
              <Card
                draggable
                onDragStart={(e) => handleDragStart(e, index)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, index)}
                onDragEnd={handleDragEnd}
                onKeyDown={(e) => handleKeyDown(e, index)}
                tabIndex={0}
                className={`cursor-move transition-opacity ${
                  draggedIndex === index ? 'opacity-50' : 'opacity-100'
                } hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500`}
                role="listitem"
                aria-label={`Step ${index + 1} of ${transformations.length}: ${step.label}`}
                aria-posinset={index + 1}
                aria-setsize={transformations.length}
              >
                <CardHeader className="p-3">
                  <div className="flex items-center gap-2">
                    {/* Drag Handle */}
                    <div
                      className="flex-shrink-0 text-muted-foreground hover:text-foreground"
                      aria-hidden="true"
                    >
                      <GripVertical className="h-5 w-5" />
                    </div>

                    {/* Step Header with Expand/Collapse */}
                    <div className="flex-1 flex items-center gap-2 min-w-0">
                      <button
                        onClick={() => toggleExpand(step.id)}
                        className="flex-shrink-0 p-0 hover:bg-muted rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        aria-label={
                          expandedSteps.has(step.id)
                            ? `Collapse step ${index + 1} details`
                            : `Expand step ${index + 1} details`
                        }
                      >
                        {expandedSteps.has(step.id) ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </button>

                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-sm truncate">
                          {step.label}
                        </h3>
                        <p className="text-xs text-muted-foreground">
                          Type: {step.type}
                        </p>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {/* Move Up Button */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleMoveUp(index)}
                        disabled={index === 0}
                        aria-label={`Move step ${index + 1} up`}
                        aria-keyshortcuts="Alt+ArrowUp"
                        className="h-8 w-8 p-0"
                      >
                        <MoveUp className="h-4 w-4" />
                      </Button>

                      {/* Move Down Button */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleMoveDown(index)}
                        disabled={index === transformations.length - 1}
                        aria-label={`Move step ${index + 1} down`}
                        aria-keyshortcuts="Alt+ArrowDown"
                        className="h-8 w-8 p-0"
                      >
                        <MoveDown className="h-4 w-4" />
                      </Button>

                      {/* Edit Button */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditClick(index)}
                        aria-label={`Edit step ${index + 1}`}
                        aria-keyshortcuts="Enter"
                        className="h-8 w-8 p-0"
                      >
                        <Edit className="h-4 w-4" />
                      </Button>

                      {/* Delete Button */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteClick(index)}
                        aria-label={`Delete step ${index + 1}`}
                        aria-keyshortcuts="Delete"
                        className="h-8 w-8 p-0"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {/* Expanded Details Section */}
                  {expandedSteps.has(step.id) && (
                    <CardContent className="mt-3 p-0 pt-3 border-t">
                      <div className="space-y-2 text-sm">
                        <div>
                          <span className="font-medium text-xs text-muted-foreground">
                            Type:
                          </span>
                          <p className="text-xs mt-0.5">{step.type}</p>
                        </div>

                        {Object.keys(step.parameters).length > 0 && (
                          <div>
                            <span className="font-medium text-xs text-muted-foreground">
                              Parameters:
                            </span>
                            <ul className="space-y-1 mt-1">
                              {Object.entries(step.parameters).map(
                                ([key, value]) => (
                                  <li key={key} className="text-xs">
                                    <span className="font-medium">{key}:</span>{' '}
                                    {typeof value === 'object'
                                      ? JSON.stringify(value)
                                      : String(value)}
                                  </li>
                                )
                              )}
                            </ul>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  )}
                </CardHeader>
              </Card>

              {/* Visual Connector */}
              {index < transformations.length - 1 && (
                <div
                  className="flex justify-center py-1"
                  aria-hidden="true"
                >
                  <div className="w-0.5 h-4 bg-border" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Screen Reader Announcement Region */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </div>

      {/* Summary for screen readers */}
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {transformations.length === 0
          ? 'No transformations in pipeline'
          : `${transformations.length} transformation${transformations.length === 1 ? '' : 's'} in pipeline`}
      </div>
    </div>
  );
}
