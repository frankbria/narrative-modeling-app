# Component Architecture Diagrams

## Overall Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Data Preparation - Dataset: sales_data.csv (10,000 rows, 25 columns)   │
│  [Explore] > [Prepare]                         Pipeline View | Chain View│
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┬─────────────────────────────────────┬────────────────────┐
│              │                                     │                    │
│  SIDEBAR     │         MAIN CANVAS                 │  PREVIEW PANEL     │
│  (300px)     │        (Flex-1)                     │   (300px)          │
│              │                                     │                    │
│  ┌─────────┐ │                                     │  ┌──────────────┐  │
│  │ Column  │ │        [Pipeline View]             │  │   Before     │  │
│  │         │ │    ┌──────────────────┐             │  │              │  │
│  │ Selector│ │    │ Remove Duplicates│             │  │  ID  Name    │  │
│  │         │ │    │   Parameters:    │             │  │  ── ──────   │  │
│  │ [Search]│ │    │ - Cols: id,name  │             │  │   1  John    │  │
│  │         │ │    │ - Keep: first    │             │  │   2  Sarah   │  │
│  │ ┌─────┐ │ │    └──────────────────┘             │  │   3  Mike    │  │
│  │ │ id  │ │ │             ↓                       │  └──────────────┘  │
│  │ ├─────┤ │ │    ┌──────────────────┐             │  ┌──────────────┐  │
│  │ │name ├─┼─┤    │  Fill Missing    │             │  │   After      │  │
│  │ ├─────┤ │ │    │   Parameters:    │             │  │              │  │
│  │ │age  │ │ │    │ - Col: age       │             │  │  ID  Name    │  │
│  │ ├─────┤ │ │    │ - Method: mean   │             │  │  ── ──────   │  │
│  │ │ ... │ │ │    └──────────────────┘             │  │   1  John    │  │
│  │ └─────┘ │ │             ↓                       │  │   2  Sarah   │  │
│  │         │ │    ┌──────────────────┐             │  │   2  Mike    │  │
│  │ [+] All │ │    │     Scale        │             │  └──────────────┘  │
│  │ [-] None│ │    │   Parameters:    │             │  Rows: 10,000      │
│  │         │ │    │ - Cols: age,income
 │             │  Quality: 98.5%     │  │
│  └─────────┘ │    │ - Method: standard
 │             │  Columns: 24       │  │
│              │    └──────────────────┘             │                    │
│              │                                     │  ┌──────────────┐  │
│              │  [Preview] [Apply & Continue]      │  │   Schema Diff│  │
│              │  [Save Recipe] [Undo] [Redo]       │  │ - Removed: 0 │  │
│              │  [Export Code]                      │  │ - Added: 0   │  │
│              │                                     │  │ - Modified: 1│  │
│              │                                     │  └──────────────┘  │
│              │                                     │                    │
└──────────────┴─────────────────────────────────────┴────────────────────┘

Legend:
  ┌─────┐ = Component boundary
  ├─────┤ = Component content
  → = Data flow
  ↓ = Sequence flow
