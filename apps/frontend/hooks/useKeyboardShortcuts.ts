import { useEffect } from 'react';

interface UseKeyboardShortcutsProps {
  onUndo: () => void;
  onRedo: () => void;
  enabled?: boolean;
}

/**
 * Hook to handle keyboard shortcuts for undo/redo operations
 *
 * Supports:
 * - Ctrl+Z / Cmd+Z for undo
 * - Ctrl+Y / Cmd+Y for redo
 * - Ctrl+Shift+Z / Cmd+Shift+Z for redo (alternative)
 */
export function useKeyboardShortcuts({
  onUndo,
  onRedo,
  enabled = true
}: UseKeyboardShortcutsProps) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const modifier = isMac ? e.metaKey : e.ctrlKey;

      // Undo: Ctrl+Z or Cmd+Z (without Shift)
      if (modifier && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        onUndo();
        return;
      }

      // Redo: Ctrl+Y, Ctrl+Shift+Z, or Cmd+Shift+Z
      if (
        (modifier && e.key === 'y') ||
        (modifier && e.shiftKey && e.key === 'z')
      ) {
        e.preventDefault();
        onRedo();
        return;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onUndo, onRedo, enabled]);
}
