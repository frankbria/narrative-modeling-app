# Data Preparation Interface Enhancement - Architecture Design Document

**Project**: Narrative Modeling App  
**Phase**: Phase 3 (Architecture Review)  
**Date**: 2025-12-17  
**Status**: Architecture Design Complete

---

## Executive Summary

This document outlines the architectural approach for enhancing the data preparation interface from a global `/prepare` route to a dataset-specific `/datasets/[id]/prepare` structure. The enhancement introduces three new components (ColumnSelector, TransformationConfigDialog, TransformationChainView) while maintaining backward compatibility with existing workflows.

**Key Design Principles**:
1. **Route-driven state management**: Dataset ID flows through URL parameters rather than context/query strings
2. **Dual-interface pattern**: ReactFlow (visual pipeline) + linear chain view (accessibility alternative)
3. **Progressive disclosure**: Complex configuration via modal dialogs to reduce cognitive load
4. **Accessibility-first**: WCAG 2.1 AA compliance with keyboard navigation throughout

**Critical Success Factors**:
- Zero breaking changes to existing `/prepare?datasetId=X` workflows (backward compatibility layer)
- <100ms response time for column selection in large datasets (100K+ columns)
- Keyboard-navigable transformation pipeline (Tab, Enter, Shift+Tab)
- 85%+ test coverage for state synchronization between views

---

## Step 1: Clarify Constraints

### System Profile
- **Type**: Traditional web app (React 18/Next.js 15) with light AI integration
- **Current Scale**: <1K users (MVP), planning for 10K+ users
- **Team Size**: 1-2 frontend developers (experienced with Next.js/React)
- **Hosting**: Cost-sensitive (<$200/month), shared VPS
- **Browser Support**: Modern browsers (Chrome, Firefox, Safari, Edge); mobile responsiveness required

### Technical Constraints
- **State Management**: Next.js App Router with useParams, useSearchParams hooks
- **ReactFlow**: Used for drag-and-drop visual editor (xyflow v11+)
- **Authentication**: NextAuth v5 (bearer token auth in API calls)
- **API Calls**: Async/await with token injection via getAuthToken()
- **Styling**: Tailwind CSS with Shadcn/UI primitives (Radix UI-based)
- **Testing**: Jest (unit) + Playwright (E2E)

### Operational Constraints
- **No Breaking Changes**: `/prepare?datasetId=X` must continue working
- **Backward Compatibility Window**: 6 months (until Phase 4)
- **Data Loss Prevention**: Unsaved transformations should prompt user before navigation
- **Performance Budget**: Initial load <2s, column selection <200ms

---

## Step 2-3: Design Architecture

### Route Migration Strategy

#### Current State (Phase 1-2)
```
/prepare (global route)
  ├─ useSearchParams() → datasetId from ?datasetId=XYZ
  ├─ WorkflowContext → setDatasetId(), completeStage()
  └─ TransformationPipeline (hardcoded to /prepare)
```

#### Target State (Phase 3+)
```
/datasets/[id]/prepare (dataset-specific)
  ├─ useParams() → datasetId from route [id]
  ├─ WorkflowContext → integrate with stage routing
  └─ Enhanced TransformationPipeline
      ├─ ColumnSelector (new)
      ├─ TransformationConfigDialog (new)
      └─ TransformationChainView (new)
```

#### Migration Approach: **Dual-Route Strategy**

**Phase 3a** (Immediate): Deploy new route alongside old
```
1. Create /datasets/[id]/prepare/page.tsx (new route)
2. Keep /prepare/page.tsx functional (backward compatibility)
3. Update WorkflowContext.setCurrentStage() to route to /datasets/[datasetId]/prepare
4. Add deprecation warning in /prepare → logs analytics event
```

**Phase 3b** (Month 3): User migration
```
1. Redirect /prepare?datasetId=X → /datasets/X/prepare (302 redirect with analytics)
2. Monitor usage via analytics dashboard
3. Maintain both routes if >5% traffic on old route
```

**Phase 4** (Month 6): Remove old route
```
1. Deprecate /prepare completely
2. Archive users still on old route
```