```

---

## PreparePageContent State Tree

```
PreparePageContent
├─ State
│  ├─ selectedColumns: Set<string>
│  │  └─ {"id", "name", "age", "email"}
│  │
│  ├─ transformations: TransformationStep[]
│  │  ├─ [0] { id: "step-1", type: "remove_duplicates", ... }
│  │  ├─ [1] { id: "step-2", type: "fill_missing", ... }
│  │  └─ [2] { id: "step-3", type: "scale", ... }
│  │
│  ├─ view: 'pipeline' | 'chain'
│  │  └─ Current view mode
│  │
│  ├─ selectedNodeId: string | null
│  │  └─ Currently selected transformation
│  │
│  ├─ preview: PreviewData | null
│  │  ├─ rows: Array<Record<string, any>>
│  │  ├─ schema: Column[]
│  │  └─ metadata: { totalRows, quality, ... }
│  │
│  ├─ unsavedChanges: boolean
│  │  └─ Triggers beforeunload prompt
│  │
│  └─ isLoading: boolean
│     └─ API call in progress
│
├─ Context (WorkflowContext)
│  ├─ state.datasetId
│  ├─ state.currentStage
│  ├─ canAccessStage()
│  └─ completeStage()
│
├─ Children
│  ├─ ColumnSelector (receives selectedColumns state)
│  │  └─ Emits: onSelectionChange(Set<string>)
│  │
│  ├─ TransformationPipeline or TransformationChainView
│  │  ├─ Receives: transformations[], view, selectedNodeId
│  │  └─ Emits: onNodeClick, onNodeUpdate, onDelete, onReorder
│  │
│  ├─ TransformationConfigDialog (modal)
│  │  ├─ Receives: isOpen, transformation, availableColumns
│  │  └─ Emits: onSave, onCancel, onDelete
│  │
│  └─ PreviewPanel
│     └─ Receives: preview, isLoading
│
└─ Event Handlers
   ├─ handleLoadDataset() → fetch metadata
   ├─ handleSelectColumns() → update selectedColumns
   ├─ handleAddTransformation() → append to array
   ├─ handleUpdateTransformation() → modify array[i]
   ├─ handleDeleteTransformation() → remove from array
   ├─ handleReorderTransformation() → reorder array
   ├─ handlePreviewTransformation() → API call
   ├─ handleApplyTransformations() → API call + completeStage()
   └─ handleBeforeUnload() → prompt if unsavedChanges
```

---

## ColumnSelector Component Flow

```
ColumnSelector (Props: datasetId, selectedColumns, onSelectionChange, ...)
│
├─ State
│  ├─ searchTerm: string
│  │  └─ User's search input
│  │
│  ├─ columns: Column[]
│  │  └─ All available columns (fetched once)
│  │
│  └─ filteredColumns: Column[]
│     └─ Filtered by search term (debounced 200ms)
│
├─ Effects
│  ├─ useEffect(() => fetchColumns(datasetId), [datasetId])
│  │  └─ Load column list on mount
│  │
│  └─ useEffect(() => debouncedSearch(searchTerm), [searchTerm])
│     └─ Filter after 200ms debounce
│
├─ Render
│  ├─ <div role="region" aria-labelledby="selector-title">
│  │  ├─ <h2>Select Columns</h2>
│  │  │
│  │  ├─ <input type="search" placeholder="Search..."/>
│  │  │  ├─ aria-label="Search columns"
│  │  │  ├─ onChange → setSearchTerm()
│  │  │  └─ keyboard: ArrowUp/Down navigate list
│  │  │
│  │  ├─ <FixedSizeList height={400} itemCount={filteredColumns.length}>
│  │  │  │  (Virtualized for performance)
│  │  │  │
│  │  │  └─ {({ index, style }) => (
│  │  │     ├─ <li role="option" style={style}>
│  │  │     ├─ <input type="checkbox"
│  │  │     │  ├─ checked={selectedColumns.has(column)}
│  │  │     │  └─ onChange → emit onSelectionChange()
│  │  │     ├─ <label>{column.name}</label>
│  │  │     └─ </li>
│  │  │  )}
│  │  │
│  │  ├─ <div className="controls">
│  │  │  ├─ <button>Select All ({filteredColumns.length})</button>
│  │  │  │  └─ onClick → emit onSelectionChange(allFiltered)
│  │  │  │
│  │  │  └─ <button>Deselect All</button>
│  │  │     └─ onClick → emit onSelectionChange(emptySet)
│  │  │
│  │  ├─ <span className="count">
│  │  │  └─ {selectedColumns.size} selected
│  │  │
│  │  └─ {isLoading && <Spinner />}
│  │
│  └─ </div>
│
└─ Event Handlers
   ├─ handleSearchChange(term) → setSearchTerm(term)
   ├─ handleColumnToggle(column) → {
   │  └─ newSelected = selectedColumns
   │     newSelected.has(column) ? remove : add
   │     onSelectionChange(newSelected)
   │  }
   ├─ handleSelectAll() → onSelectionChange(allFiltered)
   ├─ handleDeselectAll() → onSelectionChange(emptySet)
   │
   └─ Keyboard Handlers:
      ├─ ArrowUp/Down → Navigate column list
      ├─ Space → Toggle current checkbox
      ├─ Ctrl+A → Select all visible
      └─ Shift+Ctrl+A → Deselect all
