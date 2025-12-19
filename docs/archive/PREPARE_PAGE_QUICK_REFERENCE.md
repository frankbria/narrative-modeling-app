# Data Preparation Page - Quick Reference Guide

## Quick Facts

**Route**: `/datasets/[id]/prepare`
**File Location**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/app/datasets/[id]/prepare/page.tsx`
**Lines of Code**: 252 lines
**Component Type**: Server-aware Client Component ('use client')
**Status**: ✅ Ready for testing

---

## Route Parameter

```typescript
// Extract dataset ID from dynamic route
const params = useParams();
const datasetId = params?.id as string;

// Example URLs:
/datasets/abc123/prepare        // datasetId = "abc123"
/datasets/xyz789/prepare        // datasetId = "xyz789"
```

---

## Key Props & Interfaces

### Dataset Interface
```typescript
interface Dataset {
  id: string;                    // Unique dataset identifier
  filename: string;              // Original filename (e.g., "sales_data.csv")
  num_rows: number;              // Total rows in dataset
  num_columns: number;           // Total columns in dataset
  schema?: any;                  // Column definitions (optional)
  file_id?: string;              // Storage file ID (optional)
}
```

---

## Component Hooks Usage

```typescript
// Hooks used in DatasetPreparePage:
const params = useParams();                    // Extract route params [id]
const router = useRouter();                    // Navigate between routes
const { data: session } = useSession();        // Current auth session
const { state, completeStage, canAccessStage } = useWorkflow(); // Workflow state
```

---

## State Variables

```typescript
const [dataset, setDataset] = useState<Dataset | null>(null);
const [isLoading, setIsLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
const [viewMode, setViewMode] = useState<'visual' | 'chain'>('visual');
const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
```

---

## API Endpoints

### Fetch Dataset Metadata
```
GET /api/v1/user_data/{datasetId}
Headers:
  Authorization: Bearer {token}
  Content-Type: application/json

Response (200): { id, filename, num_rows, num_columns, schema?, file_id? }
Response (404): { detail: "Dataset not found" }
```

### Apply Transformations (via TransformationPipeline)
```
POST /api/v1/transformations/apply
Body: { dataset_id, transformations[] }
Response (200): { transformed_dataset_id, row_count, schema }
```

---

## Workflow Integration

### Stage Access Control
```typescript
// Check if user can access DATA_PREPARATION stage
if (!canAccessStage(WorkflowStage.DATA_PREPARATION)) {
  router.push('/upload'); // Redirect if not allowed
}
```

### Stage Completion
```typescript
// Mark stage as complete and auto-advance
completeStage(WorkflowStage.DATA_PREPARATION, {
  datasetId: transformedDatasetId,
  originalDatasetId: datasetId,
  timestamp: new Date().toISOString()
});
// Automatically navigates to next stage (FEATURE_ENGINEERING)
```

---

## View Modes

### Visual Mode (Default)
- Renders ReactFlow-based TransformationPipeline
- Drag-and-drop transformation nodes
- Visual canvas with minimap and controls

### Chain Mode (Future)
- Linear list view of transformations
- Keyboard-navigable
- Reorder via buttons or drag
- Placeholder UI: "Chain view coming soon"

---

## Unsaved Changes Tracking

### How It Works
```typescript
// Page tracks unsaved changes
const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

// Pass callback to TransformationPipeline
<TransformationPipeline
  datasetId={datasetId}
  onComplete={handleComplete}
  onUnsavedChanges={setHasUnsavedChanges}  // NEW!
/>

// Warning before navigation
window.addEventListener('beforeunload', (e) => {
  if (hasUnsavedChanges) {
    e.preventDefault();
    e.returnValue = ''; // Browser shows default warning
  }
});
```

### When Changes Are Marked
- Node added to pipeline
- Node parameters updated
- Edges connected between nodes
- Recipe loaded

### When Changes Are Cleared
- Transformations successfully applied
- Unsaved changes callback receives `false`

---

## Error Handling

### API Error Response
```typescript
if (!response.ok) {
  if (response.status === 404) {
    throw new Error('Dataset not found'); // Shown in error card
  }
  throw new Error('Failed to fetch dataset');
}
```

### User-Facing Errors
- **Loading error**: "Error Loading Dataset" with error details
- **Missing dataset**: "Dataset Not Found"
- **Network error**: "Failed to fetch dataset"
- All errors show recovery link to `/explore`

---

## UI Components Used

### From shadcn/ui
- `Button` - Navigation, view toggle, actions
- `Card` - Content container, error display
- `CardContent`, `CardHeader`, `CardTitle` - Card parts

### From lucide-react
- `Loader2` - Loading spinner
- `ArrowLeft` - Back button
- `Eye` - Visual mode icon
- `List` - Chain mode icon

### Layout Classes (Tailwind)
- Responsive grid: `grid grid-cols-1 md:grid-cols-*`
- Flexbox: `flex flex-col md:flex-row`
- Spacing: `gap-4`, `px-4`, `py-6`
- Colors: `text-primary`, `border-destructive`

---

## Conditional Rendering

### Loading State
```typescript
if (isLoading) return <LoadingSpinner />
```

### Error State
```typescript
if (error || !dataset) return <ErrorCard />
```

### Success State
```typescript
return <MainLayout />
```

---

## Navigation

### To This Page
```typescript
// From explore page or dataset list
<Link href={`/datasets/${datasetId}/prepare`}>
  Prepare Data
</Link>
```

### From This Page

**Back Button** (Top Left)
```typescript
<Link href="/explore">
  <Button>Back</Button>
</Link>
```

**On Completion** (Auto via WorkflowContext)
```typescript
// Navigates to /datasets/[id]/features
// Handled automatically by completeStage()
```

---

## TypeScript Types

### Page Component Props
```typescript
// None - page receives params from route
```

### TransformationPipeline Integration
```typescript
interface TransformationPipelineProps {
  datasetId: string;
  onComplete?: (transformedDatasetId: string) => void;
  onUnsavedChanges?: (hasChanges: boolean) => void;  // NEW
}
```

---

## Environment Variables

```bash
# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
# or for production
NEXT_PUBLIC_API_URL=https://api.example.com/api/v1
```

---

## Testing URLs

```
# Local development
http://localhost:3000/datasets/test-dataset-id/prepare

# Production
https://app.example.com/datasets/test-dataset-id/prepare
```

---

## Future Enhancements

### Phase 4 Components (Placeholders Ready)
- **ColumnSelector** - Multi-select columns with search
- **TransformationChainView** - Linear transformation list
- **TransformationConfigDialog** - Dynamic parameter forms

### Planned Features
- Chain view implementation
- Column-specific transformation UI
- Transformation recipe management
- Advanced preview options
- Export transformation code

---

## Debugging Tips

### Check Console Logs
```javascript
// Error messages logged in catch blocks:
console.error('Error fetching dataset:', err);
console.error('Error completing preparation stage:', err);
```

### Verify WorkflowContext State
```javascript
// In browser console:
localStorage.getItem('workflowState')
// Shows current workflow state and completed stages
```

### Check API Responses
```javascript
// Network tab in DevTools
// Look for: GET /api/v1/user_data/{datasetId}
// Should return 200 with dataset metadata
```

### Session Check
```javascript
// Verify NextAuth session:
// useSession() should return { data: session, status }
// Token should be injected by getAuthToken()
```

---

## Common Issues & Solutions

### Issue: Page redirects to /upload
**Cause**: `canAccessStage(DATA_PREPARATION)` returned false
**Solution**: Complete previous stages (DATA_LOADING, DATA_PROFILING) first

### Issue: "Dataset not found" error
**Cause**: Invalid dataset ID in URL
**Solution**: Use valid dataset ID from /explore page

### Issue: "Failed to fetch dataset"
**Cause**: Network error or API unavailable
**Solution**: Check API URL in environment variables, verify backend is running

### Issue: Unsaved changes warning not showing
**Cause**: onUnsavedChanges callback not connected
**Solution**: Verify TransformationPipeline is being passed the callback

### Issue: Navigation doesn't advance to next stage
**Cause**: completeStage() not called properly
**Solution**: Verify handleComplete is invoked after Apply button click

---

## Related Files

**Created**:
- `/home/frankbria/projects/narrative-modeling-app/apps/frontend/app/datasets/[id]/prepare/page.tsx`
- `/home/frankbria/projects/narrative-modeling-app/PREPARE_PAGE_IMPLEMENTATION.md`

**Modified**:
- `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/transformation/TransformationPipeline.tsx`

**Referenced**:
- WorkflowContext: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/lib/contexts/WorkflowContext.tsx`
- Auth helpers: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/lib/auth-helpers.ts`
- Workflow types: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/lib/types/workflow.ts`

---

## Success Indicators

✅ Page loads at `/datasets/[id]/prepare`
✅ Dataset metadata displays correctly
✅ View toggle switches between Visual and Chain modes
✅ TransformationPipeline renders in Visual mode
✅ Unsaved changes warning appears when making changes
✅ Apply button completes stage and navigates to next step
✅ Back button returns to /explore
✅ Loading spinner shows during fetch
✅ Error messages display for failed requests
✅ TypeScript compiles without errors

---

## Git Information

**Commit Hash**: b94eb56
**Branch**: feature/enhance-data-preparation-ui
**Commit Message**: "feat(frontend): create dataset-specific data preparation page route"

---

**Last Updated**: December 17, 2025
**Ready for**: Testing → Code Review → Deployment