#### Implementation Plan
```typescript
// apps/frontend/app/datasets/[id]/prepare/page.tsx (new)
'use client'
import { useParams } from 'next/navigation'
import PreparePageContent from '@/components/PreparePageContent'

export default function DatasetPreparePage() {
  const params = useParams()
  const datasetId = params.id as string
  
  return <PreparePageContent datasetId={datasetId} />
}

// apps/frontend/lib/contexts/WorkflowContext.tsx (updated)
const setCurrentStage = useCallback((stage: WorkflowStage) => {
  const stageConfig = WORKFLOW_STAGES.find(s => s.id === stage)
  if (stageConfig && canAccessStage(stage)) {
    // NEW: Route to dataset-specific path
    const basePath = state.datasetId 
      ? `${stageConfig.route}/${state.datasetId}`
      : stageConfig.route
    
    router.push(basePath)
  }
}, [state.datasetId, canAccessStage, router])

// Backward compatibility redirect
// apps/frontend/app/prepare/page.tsx (updated to redirect)
'use client'
import { useSearchParams, useRouter } from 'next/navigation'
import { useEffect } from 'react'

export default function PreparePage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const datasetId = searchParams.get('datasetId')
  
  useEffect(() => {
    if (datasetId) {
      // 302 redirect to new route
      router.push(`/datasets/${datasetId}/prepare`)
    } else {
      // No dataset specified, go to upload
      router.push('/upload')
    }
  }, [datasetId, router])
  
  return <div /> // Loading state while redirecting
}
```

---

### Component Hierarchy & Composition

#### New Component Tree Structure

```
PreparePageContent (wrapper component - new)
├─ Layout & State Management
│  ├─ datasetId: string (from params)
│  ├─ selectedColumns: Set<string> (local state)
│  ├─ transformations: Transform[] (local state)
│  ├─ showColumnSelector: boolean (local state)
│  └─ showConfigDialog: boolean (local state)
│
├─ Header Section
│  ├─ Page Title + Breadcrumb
│  ├─ Dataset Info (name, row count)
│  └─ Mode Toggle: ReactFlow ↔ ChainView
│
├─ Left Sidebar (300px fixed)
│  ├─ ColumnSelector (new)
│  │  ├─ Search input (debounced, keyboard navigable)
│  │  ├─ Column list (virtualized for 1000+ columns)
│  │  ├─ Selected count badge
│  │  └─ Select All / Deselect All buttons
│  │
│  └─ Transformation Library
│     ├─ 30+ transformation types (categorized)
│     ├─ Drag source for ReactFlow
│     └─ Click-to-add for ChainView
│
├─ Main Canvas Area (flex-1)
│  ├─ Conditional Rendering:
│  │  ├─ if (view === 'pipeline'): TransformationPipeline (existing)
│  │  │   └─ onNodeClick → setSelectedNode → show TransformationConfigDialog
│  │  │
│  │  └─ if (view === 'chain'): TransformationChainView (new)
│  │      ├─ Linear step list (row-oriented)
│  │      ├─ Reorder via drag-and-drop OR arrow buttons
│  │      └─ Click step → show TransformationConfigDialog
│  │
│  └─ Toolbar
│     ├─ Preview button (runs transformation preview)
│     ├─ Apply & Continue button (saves + advances stage)
│     ├─ Recipe Manager button (save/load presets)
│     ├─ Export Code button
│     ├─ Undo/Redo buttons
│     └─ Help / Documentation link
│
├─ Right Panel (300px, collapsible)
│  ├─ Preview Panel
│  │  ├─ Data preview table (before/after comparison)
│  │  ├─ Schema comparison (columns added/removed)
│  │  ├─ Data quality metrics
│  │  └─ Row count diff
│  │
│  └─ Properties Panel (when step selected)
│     ├─ Transformation type badge
│     ├─ Target columns list
│     └─ Quick-edit parameters
│
└─ Modals & Overlays
   ├─ TransformationConfigDialog (new)
   │  ├─ Transformation type display
   │  ├─ Dynamic parameter form (based on type)
   │  ├─ Column selector (if applicable)
   │  ├─ Preview of effect (if supported)
   │  ├─ Save / Cancel buttons
   │  └─ Delete step option
   │
   ├─ RecipeManager (existing, enhanced)
   │  ├─ Save recipe form
   │  └─ Load recipe browser
   │
   └─ Unsaved Changes Prompt
      ├─ "You have unsaved changes"
      ├─ Discard / Save buttons
      └─ Triggered on route leave
```

#### Component Props & Interfaces