```

---

## TransformationChainView Component Flow

```
TransformationChainView (Props: transformations[], selectedStepId, onStepClick, ...)
│
├─ Props Received
│  ├─ transformations: [
│  │   { id: "step-1", type: "remove_duplicates", ... },
│  │   { id: "step-2", type: "fill_missing", ... },
│  │   { id: "step-3", type: "scale", ... }
│  │ ]
│  ├─ selectedStepId: "step-2" | null
│  ├─ onStepClick(stepId) → parent callback
│  ├─ onStepReorder(fromIndex, toIndex) → parent callback
│  ├─ onStepDelete(stepId) → parent callback
│  └─ onStepEdit(stepId, config) → parent callback
│
├─ Render: <ol role="list" aria-label="Transformation pipeline">
│
│  └─ transformations.map((step, index) => (
│     ├─ <li role="listitem" aria-posinset={index+1} aria-setsize={transformations.length}>
│     │  ├─ <div className="step-container">
│     │  │  ├─ <button
│     │  │  │  ├─ onClick={() => onStepClick(step.id)}
│     │  │  │  ├─ className={selectedStepId === step.id ? 'selected' : ''}
│     │  │  │  ├─ aria-current={selectedStepId === step.id ? 'step' : undefined}
│     │  │  │  ├─ aria-label={`Step ${index+1}: ${step.type}`}
│     │  │  │  └─ textContent: `${index+1}. ${step.type}`
│     │  │  │
│     │  │  ├─ <div className="step-info">
│     │  │  │  ├─ Column(s): {step.columns?.join(', ')}
│     │  │  │  └─ Params: {...step.parameters}
│     │  │  │
│     │  │  ├─ <div className="controls">
│     │  │  │  ├─ <button
│     │  │  │  │  ├─ disabled={index === 0}
│     │  │  │  │  ├─ aria-label={`Move step ${index+1} up`}
│     │  │  │  │  ├─ aria-keyshortcuts="Alt+ArrowUp"
│     │  │  │  │  ├─ onClick={() => onStepReorder(index, index-1)}
│     │  │  │  │  └─ textContent: "▲"
│     │  │  │  │
│     │  │  │  ├─ <button
│     │  │  │  │  ├─ disabled={index === transformations.length-1}
│     │  │  │  │  ├─ aria-label={`Move step ${index+1} down`}
│     │  │  │  │  ├─ aria-keyshortcuts="Alt+ArrowDown"
│     │  │  │  │  ├─ onClick={() => onStepReorder(index, index+1)}
│     │  │  │  │  └─ textContent: "▼"
│     │  │  │  │
│     │  │  │  ├─ <button
│     │  │  │  │  ├─ aria-label={`Edit step ${index+1}`}
│     │  │  │  │  ├─ onClick={() => onStepClick(step.id)} (opens dialog)
│     │  │  │  │  └─ textContent: "✎ Edit"
│     │  │  │  │
│     │  │  │  └─ <button
│     │  │  │     ├─ aria-label={`Delete step ${index+1}`}
│     │  │  │     ├─ onClick={() => {
│     │  │  │     │   if (confirm("Delete this step?")) {
│     │  │  │     │     onStepDelete(step.id)
│     │  │  │     │   }
│     │  │  │     │ }}
│     │  │  │     └─ textContent: "✕"
│     │  │  │
│     │  │  └─ </div>
│     │  │
│     │  └─ </div>
│     │
│     └─ </li>
│  ))
│
└─ Keyboard Handlers (in parent PreparePageContent)
   ├─ Tab → Move focus to next step
   ├─ Shift+Tab → Move focus to previous step
   ├─ Enter (on selected step) → Show ConfigDialog
   ├─ Delete (on selected step) → Delete with confirmation
   ├─ Alt+ArrowUp (on selected step) → Move up in chain
   └─ Alt+ArrowDown (on selected step) → Move down in chain
