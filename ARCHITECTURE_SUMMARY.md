# Architecture Summary - Data Preparation Enhancement

**Status**: Phase 3 Architecture Review Complete
**Date**: 2025-12-17
**Document**: `ARCHITECTURE_PHASE3.md` (1,169 lines)

---

## Quick Reference

### Executive Summary

Restructure the data preparation interface from global `/prepare` route to dataset-specific `/datasets/[id]/prepare`, introducing three new components (ColumnSelector, TransformationConfigDialog, TransformationChainView) while maintaining backward compatibility.

**Key Improvements**:
1. Route-driven state management (dataset ID in URL)
2. Dual-interface pattern (ReactFlow visual + linear chain for accessibility)
3. Progressive disclosure (modal dialogs for configuration)
4. WCAG 2.1 AA accessibility compliance

---

## Route Migration Path

```
CURRENT (Phase 1-2):
  /prepare?datasetId=XYZ
    ├─ useSearchParams() to get datasetId
    ├─ WorkflowContext for state
    └─ No dataset scope

        ↓ DUAL-ROUTE STRATEGY

PHASE 3a (Immediate):
  /prepare?datasetId=XYZ → 302 redirect → /datasets/XYZ/prepare (NEW)
  + Keep old route working (backward compat)
  + Log deprecation warnings

PHASE 3b (Month 3):
  Monitor usage on old route
  Maintain if >5% traffic, else proceed

PHASE 4 (Month 6):
  /prepare → REMOVED
  All traffic on /datasets/[id]/prepare
```

---

## Component Architecture

### Component Tree

```
PreparePageContent (NEW - Orchestrator)
│
├─ Header
│  ├─ Title + Breadcrumb
│  ├─ Dataset Info Badge
│  └─ View Mode Toggle (Pipeline ↔ Chain)
│
├─ Left Sidebar (300px)
│  ├─ ColumnSelector (NEW)
│  │  ├─ Search Input (debounced, keyboard nav)
│  │  ├─ Virtualized Column List (1000+ cols)
│  │  ├─ Selection Counter
│  │  └─ Select All / Deselect All
│  │
│  └─ Transformation Library
│     ├─ 30+ Types (categorized)
│     ├─ Drag source (for ReactFlow)
│     └─ Click-to-add (for ChainView)
│
├─ Main Canvas (flex-1)
│  ├─ IF (view === 'pipeline'):
│  │  └─ TransformationPipeline (EXISTING)
│  │     └─ onNodeClick → open ConfigDialog
│  │
│  └─ IF (view === 'chain'):
│     └─ TransformationChainView (NEW)
│        ├─ Linear step list with arrows
│        ├─ Reorder (keyboard + buttons)
│        └─ onClick step → open ConfigDialog
│
├─ ConfigDialog (Modal - NEW)
│  ├─ Dynamic Form (based on transformation type)
│  ├─ Column Selector (if applicable)
│  ├─ Preview (if supported)
│  └─ Save / Cancel / Delete
│
├─ Right Panel (300px, collapsible)
│  ├─ Preview Panel
│  │  ├─ Before/After Table
│  │  ├─ Schema Diff
│  │  ├─ Quality Metrics
│  │  └─ Row Count Diff
│  │
│  └─ Properties (when step selected)
│     ├─ Transformation Badge
│     ├─ Columns List
│     └─ Quick Params
│
└─ Toolbar
   ├─ Preview Button
   ├─ Apply & Continue Button
   ├─ Recipe Manager
   ├─ Export Code
   └─ Undo / Redo
```

### New Components (Phase 3)

#### 1. ColumnSelector
- **File**: `components/transformation/ColumnSelector.tsx`
- **Purpose**: Multi-select column list with search
- **Features**:
  - Search: debounced, <200ms for 1K columns
  - Virtualization: handles 1000+ columns
  - Keyboard: ArrowUp/Down, Space, Ctrl+A
  - Accessibility: ARIA listbox, screen reader support