```typescript
// PreparePageContent.tsx
interface PreparePageContentProps {
  datasetId: string
}

// ColumnSelector.tsx
interface ColumnSelectorProps {
  datasetId: string
  selectedColumns: Set<string>
  onSelectionChange: (columns: Set<string>) => void
  onSelectAll: () => void
  onDeselectAll: () => void
  totalColumnCount: number
  isLoading?: boolean
  error?: string | null
}

// TransformationConfigDialog.tsx
interface TransformationConfigDialogProps {
  isOpen: boolean
  transformation?: TransformationStep | null
  transformationType?: string | null
  availableColumns: string[]
  onSave: (config: TransformationStep) => void
  onCancel: () => void
  onDelete?: (nodeId: string) => void
  isLoading?: boolean
}

// TransformationChainView.tsx
interface TransformationChainViewProps {
  transformations: TransformationStep[]
  selectedStepId?: string
  onStepClick: (stepId: string) => void
  onStepReorder: (fromIndex: number, toIndex: number) => void
  onStepDelete: (stepId: string) => void
  onStepEdit: (stepId: string, config: TransformationStep) => void
  isLoading?: boolean
}

// TransformationStep type (backend-aligned)
interface TransformationStep {
  id: string
  transformation_type: string
  column?: string
  columns?: string[]
  parameters: Record<string, any>
  rows_affected?: number
  data_loss_percentage?: number
}
```

---

### State Management Strategy

#### Local State Hierarchy (PreparePageContent)

```typescript
const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set())
const [transformations, setTransformations] = useState<TransformationStep[]>([])
const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
const [preview, setPreview] = useState<PreviewData | null>(null)
const [view, setView] = useState<'pipeline' | 'chain'>('pipeline')
const [unsavedChanges, setUnsavedChanges] = useState(false)
const [isLoading, setIsLoading] = useState(false)
```

#### Context Integration Points

```typescript
// WorkflowContext usage in PreparePageContent
const { state, completeStage, canAccessStage, setDatasetId } = useWorkflow()

useEffect(() => {
  // Ensure datasetId is set in context
  if (datasetId && datasetId !== state.datasetId) {
    setDatasetId(datasetId)
  }
}, [datasetId, state.datasetId, setDatasetId])

// On transformation complete
const handleApplyTransformations = async () => {
  try {
    const response = await applyTransformations(datasetId, transformations)
    const transformedDatasetId = response.transformed_dataset_id
    
    // Update WorkflowContext
    completeStage(WorkflowStage.DATA_PREPARATION, {
      transformedDatasetId,
      selectedColumns,
      transformationCount: transformations.length,
      timestamp: new Date().toISOString()
    })
    
    // Auto-advances to next stage (FEATURE_ENGINEERING)
  } catch (error) {
    showErrorToast(error.message)
  }
}
```

#### State Synchronization Between Views

**Challenge**: User switches between ReactFlow (pipeline) and ChainView (chain) - both need to sync

**Solution**: Single transformation array state, different renderers

```typescript
// One source of truth
const [transformations, setTransformations] = useState<TransformationStep[]>([])

// Both views read/write to same state
// ReactFlow side
const handleNodeUpdate = useCallback((nodeId: string, data: any) => {
  setTransformations(prev => 
    prev.map(t => t.id === nodeId ? { ...t, ...data } : t)
  )
}, [])

// ChainView side
const handleStepEdit = useCallback((stepId: string, config: TransformationStep) => {
  setTransformations(prev =>
    prev.map(t => t.id === stepId ? { ...t, ...config } : t)
  )
}, [])

// Both use same reorder function
const handleReorder = useCallback((fromIndex: number, toIndex: number) => {
  setTransformations(prev => {
    const newOrder = [...prev]
    const [removed] = newOrder.splice(fromIndex, 1)
    newOrder.splice(toIndex, 0, removed)
    return newOrder
  })
  setUnsavedChanges(true)
}, [])
```

---

## Step 4: Risk Assessment & Mitigation

### Risk 1: Breaking Existing `/prepare` Route Users
**Severity**: HIGH  
**Probability**: MEDIUM  
**Impact**: Data loss, workflow interruption for active users

**Mitigation Strategy**:
```typescript
// 1. Automatic redirect with analytics logging
analytics.trackEvent('prepare_route_redirect', {
  from: '/prepare',
  to: `/datasets/${datasetId}/prepare`,
  timestamp: new Date().toISOString()
})

// 2. Grace period: Keep /prepare route functional for 6 months
// 3. Monitor usage: Track % traffic on old vs new route
// 4. Pre-announcement: Email notification to active users before cutover
// 5. Rollback plan: If >10% traffic stays on old route, extend grace period
```

### Risk 2: Performance Degradation with Large Transformation Pipelines
**Severity**: MEDIUM  
**Probability**: HIGH  
**Impact**: UI lag, poor UX for 100+ step pipelines