```

---

## TransformationConfigDialog Component Flow

```
TransformationConfigDialog (Modal - Overlay)
│
├─ Props
│  ├─ isOpen: boolean
│  ├─ transformation?: TransformationStep | null (for edit)
│  ├─ transformationType?: string | null (for new)
│  ├─ availableColumns: string[]
│  ├─ onSave(config) → parent callback
│  ├─ onCancel() → parent callback
│  └─ onDelete?(stepId) → parent callback
│
├─ State
│  ├─ formData: Record<string, any>
│  │  └─ Mirrors current transformation parameters
│  │
│  └─ validationErrors: Record<string, string>
│     └─ Field-level error messages
│
├─ Effects
│  ├─ useEffect(() => {
│  │  if (isOpen) firstInputRef.current?.focus()
│  │}, [isOpen])
│  │ Focus first input on open
│  │
│  └─ useEffect(() => {
│     if (isOpen && transformation) setFormData(transformation.parameters)
│    }, [isOpen, transformation])
│    Initialize form with existing data
│
├─ Render (if !isOpen) → null
│
├─ Render (if isOpen):
│  └─ <dialog open aria-labelledby="dialog-title" aria-modal="true">
│     ├─ <div className="dialog-content">
│     │  ├─ <h2 id="dialog-title">Configure Transformation</h2>
│     │  │  └─ textContent: transformationType or transformation.type
│     │  │
│     │  ├─ <form>
│     │  │  │
│     │  │  ├─ Dynamic Form (based on transformationType):
│     │  │  │
│     │  │  ├─ IF type === 'remove_duplicates':
│     │  │  │  ├─ <label>Columns to Consider</label>
│     │  │  │  ├─ <input type="checkbox" />Column: id
│     │  │  │  ├─ <input type="checkbox" />Column: name
│     │  │  │  └─ ...
│     │  │  │
│     │  │  ├─ IF type === 'fill_missing':
│     │  │  │  ├─ <label>Target Column</label>
│     │  │  │  ├─ <select onChange={e => setFormData({...})}>
│     │  │  │  │  ├─ <option>- Select column -</option>
│     │  │  │  │  ├─ <option value="age">age</option>
│     │  │  │  │  └─ ...
│     │  │  │  │
│     │  │  │  ├─ <label>Fill Method</label>
│     │  │  │  ├─ <select>
│     │  │  │  │  ├─ <option value="value">Specific Value</option>
│     │  │  │  │  ├─ <option value="mean">Mean</option>
│     │  │  │  │  ├─ <option value="median">Median</option>
│     │  │  │  │  └─ ...
│     │  │  │  │
│     │  │  │  └─ IF formData.method === 'value':
│     │  │  │     ├─ <label>Fill Value</label>
│     │  │  │     └─ <input type="text" placeholder="0" />
│     │  │  │
│     │  │  ├─ IF type === 'scale':
│     │  │  │  ├─ <label>Target Columns</label>
│     │  │  │  ├─ <input type="checkbox" />Column: age
│     │  │  │  ├─ <input type="checkbox" />Column: income
│     │  │  │  └─ ...
│     │  │  │
│     │  │  │  ├─ <label>Scaling Method</label>
│     │  │  │  ├─ <select>
│     │  │  │  │  ├─ <option value="minmax">Min-Max</option>
│     │  │  │  │  ├─ <option value="standard">Standard (Z-score)</option>
│     │  │  │  │  └─ <option value="robust">Robust</option>
│     │  │  │  │
│     │  │  │  └─ </select>
│     │  │  │
│     │  │  ├─ ... (more conditional fields)
│     │  │  │
│     │  │  └─ <div className="form-actions">
│     │  │     ├─ <button type="submit" onClick={handleSave}>
│     │  │     │  └─ Save
│     │  │     │
│     │  │     ├─ <button type="button" onClick={onCancel}>
│     │  │     │  └─ Cancel
│     │  │     │
│     │  │     └─ IF transformation (editing):
│     │  │        └─ <button type="button" onClick={handleDelete} className="danger">
│     │  │           └─ Delete Step
│     │  │
│     │  └─ </form>
│     │
│     ├─ Focus trap handlers:
│     │  ├─ onKeyDown: if (key === 'Tab' && isLastFocusable) focus(first)
│     │  └─ onKeyDown: if (key === 'Escape') onCancel()
│     │
│     └─ </dialog>
│
└─ Event Handlers
   ├─ handleSave() → {
   │  if (!validate(formData)) return setValidationErrors(...)
   │  newStep = { ...transformation, parameters: formData }
   │  onSave(newStep)
   │  }
   ├─ handleCancel() → onCancel()
   └─ handleDelete() → {
      if (confirm("Delete this step?")) onDelete(step.id)
     }
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERACTIONS                             │
└─────────────────────────────────────────────────────────────────────────┘

    User selects columns        User adds transformation      User applies
         ↓                              ↓                           ↓
    ColumnSelector          TransformationLibrary        ApplyButton
    emission: onSelectionChange    emission: onAdd         emission: onClick
         │                            │                           │
         ├─────────────────────┬──────┴───────────────────────────┤
         │                     │                                  │
         ↓                     ↓                                  ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │           PreparePageContent (State Orchestrator)               │
    ├─────────────────────────────────────────────────────────────────┤
    │ handleSelectColumns(columns) → setSelectedColumns(columns)     │
    │ handleAddTransformation(type) → setTransformations([..., new])  │
    │ handleApplyTransformations() → {                               │
    │   API call to /transformations/apply                           │
    │   completeStage(DATA_PREPARATION, { ... })                    │
    │   Router advances to FEATURE_ENGINEERING stage                │
    │ }                                                              │
    └─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ├──────────────┴──────────────┴──────────────┘
         │
         ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │ Re-render triggered with new state                              │
    └─────────────────────────────────────────────────────────────────┘
         │
    ┌────┴───────────────────────────────────────────────────────────┐
    │                                                                 │
    ↓                                  ↓                              ↓
 ColumnSelector                   VIEW: Pipeline OR Chain      Preview Panel
 └─ Show updated                  ├─ TransformationPipeline    └─ Update preview
    selected count                 │  (ReactFlow visual)
                                  └─ TransformationChainView
    User clicks                       (Linear alternative)
    transformation step              │
         │                       User clicks step
         │                            │
         ├─────────────────────────────┘
         │
         ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │ handleStepClick(stepId) → setSelectedNodeId(stepId)             │
    │                        → show ConfigDialog                      │
    └─────────────────────────────────────────────────────────────────┘
         │
         ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │ TransformationConfigDialog (Modal Opens)                        │
    ├─────────────────────────────────────────────────────────────────┤
    │ User updates parameters and clicks Save                         │
    │ handleSave(config) → onSave callback to parent                 │
    └─────────────────────────────────────────────────────────────────┘
         │
         ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │ handleUpdateTransformation(stepId, config)                      │
    │ setTransformations([...transformed...])                         │
    │ setUnsavedChanges(true)                                         │
    └─────────────────────────────────────────────────────────────────┘
         │
         ↓
    Both views (Pipeline & Chain) re-render with updated transformations