#### 2. TransformationConfigDialog
- **File**: `components/transformation/TransformationConfigDialog.tsx`
- **Purpose**: Modal for transformation parameter configuration
- **Features**:
  - Dynamic form rendering (based on type)
  - Column selection (if applicable)
  - Validation + error messages
  - Focus trap + Escape to close
  - Delete option with confirmation

#### 3. TransformationChainView
- **File**: `components/transformation/TransformationChainView.tsx`
- **Purpose**: Linear transformation pipeline (accessible alternative to ReactFlow)
- **Features**:
  - Step list with reorder buttons (↑ ↓)
  - Keyboard: Alt+Up/Down to reorder
  - Drag-and-drop (optional for mouse users)
  - Click to select → shows ConfigDialog
  - Delete with confirmation

---

## State Management

### Single Source of Truth (PreparePageContent)

```typescript
const [transformations, setTransformations] = useState<TransformationStep[]>([])
const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set())
const [preview, setPreview] = useState<PreviewData | null>(null)
const [view, setView] = useState<'pipeline' | 'chain'>('pipeline')
const [unsavedChanges, setUnsavedChanges] = useState(false)
const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
```

### State Flow

```
User selects columns
  ↓
ColumnSelector emits onSelectionChange
  ↓
PreparePageContent updates selectedColumns state
  ↓
User clicks transformation in library
  ↓
Add to transformations array
  ↓
Both views (ReactFlow + ChainView) render same data
  ↓
User edits transformation
  ↓
ConfigDialog emits onSave
  ↓
PreparePageContent updates transformations[i]
  ↓
Both views re-render consistently
```

### Synchronization Between Views

```
CHALLENGE: User switches between ReactFlow (visual) and ChainView (linear)
SOLUTION:  Single transformations array, different UI renderers

transformations = [
  { id: 'step-1', type: 'remove_duplicates', ... },
  { id: 'step-2', type: 'fill_missing', ... },
  { id: 'step-3', type: 'scale', ... }
]

Both views read/write to this array:

ReactFlow View:          ChainView:
  [Node 1]                Step 1 ▲ ▼
  [Node 2]          ↔     Step 2 ▲ ▼
  [Node 3]                Step 3 ▲ ▼

Same data, different UX
```

---

## Accessibility Strategy

### WCAG 2.1 AA Compliance

#### Keyboard Navigation Map

```
TAB ORDER (Sequential Focus):
1. Header: Title → Mode Toggle
2. Sidebar: Search Input → Column List → Select All
3. Main Canvas: Transformation Step → Delete Button
4. Toolbar: Preview → Apply → Recipe → Export

ARROW KEYS:
  Within ColumnSelector: ArrowUp/Down navigate column list
  Within ChainView: (N/A - Tab only for steps)

SHORTCUTS:
  Ctrl+Z        → Undo transformation
  Ctrl+Shift+Z  → Redo transformation
  Alt+ArrowUp   → Move step up in chain
  Alt+ArrowDown → Move step down in chain
  Escape        → Close dialog
  Enter         → Save dialog / Activate button

COLUMN SELECTOR:
  Space         → Toggle checkbox
  Ctrl+A        → Select all visible
  Shift+Ctrl+A  → Deselect all
```

#### ARIA Labels & Roles

```html
<!-- ColumnSelector -->
<div role="region" aria-labelledby="column-title" aria-live="polite">
  <h2 id="column-title">Select Columns</h2>
  <ul role="listbox" aria-multiselectable="true">
    <li role="option" aria-selected="true">column_name</li>
  </ul>
</div>

<!-- TransformationChainView -->
<ol role="list" aria-label="Transformation pipeline">
  <li role="listitem" aria-posinset="1" aria-setsize="3">
    <button aria-current="step">Step 1: remove_duplicates</button>
    <button aria-label="Move step 1 up" aria-keyshortcuts="Alt+ArrowUp">▲</button>
    <button aria-label="Move step 1 down" aria-keyshortcuts="Alt+ArrowDown">▼</button>
  </li>
</ol>

<!-- TransformationConfigDialog -->
<dialog aria-labelledby="dialog-title" aria-modal="true">
  <h2 id="dialog-title">Configure Transformation</h2>
  <!-- Focus trap + Escape handling -->
</dialog>
```