**Mitigation Strategy**:
```typescript
// 1. Virtualization for ChainView (1000+ steps)
import { FixedSizeList } from 'react-window'

<FixedSizeList
  height={600}
  itemCount={transformations.length}
  itemSize={80}
  width="100%"
>
  {({ index, style }) => (
    <TransformationChainItem 
      style={style}
      step={transformations[index]}
    />
  )}
</FixedSizeList>

// 2. Lazy-load node configurations in ReactFlow
const handleNodeClick = useCallback(async (event, node) => {
  // Only fetch config for clicked node
  const config = await fetchTransformationConfig(node.id)
  setSelectedConfig(config)
}, [])

// 3. Debounce preview updates (500ms)
const debouncedPreview = useMemo(
  () => debounce(handlePreviewTransformation, 500),
  []
)
```

### Risk 3: Accessibility Gaps in Drag-and-Drop + Click Interfaces
**Severity**: HIGH  
**Probability**: MEDIUM  
**Impact**: WCAG 2.1 AA compliance failure, user frustration

**Mitigation Strategy**:
```typescript
// 1. Keyboard-only mode (ChainView as primary accessible interface)
// 2. ARIA labels on all interactive elements
<button
  aria-label="Reorder step up"
  aria-keyshortcuts="Alt+ArrowUp"
  onClick={() => handleReorder(index, index - 1)}
>
  Move Up
</button>

// 3. Focus management in dialogs
useEffect(() => {
  if (isOpen) {
    // Focus first interactive element
    firstInputRef.current?.focus()
  }
}, [isOpen])

// 4. Screen reader announcements
const announceChange = useCallback((message: string) => {
  const announcement = document.createElement('div')
  announcement.setAttribute('role', 'status')
  announcement.setAttribute('aria-live', 'polite')
  announcement.setAttribute('aria-atomic', 'true')
  announcement.textContent = message
  document.body.appendChild(announcement)
  setTimeout(() => announcement.remove(), 2000)
}, [])

// 5. Test with NVDA/JAWS/VoiceOver
```

### Risk 4: State Synchronization Between ReactFlow and ChainView
**Severity**: MEDIUM  
**Probability**: MEDIUM  
**Impact**: Data inconsistency, user confusion

**Mitigation Strategy**:
```typescript
// 1. Single source of truth (transformations state array)
// 2. Event-driven sync (publish/subscribe pattern)
const emit = (event: 'step-added' | 'step-updated', payload: any) => {
  listeners.forEach(fn => fn(event, payload))
}

// 3. Conflict resolution (last-write-wins for now)
const handleStepUpdate = useCallback((stepId: string, newData: any) => {
  const timestamp = Date.now()
  setTransformations(prev => {
    const updated = prev.map(t => 
      t.id === stepId 
        ? { ...t, ...newData, _lastUpdated: timestamp } 
        : t
    )
    emit('step-updated', { stepId, timestamp })
    return updated
  })
}, [])

// 4. Unit tests for state transitions
// 5. E2E tests: Switch views and verify consistency
```

### Risk 5: Large Column Lists Causing UI Slowdown
**Severity**: MEDIUM  
**Probability**: HIGH  
**Impact**: Column selector becomes unusable (>1000 columns)

**Mitigation Strategy**:
```typescript
// 1. Virtualize column list with react-window
<FixedSizeList
  height={400}
  itemCount={columnCount}
  itemSize={35}
>
  {({ index, style }) => (
    <ColumnListItem
      style={style}
      column={columns[index]}
    />
  )}
</FixedSizeList>

// 2. Debounced search (200ms)
const debouncedSearch = useMemo(
  () => debounce((term: string) => {
    const filtered = filterColumns(term)
    setFilteredColumns(filtered)
  }, 200),
  []
)

// 3. Lazy-load column metadata (only fetch on demand)
// 4. Cache column list per dataset (5-min TTL)
```

### Risk 6: Mobile/Touch Accessibility
**Severity**: LOW-MEDIUM  
**Probability**: MEDIUM  
**Impact**: Poor mobile UX, accessibility issues

**Mitigation Strategy**:
```typescript
// 1. Touch-friendly targets (min 44px × 44px)
// 2. ChainView as default on mobile (avoid drag-and-drop)
const isMobile = useMediaQuery('(max-width: 768px)')
const defaultView = isMobile ? 'chain' : 'pipeline'

// 3. Bottom sheet dialog for configuration (vs modal)
// 4. Large touch targets in ColumnSelector
// 5. E2E test on real mobile devices + Playwright mobile emulation

// 6. Responsive layout
<div className="flex flex-col md:flex-row gap-4">
  <aside className="w-full md:w-80">
    <ColumnSelector />
  </aside>
  <main className="flex-1">
    <TransformationCanvas />
  </main>
</div>
```