```

---

## State Persistence & Navigation

```
User Journey:

  1. Navigate to /datasets/[id]/prepare
        ↓
  2. DatasetPreparePage loads
        ↓
  3. PreparePageContent mounts
        ├─ useEffect(() => loadDataset(datasetId))
        └─ useEffect(() => setDatasetId(datasetId) in WorkflowContext)
        ↓
  4. User builds transformation pipeline
        ├─ State updates in PreparePageContent
        ├─ unsavedChanges = true
        └─ Local state ONLY (not persisted to backend yet)
        ↓
  5. User clicks "Preview"
        ├─ API: POST /transformations/preview
        ├─ Response: preview data + impact metrics
        └─ Update preview panel
        ↓
  6. User clicks "Apply & Continue"
        ├─ API: POST /transformations/apply
        │  └─ Backend applies transformations
        │
        ├─ Response: transformed_dataset_id
        │
        ├─ completeStage(DATA_PREPARATION, {
        │    transformedDatasetId,
        │    selectedColumns,
        │    transformationCount,
        │    timestamp
        │  })
        │
        ├─ WorkflowContext advances to next stage
        │
        └─ Router.push(/features/[transformedDatasetId])
        ↓
  7. User navigates to next stage
        ↓
  8. DONE (transformation state not needed anymore)