#### Screen Reader Testing
- NVDA (Windows)
- JAWS (Windows)
- VoiceOver (macOS, iOS)
- TalkBack (Android)

---

## Risk Assessment

| Risk | Severity | Probability | Mitigation |
|------|----------|-------------|-----------|
| Breaking existing `/prepare` users | HIGH | MEDIUM | 302 redirect with analytics, 6-month grace period |
| Performance with 100+ step pipelines | MEDIUM | HIGH | Virtualization for ChainView, lazy-load configs |
| Accessibility gaps | HIGH | MEDIUM | WCAG 2.1 AA testing, keyboard-only workflows |
| State sync between views | MEDIUM | MEDIUM | Single source of truth, comprehensive unit tests |
| Large column lists (1000+) | MEDIUM | HIGH | Virtualize ColumnSelector, debounced search |
| Mobile/touch usability | LOW-MEDIUM | MEDIUM | ChainView default on mobile, 44px targets |

---

## File Changes Summary

### New Files
```
components/transformation/
  ├─ ColumnSelector.tsx (NEW)
  ├─ TransformationConfigDialog.tsx (NEW)
  ├─ TransformationChainView.tsx (NEW)
  └─ PreparePageContent.tsx (NEW - orchestrator)

app/datasets/[id]/
  └─ prepare/page.tsx (NEW)

lib/hooks/
  ├─ useColumnList.ts (NEW)
  ├─ useTransformationPreview.ts (NEW)
  └─ useUnsavedChanges.ts (NEW)

lib/types/
  └─ transformation.ts (NEW - interfaces)
```

### Modified Files
```
app/prepare/page.tsx (UPDATED: redirect to new route)
lib/contexts/WorkflowContext.tsx (UPDATED: dataset-specific routing)
components/transformation/TransformationPipeline.tsx (ENHANCED: dialog integration)
```

---

## Backward Compatibility

### Migration Timeline

```
PHASE 3a (Now):
  ✓ Create /datasets/[id]/prepare route
  ✓ Keep /prepare?datasetId=X working
  ✓ Redirect with 302 status + analytics log

PHASE 3b (Month 3):
  ✓ Monitor: % traffic on old vs new route
  ✓ Decision: If <5% on old route, proceed to Phase 4
  ✓ Otherwise: Extend grace period

PHASE 4 (Month 6):
  ✓ Remove /prepare completely
  ✓ 410 Gone status code
```

### Deprecation Warnings

```typescript
// In old /prepare route
if (datasetId) {
  console.warn('[DEPRECATED] /prepare?datasetId=X will be removed in Phase 4. Use /datasets/[id]/prepare instead.')
  analytics.trackEvent('prepare_route_redirect', {
    from: '/prepare',
    to: `/datasets/${datasetId}/prepare`,
    timestamp: new Date().toISOString()
  })
}
```

---

## Testing Strategy

### Unit Tests (Jest)
```
ColumnSelector.test.tsx
  ✓ Renders search + column list
  ✓ Search filters <200ms for 1K cols
  ✓ Selection updates parent
  ✓ Keyboard nav works (ArrowUp/Down, Space)
  ✓ Virtualization renders visible items

TransformationConfigDialog.test.tsx
  ✓ Renders form for each transformation type
  ✓ Validates required fields
  ✓ Focus trap prevents Tab escape
  ✓ Escape closes dialog
  ✓ Delete works with confirmation

TransformationChainView.test.tsx
  ✓ Renders steps in order
  ✓ Reorder via arrow buttons
  ✓ Reorder via drag-and-drop
  ✓ Delete removes step
  ✓ Keyboard nav (Alt+Up/Down)

PreparePageContent.test.tsx
  ✓ Loads dataset metadata on mount
  ✓ Syncs state between views
  ✓ Unsaved changes prompt
  ✓ Completes workflow stage on apply
```