---

## Accessibility Specification

### WCAG 2.1 AA Compliance Checklist

#### Keyboard Navigation
```
TAB Order (PreparePageContent):
  1. Header: Title link → Mode toggle button
  2. Sidebar: Search input → Column list (arrow keys) → Select All button
  3. Main: Transformation canvas (Tab within) → Add button
  4. Canvas: 
     - ReactFlow: Tab between nodes, Enter to edit
     - ChainView: Tab between steps, Enter to edit, Alt+Up/Down to reorder
  5. Preview panel: Tab through preview controls
  6. Toolbar: Preview → Apply & Continue → Recipe Manager → Export
```

#### ARIA Attributes
```html
<!-- ColumnSelector -->
<div
  role="region"
  aria-labelledby="column-selector-title"
  aria-live="polite"
  aria-busy={isLoading}
>
  <h2 id="column-selector-title">Select Columns</h2>
  
  <input
    type="search"
    aria-label="Search columns"
    aria-describedby="search-hint"
    aria-expanded={isOpen}
    placeholder="Search by name..."
  />
  <span id="search-hint" className="sr-only">
    Type to filter, use arrow keys to navigate
  </span>
  
  <ul role="listbox" aria-multiselectable="true">
    {columns.map(col => (
      <li key={col.name} role="option" aria-selected={isSelected(col.name)}>
        <input type="checkbox" />
        {col.name}
      </li>
    ))}
  </ul>
</div>

<!-- TransformationChainView -->
<ol role="list" aria-label="Transformation pipeline">
  {transformations.map((step, idx) => (
    <li key={step.id} role="listitem" aria-posinset={idx + 1} aria-setsize={transformations.length}>
      <button
        onClick={() => selectStep(step.id)}
        aria-current={isSelected ? 'step' : undefined}
        aria-label={`Step ${idx + 1}: ${step.transformation_type}`}
      >
        {step.transformation_type}
      </button>
      <button
        aria-label={`Move step ${idx + 1} up`}
        aria-keyshortcuts="Alt+ArrowUp"
        onClick={() => handleReorder(idx, idx - 1)}
      >
        ▲
      </button>
      <button
        aria-label={`Move step ${idx + 1} down`}
        aria-keyshortcuts="Alt+ArrowDown"
        onClick={() => handleReorder(idx, idx + 1)}
      >
        ▼
      </button>
      <button
        aria-label={`Delete step ${idx + 1}`}
        onClick={() => handleDelete(step.id)}
      >
        ✕
      </button>
    </li>
  ))}
</ol>

<!-- TransformationConfigDialog -->
<dialog
  aria-labelledby="dialog-title"
  aria-describedby="dialog-desc"
  aria-modal="true"
>
  <h2 id="dialog-title">Configure Transformation</h2>
  <p id="dialog-desc">Set parameters for {transformationType}</p>
  
  <!-- Focus trap: First element gets focus -->
  <input ref={firstInputRef} autoFocus />
  
  <!-- Last element wraps focus back to first -->
  <button onClick={() => firstInputRef.current?.focus()}>
    Cancel (or Tab from last element)
  </button>
</dialog>
```

#### Keyboard Shortcuts Reference
```
Global:
  Ctrl/Cmd+Z     → Undo
  Ctrl/Cmd+Shift+Z → Redo
  Ctrl/Cmd+S     → Save current state
  
Column Selector:
  ArrowUp/Down    → Navigate column list
  Space           → Toggle selection
  Ctrl+A          → Select all visible
  Shift+Ctrl+A    → Deselect all
  
Transformation Chain:
  Tab             → Move to next step
  Shift+Tab       → Move to previous step
  Enter           → Edit selected step
  Delete          → Remove selected step
  Alt+ArrowUp     → Move step up in chain
  Alt+ArrowDown   → Move step down in chain
  Escape          → Close dialog (if open)
  
Transformation Config Dialog:
  Tab             → Move to next field
  Shift+Tab       → Move to previous field
  Enter           → Save (if on Save button)
  Escape          → Cancel dialog
```

#### Screen Reader Testing Matrix
```
Device/Software          | Test Status
------------------------+-------------
NVDA (Windows)          | Required
JAWS (Windows)          | Required
VoiceOver (macOS)       | Required
VoiceOver (iOS)         | Required
TalkBack (Android)      | Required
```

