# Transformation History: Undo/Redo System

## Overview

The transformation history system enables users to undo and redo data transformations, navigate through transformation history, and manage multiple transformation branches. The system uses an operation replay strategy that stores transformation operations (not full dataframes) and leverages S3 for version storage with content deduplication.

## Architecture

### Backend Components

#### 1. Data Models (`apps/backend/app/models/transformation.py`)

**TransformationConfig Model Extensions**:
- `current_position: int` - Tracks current position in transformation history (-1 = initial state, 0+ = step index)
- `can_undo() -> bool` - Returns True if undo operation is available (position > 0)
- `can_redo() -> bool` - Returns True if redo operation is available (position < len(steps) - 1)
- `get_current_state() -> Dict[str, Any]` - Returns metadata about current history state
- `add_transformation_step()` - Updated to handle branching (truncates forward history when applying after undo)

**Database Indexes**:
- `[("dataset_id", 1), ("current_position", 1)]` - Fast history queries
- `[("user_id", 1), ("dataset_id", 1), ("updated_at", -1)]` - User history listing

#### 2. History Service (`apps/backend/app/services/history_service.py`)

Core service orchestrating undo/redo operations:

```python
class HistoryService:
    async def undo(dataset_id: str, user_id: str) -> Dict[str, Any]
    async def redo(dataset_id: str, user_id: str) -> Dict[str, Any]
    async def jump_to_position(dataset_id: str, position: int, user_id: str) -> Dict[str, Any]
    async def get_history(dataset_id: str, user_id: str) -> Dict[str, Any]
    async def clear_history(dataset_id: str, user_id: str) -> bool
```

**Dependencies**:
- `VersioningService` - Retrieves dataset versions from S3
- `TransformationService` - Manages transformation configs

**Workflow**:
1. Get transformation config for dataset
2. Validate operation (check can_undo/can_redo)
3. Update current_position
4. Retrieve version from S3 via VersioningService
5. Update dataset file_path to point to version
6. Save updated config
7. Return result with version_id, current_position, message

#### 3. API Endpoints (`apps/backend/app/api/routes/transformations.py`)

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/datasets/{id}/history/undo` | POST | Undo last transformation | None | HistoryResponse |
| `/datasets/{id}/history/redo` | POST | Redo previously undone transformation | None | HistoryResponse |
| `/datasets/{id}/history/jump` | POST | Jump to specific position | `{ position: int }` | HistoryResponse |
| `/datasets/{id}/history` | GET | Get full history | None | HistoryData |
| `/datasets/{id}/history` | DELETE | Clear history | None | `{ success: bool }` |

**Response Schemas**:

```typescript
interface HistoryResponse {
  success: boolean;
  dataset_id: string;
  current_position: number;
  version_id: string;
  message: string;
}

interface HistoryData {
  history: HistoryEntry[];
  current_position: number;
  can_undo: boolean;
  can_redo: boolean;
}
```

**Authorization**: All endpoints require valid user authentication via `get_current_user_id` dependency and verify dataset ownership.

### Frontend Components

#### 1. TypeScript Interfaces (`apps/frontend/lib/types/history.ts`)

```typescript
interface HistoryEntry {
  position: number;
  timestamp: string;
  transformationType: string;
  description: string;
  affectedColumns: string[];
  rowsAffected?: number;
  versionId?: string;
}

