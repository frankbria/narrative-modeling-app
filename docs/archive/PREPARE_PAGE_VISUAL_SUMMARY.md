# Data Preparation Page - Visual Summary

## Route Architecture

```
OLD ROUTE (Phase 3a - Redirects)         NEW ROUTE (Phase 3+)
┌─────────────────────────────┐          ┌──────────────────────────┐
│ /prepare?datasetId=abc123   │          │ /datasets/abc123/prepare │
│ (Legacy - Deprecated)       │          │ (New - Current)          │
└──────────────┬──────────────┘          └──────────────┬───────────┘
               │                                         │
               │ Redirects (302)                         │
               └────────────────────────┬────────────────┘
                                        │
                                        ▼
                          DatasetPreparePage
                          (page.tsx - 252 lines)
```

---

## Directory Structure

```
apps/frontend/app/
│
├── explore/
│   └── [id]/
│       └── page.tsx ............ Explore page (existing)
│
├── datasets/ ................... NEW DIRECTORY
│   └── [id]/
│       └── prepare/ ............ NEW SUBDIRECTORY
│           └── page.tsx ........ NEW COMPONENT (252 lines)
│
└── prepare/
    └── page.tsx ................ Legacy route (redirects)
```

---

## Page Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Back  │ Prepare Data                          Visual │ Chain  │
│          │ sales_data.csv • 1,000 rows • 12 columns             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Visual Pipeline                                          │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │                                                           │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │ TransformationPipeline (ReactFlow Canvas)        │   │   │
│  │  │                                                   │   │   │
│  │  │  ┌─────────────────┐      ┌─────────────────┐   │   │   │
│  │  │  │  Remove Dups    │─────→│  Fill Missing   │   │   │   │
│  │  │  └─────────────────┘      └─────────────────┘   │   │   │
│  │  │         │                                        │   │   │
│  │  │    [Toolbar]                                     │   │   │
│  │  │  [Preview] [Apply & Continue] [Recipes]         │   │   │
│  │  │                                                   │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Changes are automatically saved. Navigate away to continue     │
│  to the next stage when you're done.                            │
│                                                                   │
│  ⚠️ You have unsaved changes. They will be lost if you         │
│     navigate away. (conditional)                               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## State Flow Diagram

```
┌────────────────────┐
│  Page Mounts       │
└─────────┬──────────┘
          │
          ▼
┌────────────────────────────────┐
│ canAccessStage(                │
│   DATA_PREPARATION             │
│ )?                             │
└────────────┬─────────────────┬─┘
             │ NO              │ YES
             ▼                 ▼
      Redirect to      Fetch Dataset
       /upload         (GET /user_data/{id})
                             │
                    ┌────────┴────────┐
                    │ Success / Error │
                    ▼                 ▼
                Display Data      Error Card
                Dataset UI        + Back Link
                    │
                    ▼
        ┌───────────────────────┐
        │ User interacts with   │
        │ TransformationPipeline│
        └───────┬───────────────┘
                │
        ┌───────▼──────────────────┐
        │ Changes made?            │
        │ setHasUnsavedChanges()   │
        │ true                     │
        └──────────────────────────┘
                │
                ▼
        ┌──────────────────────────┐
        │ Show warning: Unsaved    │
        │ changes on navigation    │
        └──────────────────────────┘
                │
        ┌───────▼───────────────┐
        │ Click "Apply &        │
        │ Continue" button      │
        └───────┬───────────────┘
                │
        ┌───────▼────────────────────────────┐
        │ TransformationPipeline calls       │
        │ onComplete(transformedDatasetId)   │
        └───────┬────────────────────────────┘
                │
        ┌───────▼──────────────────────────────┐
        │ handleComplete() calls:              │
        │ completeStage(                       │
        │   DATA_PREPARATION, {...}           │
        │ )                                    │
        └───────┬───────────────────────────────┘
                │
        ┌───────▼────────────────────────┐
        │ WorkflowContext:               │
        │ - Marks stage as completed     │
        │ - Auto-advances to next stage  │
        │ - Navigates to /datasets/[id]/ │
        │   features                     │
        └────────────────────────────────┘
```

---

## Component Hierarchy