---

## Component Specifications

### 1. ColumnSelector Component

**File**: `/apps/frontend/components/transformation/ColumnSelector.tsx`

**Responsibilities**:
- Display searchable, multi-select list of columns
- Virtualize for 1000+ column lists
- Provide Select All / Deselect All actions
- Emit selection change events

**Props**:
```typescript
interface ColumnSelectorProps {
  datasetId: string
  selectedColumns: Set<string>
  onSelectionChange: (columns: Set<string>) => void
  totalColumnCount: number
  isLoading?: boolean
  error?: string | null
}
```

**State**:
```typescript
const [searchTerm, setSearchTerm] = useState('')
const [filteredColumns, setFilteredColumns] = useState<Column[]>([])
const [columns, setColumns] = useState<Column[]>([])
```

**Keyboard Navigation**:
- ArrowUp/Down: Navigate list
- Space: Toggle checkbox
- Ctrl+A: Select all filtered
- Shift+Ctrl+A: Deselect all

**Test Coverage**:
- Search performance (<200ms for 1000 columns)
- Virtualization working correctly
- Keyboard navigation works end-to-end
- Selection state sync with parent

### 2. TransformationConfigDialog Component

**File**: `/apps/frontend/components/transformation/TransformationConfigDialog.tsx`

**Responsibilities**:
- Display modal for configuring transformation parameters
- Render dynamic form based on transformation type
- Allow column selection for applicable transformations
- Validate parameters before saving

**Props**:
```typescript
interface TransformationConfigDialogProps {
  isOpen: boolean
  transformation?: TransformationStep | null
  transformationType?: string | null
  availableColumns: string[]
  onSave: (config: TransformationStep) => void
  onCancel: () => void
  onDelete?: (stepId: string) => void
  isLoading?: boolean
}
```

**Dialog Focus Management**:
- Auto-focus first form field on open
- Focus trap: Tab from last element → first element
- Escape key closes dialog
- Tab/Shift+Tab navigate form fields

**Parameter Forms** (varies by transformation type):
```
REMOVE_DUPLICATES
  - Columns to consider (multi-select)
  - Keep strategy: first, last, none
  
FILL_MISSING
  - Target column (select)
  - Fill method: value, mean, median, forward, backward
  - Fill value (text input, if method=value)
  
TO_NUMERIC
  - Target column (select)
  - Error handling: raise, coerce, ignore
  
SCALE
  - Target columns (multi-select)
  - Scaling method: minmax, standard, robust
```

**Test Coverage**:
- Form renders correctly for each transformation type
- Validation works (required fields, type checks)
- Focus trap prevents tab escape
- Escape key closes dialog
- Delete button works (with confirmation)

### 3. TransformationChainView Component

**File**: `/apps/frontend/components/transformation/TransformationChainView.tsx`

**Responsibilities**:
- Display linear list of transformation steps
- Allow reordering via drag-and-drop OR arrow buttons
- Support step selection and editing
- Provide delete/duplicate actions

**Props**:
```typescript
interface TransformationChainViewProps {
  transformations: TransformationStep[]
  selectedStepId?: string
  onStepClick: (stepId: string) => void
  onStepReorder: (fromIndex: number, toIndex: number) => void
  onStepDelete: (stepId: string) => void
  onStepEdit: (stepId: string, config: TransformationStep) => void
  isLoading?: boolean
}
```

**Layout**:
```
[Step 1] ▲ ▼ [Edit] [Delete]
[Step 2] ▲ ▼ [Edit] [Delete]
[Step 3] ▲ ▼ [Edit] [Delete]
```

**Interaction Patterns**:

1. **Click to select**: Click step → highlight + show details
2. **Arrow buttons to reorder**: Alt+Up/Alt+Down (keyboard) or button click
3. **Drag to reorder** (optional drag-and-drop for mouse users)
4. **Click Edit**: Opens TransformationConfigDialog for that step
5. **Click Delete**: Shows confirmation → removes step

**Accessibility Features**:
- Each step is a `<li role="listitem">` with proper ARIA
- Arrow buttons have aria-keyshortcuts
- Focus visible on selected step
- Screen reader announces position: "Step 2 of 5"

**Test Coverage**:
- Reorder works via arrow buttons
- Reorder works via drag-and-drop (if enabled)
- Delete removes step from list
- Selected step highlights correctly
- Keyboard navigation (Tab, ArrowUp/Down, Alt+Up/Down)

