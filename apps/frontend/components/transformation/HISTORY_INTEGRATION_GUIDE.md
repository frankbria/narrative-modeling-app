# Transformation History Integration Guide

## Overview

The transformation history system provides undo/redo functionality for dataset transformations. This guide explains how to integrate the history components into your transformation workflow.

## Architecture

### Backend Components

The backend provides RESTful endpoints for managing transformation history:

- `GET /datasets/{id}/history` - Retrieve full history
- `POST /datasets/{id}/history/undo` - Undo last transformation
- `POST /datasets/{id}/history/redo` - Redo next transformation
- `POST /datasets/{id}/history/jump` - Jump to specific position
- `DELETE /datasets/{id}/history` - Clear all history

See `claudedocs/TRANSFORMATION_HISTORY.md` for complete API documentation.

### Frontend Components

Three main components are available:

1. **UndoRedoControls** - Simple undo/redo buttons
2. **HistoryItem** - Individual history entry display
3. **TransformationHistory** - Full history panel with jump navigation

## Integration Patterns

### Pattern 1: Basic Undo/Redo Controls

For simple transformation UIs, add undo/redo buttons:

```typescript
import { useState, useEffect } from 'react';
import { UndoRedoControls } from '@/components/transformation';
import { HistoryService } from '@/lib/services/history';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { getAuthToken } from '@/lib/auth-helpers';

function TransformationPage({ datasetId }: { datasetId: string }) {
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [loading, setLoading] = useState(false);

  // Load history state
  useEffect(() => {
    loadHistoryState();
  }, [datasetId]);

  const loadHistoryState = async () => {
    try {
      const token = await getAuthToken();
      const data = await HistoryService.getHistory(datasetId, token);
      setCanUndo(data.can_undo);
      setCanRedo(data.can_redo);
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  };

  const handleUndo = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      await HistoryService.undo(datasetId, token);
      await loadHistoryState();
      await reloadDatasetPreview(); // Refresh your data display
    } catch (error) {
      console.error('Undo failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRedo = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      await HistoryService.redo(datasetId, token);
      await loadHistoryState();
      await reloadDatasetPreview(); // Refresh your data display
    } catch (error) {
      console.error('Redo failed:', error);
    } finally {
      setLoading(false);
    }
  };

  // Enable keyboard shortcuts
  useKeyboardShortcuts({
    onUndo: handleUndo,
    onRedo: handleRedo,
    enabled: !loading
  });

  return (
    <div>
      <UndoRedoControls
        canUndo={canUndo}
        canRedo={canRedo}
        onUndo={handleUndo}
        onRedo={handleRedo}
        loading={loading}
      />
      {/* Your transformation UI here */}
    </div>
  );
}
```

### Pattern 2: Full History Panel

For advanced UIs with history navigation:

```typescript
import { useState, useEffect } from 'react';
import { TransformationHistory } from '@/components/transformation';
import { HistoryService } from '@/lib/services/history';
import { getAuthToken } from '@/lib/auth-helpers';
import { HistoryEntry } from '@/lib/types/history';

function AdvancedTransformationPage({ datasetId }: { datasetId: string }) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [currentPosition, setCurrentPosition] = useState(0);

  // Load full history
  useEffect(() => {
    loadHistory();
  }, [datasetId]);

  const loadHistory = async () => {
    try {
      const token = await getAuthToken();
      const data = await HistoryService.getHistory(datasetId, token);
      setHistory(data.history);
      setCurrentPosition(data.current_position);
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  };

  const handleJumpToPosition = async (position: number) => {
    try {
      const token = await getAuthToken();
      await HistoryService.jumpToPosition(datasetId, position, token);
      await loadHistory();
      await reloadDatasetPreview();
    } catch (error) {
      console.error('Jump failed:', error);
    }
  };

  const handleClearHistory = async () => {
    if (!confirm('Clear all transformation history? This cannot be undone.')) {
      return;
    }

    try {
      const token = await getAuthToken();
      await HistoryService.clearHistory(datasetId, token);
      await loadHistory();
    } catch (error) {
      console.error('Clear failed:', error);
    }
  };

  return (
    <div className="flex h-full">
      {/* Your main UI */}
      <div className="flex-1">
        {/* Transformation controls */}
      </div>

      {/* History sidebar */}
      <div className="w-80 border-l">
        <TransformationHistory
          datasetId={datasetId}
          history={history}
          currentPosition={currentPosition}
          onJumpToPosition={handleJumpToPosition}
          onClearHistory={handleClearHistory}
        />
      </div>
    </div>
  );
}
```

### Pattern 3: Integration with WorkflowContext

