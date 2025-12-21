import { Button } from '@/components/ui/button';
import { Undo2, Redo2 } from 'lucide-react';

interface UndoRedoControlsProps {
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  loading?: boolean;
}

/**
 * Undo/Redo control buttons
 *
 * Provides visual controls for undo/redo operations with:
 * - Icon buttons with lucide-react icons
 * - Disabled states based on availability
 * - Loading state support
 * - Accessibility labels
 */
export function UndoRedoControls({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  loading = false
}: UndoRedoControlsProps) {
  return (
    <div className="flex gap-2">
      <Button
        variant="outline"
        size="icon"
        onClick={onUndo}
        disabled={!canUndo || loading}
        aria-label="Undo (Ctrl+Z)"
        title="Undo (Ctrl+Z)"
      >
        <Undo2 className="h-4 w-4" />
      </Button>

      <Button
        variant="outline"
        size="icon"
        onClick={onRedo}
        disabled={!canRedo || loading}
        aria-label="Redo (Ctrl+Y)"
        title="Redo (Ctrl+Y)"
      >
        <Redo2 className="h-4 w-4" />
      </Button>
    </div>
  );
}