### 4. Enhanced PreparePageContent Wrapper

**File**: `/apps/frontend/components/PreparePageContent.tsx` (new)

**Responsibilities**:
- Orchestrate state for preparation page
- Route dataset ID from params/context
- Manage transitions between ReactFlow and ChainView
- Handle save/discard logic

**Key Methods**:

```typescript
// Load dataset metadata and column list
const loadDatasetMetadata = async (datasetId: string) => {
  const response = await fetch(`${API_URL}/datasets/${datasetId}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.json()
}

// Sync transformation state between views
const handleTransformationUpdate = (stepId: string, newData: any) => {
  setTransformations(prev =>
    prev.map(t => t.id === stepId ? { ...t, ...newData } : t)
  )
  setUnsavedChanges(true)
}

// Prompt before navigation if unsaved changes
useEffect(() => {
  const handleBeforeUnload = (e: BeforeUnloadEvent) => {
    if (unsavedChanges) {
      e.preventDefault()
      e.returnValue = ''
    }
  }
  window.addEventListener('beforeunload', handleBeforeUnload)
  return () => window.removeEventListener('beforeunload', handleBeforeUnload)
}, [unsavedChanges])
```

---

## Testing Strategy

### Unit Tests (Jest)
```typescript
// ColumnSelector.test.tsx
- Renders search input and column list
- Search filters columns correctly
- Selection updates parent state
- Keyboard navigation works
- Virtualization renders visible items only

// TransformationConfigDialog.test.tsx
- Renders form fields for transformation type
- Validates required fields
- Saves configuration on submit
- Closes on Escape key
- Focus trap prevents Tab escape

// TransformationChainView.test.tsx
- Renders steps in order
- Reorder via arrow buttons works
- Delete removes step
- Selected step highlights
- Keyboard navigation works (Alt+Up/Down)

// PreparePageContent.test.tsx
- Loads dataset metadata on mount
- Syncs state between views
- Shows unsaved changes prompt
- Completes workflow stage on apply
```

### E2E Tests (Playwright)
```typescript
// scenarios/data-preparation.spec.ts
- User loads /datasets/[id]/prepare
- User selects columns
- User adds transformation
- User configures transformation
- User previews changes
- User applies transformations
- User completes stage and advances
- User switches between ReactFlow and ChainView
- Keyboard-only workflow (no mouse)
- Unsaved changes warning appears
```

### Accessibility Tests
```
- axe-core automated scans (Jest)
- WAVE manual review
- NVDA/JAWS testing
- Keyboard navigation (all 6 keyboard shortcuts)
- Focus visible indicators
- Color contrast ratios
```

---

## Backward Compatibility Layer

### Dual-Route Implementation

```typescript
// /apps/frontend/app/prepare/page.tsx (UPDATED - redirects)
'use client'
import { useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'

export default function LegacyPreparePage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const datasetId = searchParams.get('datasetId')

  useEffect(() => {
    // Track migration for analytics
    if (datasetId) {
      console.warn('[DEPRECATED] /prepare?datasetId=X will be removed in Phase 4. Use /datasets/[id]/prepare instead.')
      
      // Redirect with 302
      router.replace(`/datasets/${datasetId}/prepare`)
    } else {
      router.replace('/upload')
    }
  }, [datasetId, router])

  // Loading state while redirecting
  return (
    <div className="flex items-center justify-center h-full">
      <Loader2 className="w-8 h-8 animate-spin" />
    </div>
  )
}

// /apps/frontend/app/datasets/[id]/prepare/page.tsx (NEW)
'use client'
import { useParams } from 'next/navigation'
import PreparePageContent from '@/components/PreparePageContent'