For apps using the Workflow context:

```typescript
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { UndoRedoControls } from '@/components/transformation';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';

function WorkflowTransformationPage() {
  const {
    state,
    updateHistoryState,
    refreshHistory
  } = useWorkflow();

  // History state is managed in WorkflowContext
  const { canUndo, canRedo, datasetId } = state;

  const handleUndo = async () => {
    // Call HistoryService.undo...
    await refreshHistory(); // Updates WorkflowContext
  };

  const handleRedo = async () => {
    // Call HistoryService.redo...
    await refreshHistory(); // Updates WorkflowContext
  };

  useKeyboardShortcuts({
    onUndo: handleUndo,
    onRedo: handleRedo,
    enabled: true
  });

  return (
    <UndoRedoControls
      canUndo={canUndo || false}
      canRedo={canRedo || false}
      onUndo={handleUndo}
      onRedo={handleRedo}
    />
  );
}
```

## Integration with TransformationPipeline

The `TransformationPipeline` component is a visual pipeline builder. History integration works as follows:

### Current Architecture

- **Pipeline Design**: Managed locally (nodes, edges, ReactFlow state)
- **Applied Transformations**: Tracked in backend history

### Integration Approach

1. **Replace Placeholder Buttons** (lines 340-353 in TransformationPipeline.tsx):
   - Remove local `history` and `historyIndex` state
   - Replace Undo/Redo buttons with `UndoRedoControls` component
   - Add handlers that call `HistoryService.undo/redo`

2. **Refresh After Undo/Redo**:
   - Call `loadPreview()` after successful undo/redo
   - Update any related UI state

3. **Example Integration**:

```typescript
// In TransformationPipeline.tsx

import { UndoRedoControls } from '@/components/transformation';
import { HistoryService } from '@/lib/services/history';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';

// Add state for history
const [canUndo, setCanUndo] = useState(false);
const [canRedo, setCanRedo] = useState(false);

// Load history state
useEffect(() => {
  loadHistoryState();
}, [datasetId]);

const loadHistoryState = async () => {
  try {
    const token = await getAuthToken();
    const data = await HistoryService.getHistory(datasetId, token);
    setCanUndo(data.can_undo);
    setCanRedo(data.can_redo);
  } catch (error) {
    console.error('Failed to load history:', error);
  }
};

const handleUndo = async () => {
  setLoading(true);
  try {
    const token = await getAuthToken();
    await HistoryService.undo(datasetId, token);
    await loadHistoryState();
    await loadPreview(); // Reload dataset preview
  } catch (error) {
    console.error('Undo failed:', error);
  } finally {
    setLoading(false);
  }
};

const handleRedo = async () => {
  setLoading(true);
  try {
    const token = await getAuthToken();
    await HistoryService.redo(datasetId, token);
    await loadHistoryState();
    await loadPreview(); // Reload dataset preview
  } catch (error) {
    console.error('Redo failed:', error);
  } finally {
    setLoading(false);
  }
};

// Enable keyboard shortcuts
useKeyboardShortcuts({
  onUndo: handleUndo,
  onRedo: handleRedo,
  enabled: !loading
});

// In toolbar (replace lines 340-353):
<UndoRedoControls
  canUndo={canUndo}
  canRedo={canRedo}
  onUndo={handleUndo}
  onRedo={handleRedo}
  loading={loading}
/>
```

## Important Notes

### History Scope

- History tracks **applied transformations**, not pipeline designs
- Each call to `/transformations/apply` adds to history
- Undo/redo affects the **dataset state**, not the visual pipeline

### State Management

- History state can be managed locally or in WorkflowContext
- Keyboard shortcuts (Ctrl+Z/Cmd+Z, Ctrl+Y/Cmd+Y) are opt-in
- Always refresh data displays after undo/redo operations

### Error Handling

```typescript
try {
  await HistoryService.undo(datasetId, token);
} catch (error) {
  if (error.message.includes('Cannot undo')) {
    toast.error('No transformations to undo');
  } else {
    toast.error('Undo operation failed');
    console.error(error);
  }
}
```

### Testing

- Unit tests provided for all components
- Some keyboard shortcut tests skipped due to JSDOM limitations (work in real browsers)
- E2E tests should verify full undo/redo workflows

## API Reference

See `apps/frontend/lib/services/history.ts` for complete HistoryService API.

## Related Documentation

- Backend: `claudedocs/TRANSFORMATION_HISTORY.md`
- WorkflowContext: `apps/frontend/lib/contexts/WorkflowContext.tsx`
- Types: `apps/frontend/lib/types/history.ts`