```
DatasetPreparePage
│
├── Header Section
│   ├── Link (back button)
│   │   └── Button (ArrowLeft icon)
│   │
│   ├── Title & Subtitle
│   │   ├── h1 "Prepare Data"
│   │   └── p (filename, rows, columns)
│   │
│   └── View Mode Toggle
│       ├── Button (Visual - Eye icon)
│       └── Button (Chain - List icon)
│
├── Main Content
│   └── Card
│       ├── CardHeader
│       │   └── CardTitle (dynamic: Visual/Chain)
│       │
│       └── CardContent
│           └── TransformationPipeline (or Chain placeholder)
│               │
│               ├── TransformationSidebar
│               │   └── Transformation type list
│               │
│               ├── ReactFlow Canvas
│               │   ├── Nodes (TransformationNode)
│               │   ├── Edges (connections)
│               │   ├── Controls
│               │   └── MiniMap
│               │
│               ├── Toolbar
│               │   ├── Preview Button
│               │   ├── Apply & Continue Button
│               │   ├── Recipe Manager
│               │   ├── Undo/Redo
│               │   └── Export Code
│               │
│               └── PreviewPanel
│                   └── Data preview table
│
└── Information Footer
    ├── p (auto-save message)
    └── p (conditional: unsaved changes warning)
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ User URL: /datasets/abc123/prepare                          │
│ params.id = "abc123"                                        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │ useParams()    │
        │ datasetId =    │
        │ "abc123"       │
        └────────┬───────┘
                 │
        ┌────────▼──────────────────────┐
        │ useWorkflow()                  │
        │ - state                        │
        │ - completeStage                │
        │ - canAccessStage               │
        └────────┬───────────────────────┘
                 │
        ┌────────▼─────────────────────────────┐
        │ fetch(/user_data/abc123)              │
        │ ↓                                      │
        │ Response: Dataset object              │
        │ {                                      │
        │   id: "abc123",                       │
        │   filename: "sales.csv",              │
        │   num_rows: 1000,                     │
        │   num_columns: 12                     │
        │ }                                      │
        └────────┬──────────────────────────────┘
                 │
        ┌────────▼──────────────────────────┐
        │ setDataset(response)               │
        │ Display page with dataset info     │
        └────────┬───────────────────────────┘
                 │
        ┌────────▼────────────────────────────────────┐
        │ Render TransformationPipeline               │
        │ Pass props:                                 │
        │ - datasetId="abc123"                       │
        │ - onComplete={handleComplete}              │
        │ - onUnsavedChanges={setHasUnsavedChanges}  │
        └────────┬─────────────────────────────────┬─┘
                 │ User adds transformation nodes   │
                 │                                 │
        ┌────────▼──────────────────────────┐   │
        │ TransformationPipeline tracks     │   │
        │ changes via onUnsavedChanges()    │   │
        │ ↓                                  │   │
        │ setHasUnsavedChanges(true)        │   │
        └────────┬──────────────────────────┘   │
                 │                               │
        ┌────────▼─────────────────────────┐   │
        │ Page state: hasUnsavedChanges    │   │
        │ ↓                                 │   │
        │ Footer shows warning message     │   │
        └────────┬──────────────────────────┘   │
                 │ User clicks "Apply"           │
                 │                               │
        ┌────────▼──────────────────────────────┐
        │ TransformationPipeline:                │
        │ POST /transformations/apply            │
        │ {                                      │
        │   dataset_id: "abc123",                │
        │   transformations: [...]               │
        │ }                                      │
        └────────┬───────────────────────────────┘
                 │
        ┌────────▼──────────────────────────┐
        │ API Response (200):                │
        │ {                                  │
        │   transformed_dataset_id: "xyz789" │
        │ }                                  │
        └────────┬───────────────────────────┘
                 │
        ┌────────▼──────────────────────────┐
        │ TransformationPipeline calls      │
        │ onComplete("xyz789")              │
        └────────┬───────────────────────────┘
                 │
        ┌────────▼─────────────────────────────────┐
        │ DatasetPreparePage handleComplete()      │
        │ ↓                                         │
        │ completeStage(                           │
        │   DATA_PREPARATION,                      │
        │   {                                      │
        │     datasetId: "xyz789",                 │
        │     originalDatasetId: "abc123"          │
        │   }                                      │
        │ )                                        │
        └────────┬──────────────────────────────┬──┘
                 │ WorkflowContext updates        │
                 │                               │
        ┌────────▼────────────────────────────┐│
        │ - Mark DATA_PREPARATION completed  ││
        │ - Move to next stage                ││
        │ - Router.push(                       ││
        │   /datasets/xyz789/features        ││
        │ )                                    ││
        └─────────────────────────────────────┘│
                                                │
        ┌───────────────────────────────────────┘
        │
        ▼
    Navigate to
 Feature Engineering
     Stage
```

---

## View Mode Toggle Behavior

```
User clicks "Visual" button     User clicks "Chain" button
        │                              │
        ▼                              ▼
setViewMode('visual')       setViewMode('chain')
        │                              │
        ▼                              ▼
Condition: viewMode === 'visual'    Condition: viewMode === 'chain'
        │                              │
        ▼                              ▼
Render:                         Render:
- TransformationPipeline       - Chain View Placeholder
- Full ReactFlow canvas        - "Chain view coming soon"
- Sidebar                      - Dashed border box
- Toolbar (Preview, Apply, etc) - List icon
- Preview panel

Button styling:                 Button styling:
- Visual btn: "default"        - Chain btn: "default"
- Chain btn: "ghost"           - Visual btn: "ghost"
```