export default function DatasetPreparePage() {
  const params = useParams()
  const datasetId = params.id as string

  return <PreparePageContent datasetId={datasetId} />
}
```

### Deprecation Timeline
```
Phase 3a (Now): /prepare → 302 redirects to /datasets/[id]/prepare
Phase 3b (Month 3): Track % usage, consider extending if >5%
Phase 4 (Month 6): Remove /prepare completely
```

---

## API Integration Summary

### Required API Endpoints

1. **GET** `/datasets/{datasetId}`
   - Returns: Dataset metadata (columns, row count, etc.)
   - Used: Load dataset info in ColumnSelector

2. **GET** `/datasets/{datasetId}/preview?rows=100`
   - Returns: Data preview (first N rows)
   - Used: Initial preview panel

3. **POST** `/transformations/preview`
   - Request: dataset_id, transformations array
   - Returns: Transformed data preview + impact metrics
   - Used: Preview button

4. **POST** `/transformations/apply`
   - Request: dataset_id, transformations array
   - Returns: transformed_dataset_id, row_count, schema
   - Used: Apply & Continue button

5. **GET** `/recipes?dataset_id={id}`
   - Returns: List of saved transformation recipes
   - Used: Recipe Manager

6. **POST** `/recipes/save`
   - Request: name, description, transformations, dataset_id
   - Returns: recipe_id
   - Used: Save recipe button

### Error Handling
```typescript
// API call wrapper with toast notifications
const makeApiCall = async (url: string, options: any) => {
  try {
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${await getAuthToken()}`,
        ...options.headers
      },
      ...options
    })
    
    if (!response.ok) {
      const error = await response.json()
      showErrorToast(error.message || 'Request failed')
      throw new Error(error.message)
    }
    
    return await response.json()
  } catch (error) {
    console.error(error)
    throw error
  }
}
```

---

## File Structure Summary

```
apps/frontend/
├─ app/
│  ├─ prepare/page.tsx (UPDATED: redirect)
│  └─ datasets/[id]/
│     └─ prepare/
│        └─ page.tsx (NEW: wrapper)
│
├─ components/
│  └─ transformation/
│     ├─ TransformationPipeline.tsx (EXISTING: enhanced)
│     ├─ ColumnSelector.tsx (NEW)
│     ├─ TransformationConfigDialog.tsx (NEW)
│     ├─ TransformationChainView.tsx (NEW)
│     ├─ PreparePageContent.tsx (NEW: wrapper/orchestrator)
│     ├─ RecipeManager.tsx (EXISTING)
│     ├─ PreviewPanel.tsx (EXISTING)
│     └─ TransformationSidebar.tsx (EXISTING)
│
├─ lib/
│  ├─ contexts/
│  │  └─ WorkflowContext.tsx (UPDATED: dataset routing)
│  │
│  └─ hooks/
│     ├─ useColumnList.ts (NEW: fetch + cache columns)
│     ├─ useTransformationPreview.ts (NEW: debounced preview)
│     └─ useUnsavedChanges.ts (NEW: prompt on route change)
│
└─ types/
   └─ transformation.ts (NEW: interfaces)
```

---

## Deployment Checklist

- [ ] Code review: Phase 3 design & implementation
- [ ] Unit tests: 85%+ coverage for new components
- [ ] E2E tests: Core workflows pass
- [ ] Accessibility audit: WCAG 2.1 AA compliance
- [ ] Performance testing: Load <2s, column search <200ms
- [ ] Backward compatibility: /prepare?datasetId=X still works
- [ ] Documentation: Update CLAUDE.md with new routes
- [ ] Analytics setup: Track migration from old to new route
- [ ] User communication: Deprecation notice + timeline
- [ ] Rollback plan: Revert to dual routes if issues arise

---

## Success Criteria

**Functional**:
1. ✅ Route migration: /prepare → /datasets/[id]/prepare complete
2. ✅ ColumnSelector: Supports 1000+ columns with <200ms search
3. ✅ TransformationConfigDialog: Dynamic forms for all 30+ transformation types
4. ✅ TransformationChainView: Linear reordering and keyboard navigation
5. ✅ View switching: ReactFlow ↔ ChainView without data loss
6. ✅ Backward compatibility: Old route redirects correctly

**Quality**:
1. ✅ Test coverage: 85%+ for all new components
2. ✅ Accessibility: WCAG 2.1 AA (keyboard nav, ARIA, focus management)
3. ✅ Performance: Initial load <2s, transformation preview <500ms
4. ✅ Type safety: Full TypeScript coverage (no `any` types)

**User Experience**:
1. ✅ Workflow progression: Users advance to next stage on completion
2. ✅ Unsaved changes prompt: Prevents accidental data loss
3. ✅ Error messaging: Clear, actionable error messages
4. ✅ Mobile responsive: Works on mobile (ChainView as default)

---

## Next Steps (Phase 4)

1. **Implementation Sprint 1**: ColumnSelector + TransformationChainView
2. **Implementation Sprint 2**: TransformationConfigDialog + PreparePageContent
3. **Integration Sprint**: Sync with TransformationPipeline + testing
4. **QA Sprint**: E2E, accessibility, performance validation
5. **Deployment**: Stage to production with analytics monitoring
6. **Cleanup Phase**: Monitor usage and schedule /prepare deprecation