interface HistoryState {
  currentPosition: number;
  entries: HistoryEntry[];
  lastSync: number;
}
```

#### 2. History Service (`apps/frontend/lib/services/history.ts`)

Client-side service for API communication:

```typescript
class HistoryService {
  async undo(datasetId: string, token: string): Promise<HistoryResponse>
  async redo(datasetId: string, token: string): Promise<HistoryResponse>
  async jumpToPosition(datasetId: string, position: number, token: string): Promise<HistoryResponse>
  async getHistory(datasetId: string, token: string): Promise<HistoryData>
  async clearHistory(datasetId: string, token: string): Promise<void>
}
```

#### 3. React Components

**UndoRedoControls** (`apps/frontend/components/transformation/UndoRedoControls.tsx`):
- Undo/Redo buttons with keyboard shortcut tooltips
- Disabled state management based on canUndo/canRedo flags
- Loading state during operations
- Integration with Shadcn/UI Button and Tooltip components

**TransformationHistory** (`apps/frontend/components/transformation/TransformationHistory.tsx`):
- Side panel displaying full transformation history
- Scrollable timeline of transformations
- Current position indicator
- Click-to-jump navigation
- Clear history button

**HistoryItem** (`apps/frontend/components/transformation/HistoryItem.tsx`):
- Individual history entry display
- Transformation icon based on type
- Timestamp (relative time format)
- Affected columns badges
- Impact summary (rows affected)
- Current position highlighting

#### 4. Custom Hooks

**useKeyboardShortcuts** (`apps/frontend/hooks/useKeyboardShortcuts.ts`):
- Ctrl+Z / Cmd+Z - Undo
- Ctrl+Y / Cmd+Y or Ctrl+Shift+Z / Cmd+Shift+Z - Redo
- Cross-platform support (Windows/Mac)
- Prevents default browser behavior
- Disabled state support

```typescript
useKeyboardShortcuts({
  onUndo: () => handleUndo(),
  onRedo: () => handleRedo(),
  enabled: true
});
```

#### 5. Workflow Context Integration

**Extended WorkflowState** (`apps/frontend/lib/types/workflow.ts`):
```typescript
interface WorkflowState {
  // Existing fields...
  historyPosition?: number;
  canUndo?: boolean;
  canRedo?: boolean;
}
```

**New Context Methods**:
- `updateHistoryPosition(position: number): void`
- `updateHistoryState(historyState: HistoryState): void`
- `refreshHistory(): Promise<void>`

#### 6. localStorage Persistence (`apps/frontend/lib/utils/historyStorage.ts`)

**Functions**:
- `saveHistoryState(datasetId: string, state: HistoryState): void`
- `loadHistoryState(datasetId: string): HistoryState | null`
- `clearHistoryState(datasetId: string): void`

**Features**:
- 24-hour cache expiry
- Offline display support
- Automatic cache invalidation

## Operation Replay Strategy

The system does NOT store full dataframes at each step. Instead:

1. **Transformation Steps**: Each transformation operation is stored with:
   - Operation type (e.g., "drop_column", "fill_missing")
   - Parameters (e.g., `{ column: "age", method: "mean" }`)
   - Metadata (timestamp, affected columns, rows affected)

2. **Version Storage**: Dataset versions are stored in S3 with:
   - Content deduplication (same content = same S3 key)
   - Metadata linking to transformation step
   - Parent version references for lineage tracking

3. **Undo/Redo**: When navigating history:
   - Update `current_position` pointer
   - Retrieve version from S3
   - Update dataset `file_path` to point to version
   - No re-execution of transformations required

## Branching History

When a user undoes to position N and applies a new transformation:

1. **Truncation**: Forward history (steps N+1 onwards) is truncated from `transformation_steps`
2. **New Branch**: New step is added at position N+1
3. **Version Linking**: New version's `parent_version_id` points to version at position N
4. **Position Update**: `current_position` updated to N+1

**UI Indication**: Timeline shows "branched" indicator for truncated history (optional feature).

## Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|---------------|-------|
| Undo | Ctrl+Z | Cmd+Z |
| Redo | Ctrl+Y or Ctrl+Shift+Z | Cmd+Y or Cmd+Shift+Z |

## Performance Considerations

### Backend Optimizations

1. **Database Indexes**: Compound indexes on `(dataset_id, current_position)` for fast queries
2. **S3 Presigned URLs**: Use presigned URLs for faster version retrieval
3. **Lazy Loading**: History panel loads only visible items initially
4. **Caching**: Version metadata cached in MongoDB

### Frontend Optimizations

1. **localStorage Caching**: History data cached for offline display
2. **Debouncing**: Keyboard shortcuts debounced (300ms) to prevent rapid calls
3. **Optimistic Updates**: UI updates immediately, rolls back on error
4. **Virtual Scrolling**: For large histories (100+ transformations)

## Error Handling

### Backend Errors

| Error | HTTP Status | Description |
|-------|-------------|-------------|
| `ValueError("Cannot undo from initial state")` | 400 Bad Request | No transformations to undo |
| `ValueError("Cannot redo from latest state")` | 400 Bad Request | No transformations to redo |
| `ValueError("Invalid position")` | 400 Bad Request | Position out of bounds |
| `PermissionError("Unauthorized")` | 403 Forbidden | User doesn't own dataset |
| `ValueError("Dataset not found")` | 404 Not Found | Dataset doesn't exist |

### Frontend Error Handling

```typescript
try {
  await historyService.undo(datasetId, token);
  // Update UI
} catch (error) {
  if (error.message.includes('Cannot undo')) {
    toast.error('No transformations to undo');
  } else {
    toast.error('Failed to undo transformation');
    console.error(error);
  }
}
```

## Testing

### Backend Tests

**Unit Tests** (`apps/backend/tests/test_models/test_transformation_history.py`):
- 12 tests covering TransformationConfig history methods
- Test coverage: 100%

**Service Tests** (`apps/backend/tests/test_services/test_history_service.py`):
- 14 tests covering HistoryService operations
- Mock S3 and database interactions
- Test coverage: 100%

**API Tests** (`apps/backend/tests/test_api/test_history_endpoints.py`):
- 7 tests covering all endpoints
- Authorization and ownership validation
- Test coverage: 100%

### Frontend Tests

**Service Tests** (`apps/frontend/__tests__/services/history.test.ts`):
- Mock fetch API
- Test all CRUD operations
- Error handling scenarios

**Component Tests**:
- `UndoRedoControls.test.tsx` - Button states, click handlers, loading
- `TransformationHistory.test.tsx` - History rendering, jump navigation
- `HistoryItem.test.tsx` - Entry display, highlighting

**Hook Tests**:
- `useKeyboardShortcuts.test.tsx` - Keyboard event handling, cross-platform

### E2E Tests (`apps/frontend/e2e/transformation-history.spec.ts`)

Complete workflow tests:
1. Apply multiple transformations
2. Undo transformations, verify data reverts
3. Redo transformations, verify data reapplies
4. Jump to middle of history
5. Apply new transformation after undo (branching)
6. Test keyboard shortcuts
7. Test history persistence across page refresh

## Usage Examples

### Basic Undo/Redo

```typescript
import { useHistoryControls } from '@/hooks/useHistoryControls';