### E2E Tests (Playwright)
```
data-preparation.spec.ts
  ✓ User navigates to /datasets/[id]/prepare
  ✓ User selects columns
  ✓ User adds transformation
  ✓ User configures transformation
  ✓ User previews changes
  ✓ User applies transformations
  ✓ User advances to next stage
  ✓ User switches between views
  ✓ Keyboard-only workflow (no mouse)
  ✓ Unsaved changes warning appears
```

### Accessibility Tests
```
✓ axe-core automated scans
✓ WAVE manual review
✓ NVDA/JAWS keyboard navigation
✓ VoiceOver/TalkBack mobile
✓ Focus visible indicators
✓ Color contrast ratios (WCAG AA)
```

---

## Success Criteria

### Functional ✅
- Route migration: /prepare → /datasets/[id]/prepare complete
- ColumnSelector: 1000+ columns with <200ms search
- TransformationConfigDialog: Dynamic forms for all 30+ types
- TransformationChainView: Linear reordering + keyboard nav
- View switching: ReactFlow ↔ ChainView without data loss
- Backward compatibility: Old route redirects correctly

### Quality ✅
- Test coverage: 85%+ for all new components
- Accessibility: WCAG 2.1 AA compliance
- Performance: Initial load <2s, preview <500ms
- Type safety: Full TypeScript (no `any` types)

### User Experience ✅
- Workflow progression: Users advance on completion
- Unsaved changes prompt: Prevents data loss
- Error messaging: Clear, actionable messages
- Mobile responsive: ChainView default on mobile

---

## API Integration Points

### Required Backend Endpoints

1. **GET** `/datasets/{datasetId}`
   - Dataset metadata (columns, row count)

2. **GET** `/datasets/{datasetId}/preview?rows=100`
   - Data preview (first N rows)

3. **POST** `/transformations/preview`
   - Apply transformations + return preview

4. **POST** `/transformations/apply`
   - Apply transformations + return result

5. **GET** `/recipes?dataset_id={id}`
   - List saved recipes

6. **POST** `/recipes/save`
   - Save transformation recipe

---

## Implementation Phases

### Phase 3: Architecture & Design (Current)
- ✅ Constraint analysis
- ✅ Route migration strategy
- ✅ Component specifications
- ✅ Accessibility audit
- ✅ Risk assessment

### Phase 4: Implementation
- Sprint 1: ColumnSelector + TransformationChainView
- Sprint 2: TransformationConfigDialog + PreparePageContent
- Sprint 3: Integration + testing
- Sprint 4: QA + deployment

### Phase 5: Monitoring & Cleanup
- Monitor old route traffic
- Plan deprecation cutover
- Remove legacy route

---

## Key Files & Links

| Document | Location | Purpose |
|----------|----------|---------|
| Full Architecture | `/ARCHITECTURE_PHASE3.md` | Complete 1,169-line design document |
| This Summary | `/ARCHITECTURE_SUMMARY.md` | Quick reference guide |
| Project Guide | `/CLAUDE.md` | Project conventions & standards |

---

## Next Steps

1. **Review**: Get stakeholder approval on this architecture
2. **Plan**: Break Phase 4 into implementation sprints
3. **Implement**: Build components in dependency order
4. **Test**: Unit + E2E + accessibility testing
5. **Deploy**: Staged rollout with analytics monitoring
6. **Monitor**: Track migration from old to new route

---

**Generated**: 2025-12-17
**Architecture Expert**: System Architecture Review Workflow
**Status**: Ready for Phase 4 Implementation