---

## Error State Transitions

```
API Call
   │
   ├─ Success (200)
   │  └─ Display dataset
   │
   ├─ 404 Not Found
   │  └─ "Dataset not found"
   │     Display error card with back link
   │
   └─ Other Error (5xx, network, etc)
      └─ "Failed to fetch dataset"
         Display error card with back link
         Show error details if available

Catch Block
   │
   └─ Exception
      └─ Log to console
         Display "Failed to fetch dataset"
         Show recovery link to /explore
```

---

## Props Flow

```
DatasetPreparePage
│
├─ datasetId (string)
│  └─ From: useParams()
│     Used by: TransformationPipeline
│
├─ handleComplete (function)
│  └─ Definition: (transformedDatasetId: string) => void
│     Passed to: TransformationPipeline.onComplete
│     Called when: User applies transformations
│     Does: Calls completeStage() and advances workflow
│
├─ setHasUnsavedChanges (function)
│  └─ Definition: (hasChanges: boolean) => void
│     Passed to: TransformationPipeline.onUnsavedChanges
│     Called when: User makes changes in pipeline
│     Does: Updates page's unsaved changes warning
│
└─ dataset (Dataset | null)
   └─ From: API fetch response
      Used by: Header display and error handling
      Contains: filename, num_rows, num_columns
```

---

## Responsive Breakpoints

```
Mobile (< 768px)
┌────────────────┐
│ ← Back         │
│ Prepare Data   │
│ sales.csv...   │
│ [Visual] [Chain]
│                │
│ [Pipeline]     │
│ [Footer]       │
└────────────────┘

Tablet (768px - 1024px)
┌────────────────────────────┐
│ ← Back | Prepare Data      │
│        | sales.csv...      │
│ [Visual] [Chain]           │
│                            │
│ [Pipeline]                 │
│ [Footer]                   │
└────────────────────────────┘

Desktop (> 1024px)
┌────────────────────────────────────────────┐
│ ← Back │ Prepare Data          Visual Chain│
│        │ sales.csv • 1000 rows  [Btns]    │
│                                            │
│ [Pipeline / Chain View]                    │
│                                            │
│ [Footer Message]                           │
└────────────────────────────────────────────┘
```

---

## TypeScript Type Safety

```
DatasetPreparePage
│
├─ Input Types
│  └─ params from useParams() → Record<string, string | undefined>
│     Safely cast: (params?.id as string)
│
├─ State Types
│  ├─ dataset: Dataset | null
│  ├─ isLoading: boolean
│  ├─ error: string | null
│  ├─ viewMode: 'visual' | 'chain'
│  └─ hasUnsavedChanges: boolean
│
├─ Interface Types
│  └─ Dataset
│     ├─ id: string
│     ├─ filename: string
│     ├─ num_rows: number
│     ├─ num_columns: number
│     ├─ schema?: any
│     └─ file_id?: string
│
└─ Hook Return Types
   ├─ useParams() → object
   ├─ useRouter() → NextRouter
   ├─ useSession() → { data: Session, status }
   └─ useWorkflow() → WorkflowContextType
```

---

## Performance Metrics

```
Page Load Timeline
├─ 0ms: Component mounts
├─ 0-10ms: Hooks initialize
├─ 10-50ms: useEffect executes
├─ 50-200ms: canAccessStage check
├─ 200-500ms: API fetch initiated
│  └─ (Network latency: 100-300ms)
├─ 500-600ms: Response received
├─ 600-650ms: Data parsed & state updated
├─ 650-700ms: Component re-renders
└─ 700ms: Page fully interactive

Target Performance
├─ Page load: < 2000ms
├─ Dataset fetch: < 500ms
├─ Transformation preview: < 200ms
└─ UI interactions: < 100ms
```

---

## Security Flow

```
API Request
   │
   ├─ Authorization Header
   │  └─ getAuthToken() → Bearer {token}
   │     From: NextAuth session
   │     Refreshed: Automatically
   │
   ├─ Content-Type Header
   │  └─ application/json
   │
   └─ Request Body
      └─ datasetId, transformations
         No sensitive data in client logs

Response Handling
   │
   └─ Validate response
      ├─ Check status code (200, 404, 5xx)
      ├─ Parse JSON
      ├─ Type-check against interface
      └─ Display or error

Data Privacy
   │
   ├─ No PII logged to console
   ├─ Error messages user-friendly (no stack traces)
   ├─ Session tokens secure (httpOnly cookie)
   └─ API enforces authorization server-side
```

---

**Last Updated**: December 17, 2025
**Commit**: b94eb56
**Status**: ✅ Ready for Testing