function TransformationPage({ datasetId }: { datasetId: string }) {
  const { undo, redo, canUndo, canRedo, loading } = useHistoryControls(datasetId);

  return (
    <div>
      <button onClick={undo} disabled={!canUndo || loading}>
        Undo (Ctrl+Z)
      </button>
      <button onClick={redo} disabled={!canRedo || loading}>
        Redo (Ctrl+Y)
      </button>
    </div>
  );
}
```

### Jump to Position

```typescript
import { HistoryService } from '@/lib/services/history';

const historyService = new HistoryService();

async function jumpToStep(datasetId: string, position: number) {
  const token = await getAuthToken();
  const result = await historyService.jumpToPosition(datasetId, position, token);
  console.log(`Jumped to position ${result.current_position}`);
}
```

### Get Full History

```typescript
async function loadHistory(datasetId: string) {
  const token = await getAuthToken();
  const history = await historyService.getHistory(datasetId, token);

  console.log(`Current position: ${history.current_position}`);
  console.log(`Can undo: ${history.can_undo}`);
  console.log(`Can redo: ${history.can_redo}`);
  console.log(`History entries:`, history.history);
}
```

## Troubleshooting

### Issue: Undo button disabled when it shouldn't be

**Cause**: History state out of sync

**Solution**:
```typescript
const { refreshHistory } = useWorkflow();
await refreshHistory(); // Force refresh from backend
```

### Issue: Version not found in S3

**Cause**: S3 object deleted or version_id invalid

**Solution**: Check `DatasetVersion` model for correct `s3_key` and verify S3 bucket permissions.

### Issue: History cleared unexpectedly

**Cause**: Transformation with `current_position < len(steps) - 1` triggered branching

**Solution**: This is expected behavior. When applying transformation after undo, forward history is truncated.

### Issue: Keyboard shortcuts not working

**Cause**: Focus on input field or shortcuts disabled

**Solution**: Ensure `enabled` prop is `true` and component has focus context:
```typescript
useKeyboardShortcuts({
  onUndo,
  onRedo,
  enabled: !isInputFocused
});
```

## Future Enhancements

1. **Visual Timeline**: Graphical timeline with branching visualization
2. **Diff View**: Show side-by-side comparison between versions
3. **Named Snapshots**: Allow users to name and bookmark specific positions
4. **Batch Undo**: Undo multiple steps at once
5. **History Search**: Search transformations by type, column, or date
6. **Collaborative History**: Merge histories from multiple users
7. **Auto-save Points**: Automatically create snapshots at intervals

## API Reference

See [API Documentation](../apps/backend/docs/API.md) for complete endpoint specifications.

## Related Documentation

- [Versioning System](../apps/backend/docs/VERSIONING.md)
- [Transformation Service](../apps/backend/docs/TRANSFORMATIONS.md)
- [Testing Standards](../apps/backend/docs/TEST_STANDARDS.md)
- [Sprint Documentation](../apps/backend/docs/SPRINTS.md)
