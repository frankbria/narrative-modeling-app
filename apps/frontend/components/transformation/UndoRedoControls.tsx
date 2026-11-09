import { Button } from '@/components/ui/button';
import { HugeiconsIcon } from '@/components/ui/icon';
import { Redo03Icon, Undo03Icon } from '@hugeicons/core-free-icons';

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
 * - Icon buttons with Hugeicons icons
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
        <HugeiconsIcon icon={Undo03Icon} className="h-4 w-4" />
      </Button>

      <Button
        variant="outline"
        size="icon"
        onClick={onRedo}
        disabled={!canRedo || loading}
        aria-label="Redo (Ctrl+Y)"
        title="Redo (Ctrl+Y)"
      >
        <HugeiconsIcon icon={Redo03Icon} className="h-4 w-4" />
      </Button>
    </div>
  );
}