If user tries to navigate away without applying:
  ├─ beforeunload event triggered
  └─ IF unsavedChanges:
     └─ Prompt: "You have unsaved changes. Discard or Save?"
        ├─ Discard → Allow navigation
        └─ Save → Show warning (transformations applied locally only)
```

---

## Performance Optimization Strategy

```
Optimization: Virtualization for Large Datasets
═════════════════════════════════════════════════

Example: 1,000 columns in ColumnSelector

WITHOUT Virtualization:
  DOM Nodes Created: 1,000
  Render Time: ~500ms
  Memory: ~5MB
  User Experience: LAGGY

WITH Virtualization (react-window):
  DOM Nodes Visible: ~10 (on screen)
  DOM Nodes Created Total: ~30 (with buffer)
  Render Time: ~20ms
  Memory: ~100KB
  User Experience: SMOOTH

  <FixedSizeList
    height={400}
    itemCount={1000}
    itemSize={35}
    width="100%"
  >
    {({ index, style }) => (
      <ColumnListItem
        style={style}
        column={columns[index]}
        isSelected={selectedColumns.has(columns[index].name)}
        onChange={...}
      />
    )}
  </FixedSizeList>


Optimization: Debounced Search
═══════════════════════════════

User types "ag" quickly:

  't' → debouncedSearch('t') [timer started]
  'a' → cancel timer, start new one
  'g' → cancel timer, start new one
  [200ms passed] → Execute search 'tag'

Result: 1 API call instead of 3

const debouncedSearch = useMemo(
  () => debounce((term: string) => {
    setFilteredColumns(filterColumns(term))
  }, 200),
  []
)


Optimization: State Memoization
════════════════════════════════

const transformationList = useMemo(
  () => transformations.map(t => ({ ...t })),
  [transformations]
)

Only recalculate if transformations reference changes
```

---

## Error Handling Flow

```
API Call in PreparePageContent
      ↓
try {
  response = await fetch(url)

  if (!response.ok) {
    error = await response.json()
    throw new Error(error.message)
  }

  data = await response.json()
  return data
}
catch (error) {
  ├─ showErrorToast(error.message)
  │  └─ Display toast for 5 seconds
  │
  ├─ console.error(error)
  │  └─ Log to console for debugging
  │
  └─ Handle state:
     ├─ setIsLoading(false)
     ├─ setError(error.message)
     └─ Keep UI stable (don't clear data)

Result: User sees error message + can retry
```

---

## Accessibility Event Flow

```
Keyboard User navigates to Step 2 using Tab
      ↓
Step 2 button receives focus
      ├─ Focus visible ring appears (outline-2 ring-blue-500)
      ├─ Screen reader announces: "Step 2 of 5, Fill Missing"
      └─ aria-current="step" triggers screen reader state
      ↓
User presses Enter
      ├─ Button onClick handler fires
      ├─ ConfigDialog opens
      └─ Focus moves to first form field (auto-focused)
      ↓
User navigates form with Tab
      ├─ label "Target Column" read
      ├─ <select> focused
      ├─ aria-label used if no label
      └─ Continue through form
      ↓
User presses Escape
      ├─ Dialog closes
      └─ Focus returns to Step 2 button
      ↓
User presses Alt+ArrowUp
      ├─ JavaScript intercepts keyboard event
      ├─ Calls onStepReorder(1, 0) to move up
      └─ Step 2 becomes Step 1 in DOM + screen reader announces change
```

---

**Generated**: 2025-12-17
**Architecture Review**: Phase 3 Complete
