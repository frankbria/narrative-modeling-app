# ColumnSelector Quick Start Guide

## Installation

The component is ready to use. Ensure dependencies are installed:

```bash
npm install
```

## Basic Usage

```tsx
import { ColumnSelector } from '@/components/transformation/ColumnSelector';
import { useState } from 'react';

export function MyComponent() {
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set());

  return (
    <div className="w-96 h-96">
      <ColumnSelector
        datasetId="my-dataset"
        selectedColumns={selectedColumns}
        onSelectionChange={setSelectedColumns}
      />
    </div>
  );
}
```

## Key Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `datasetId` | string | Yes | Dataset ID for fetching columns |
| `selectedColumns` | Set<string> | Yes | Set of selected column names |
| `onSelectionChange` | (columns: Set<string>) => void | Yes | Callback when selection changes |
| `className` | string | No | Additional CSS classes |

## Common Patterns

### With loading state
```tsx
const [selectedColumns, setSelectedColumns] = useState<Set<string>>(new Set());
const [isLoading, setIsLoading] = useState(false);

return (
  <div className="relative">
    <ColumnSelector
      datasetId={datasetId}
      selectedColumns={selectedColumns}
      onSelectionChange={setSelectedColumns}
    />
    {isLoading && <div className="absolute inset-0 bg-white/50" />}
  </div>
);
```

### With Apply button
```tsx
const handleApply = () => {
  // Use selectedColumns
  console.log('Selected:', Array.from(selectedColumns));
};

return (
  <div>
    <ColumnSelector
      datasetId={datasetId}
      selectedColumns={selectedColumns}
      onSelectionChange={setSelectedColumns}
    />
    <Button
      onClick={handleApply}
      disabled={selectedColumns.size === 0}
    >
      Apply ({selectedColumns.size} columns)
    </Button>
  </div>
);
```

### With pre-selected columns
```tsx
const defaultColumns = new Set(['id', 'name', 'date']);
const [selectedColumns, setSelectedColumns] = useState(defaultColumns);

return (
  <ColumnSelector
    datasetId={datasetId}
    selectedColumns={selectedColumns}
    onSelectionChange={setSelectedColumns}
  />
);
```

## Keyboard Shortcuts

- **Arrow Up/Down**: Navigate columns
- **Space**: Toggle selected column
- **Escape**: Clear search
- **Tab**: Move to next interactive element

## Styling

Set height with className:

```tsx
// Small (300px)
<ColumnSelector ... className="h-80" />

// Medium (400px)
<ColumnSelector ... className="h-96" />

// Large (500px)
<ColumnSelector ... className="h-screen" />
```

## Troubleshooting

### Columns not appearing?
- Check browser console for fetch errors
- Verify `datasetId` is correct
- Ensure API endpoint is accessible
- Check authentication token

### Selection not updating?
- Verify `onSelectionChange` callback is set
- Check parent component state management
- Ensure `selectedColumns` is a Set (not array)

### Search not working?
- Ensure input field is focused
- Verify columns were fetched successfully
- Check debounce delay (default 300ms)

## API Response Format

The component expects this response from `/api/v1/data/{datasetId}/preview`:

```json
{
  "columns": [
    {
      "name": "column_name",
      "type": "numeric|categorical|datetime|text",
      "unique_count": 100,
      "null_count": 5,
      "total_rows": 1000
    }
  ],
  "data": [
    { "column_name": "value", ... }
  ]
}
```

## Error Handling

The component handles errors gracefully:

```tsx
// Failed to load columns
<ColumnSelector datasetId="invalid" />
// → Shows: "Failed to load columns: 404 Not Found"
```

## Performance Notes

- Uses virtual scrolling for 1000+ columns
- Search is debounced (300ms)
- Optimized with React.memo and useCallback
- No re-renders on parent state changes unless props change

## Accessibility

Full keyboard navigation available:
- Tab to focus
- Arrow keys to navigate
- Space to select
- Escape to clear

Screen readers supported with ARIA labels.

## Testing

Run tests:
```bash
npm test ColumnSelector
```

With coverage:
```bash
npm test -- --coverage
```

## Import Path

```tsx
// Full path
import { ColumnSelector } from '@/components/transformation/ColumnSelector';

// Direct use
import ColumnSelector from '@/components/transformation/ColumnSelector';
```

## Next Steps

1. Integrate into PreparePageContent
2. Connect with TransformationConfigDialog
3. Add to WorkflowContext integration
4. Deploy and monitor

## Help & Docs

- Full documentation: `COLUMN_SELECTOR.md`
- Hook documentation: `lib/hooks/useDebounce.md`
- Examples: `ColumnSelector.example.tsx`
- Tests: `ColumnSelector.test.tsx`
