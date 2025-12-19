# TransformationChainView - Quick Usage Guide

## Quick Start

```typescript
import { TransformationChainView, TransformationStep } from '@/components/transformation/TransformationChainView';
import { useState } from 'react';

export function MyDataPrepComponent() {
  const [steps, setSteps] = useState<TransformationStep[]>([
    {
      id: '1',
      type: 'remove_duplicates',
      label: 'Remove Duplicates',
      parameters: { keep: 'first' },
    },
  ]);

  return (
    <TransformationChainView
      transformations={steps}
      onReorder={(from, to) => {
        const newSteps = [...steps];
        const [removed] = newSteps.splice(from, 1);
        newSteps.splice(to, 0, removed);
        setSteps(newSteps);
      }}
      onEdit={(index) => {
        // Open config dialog
        openEditDialog(steps[index]);
      }}
      onDelete={(index) => {
        setSteps(steps.filter((_, i) => i !== index));
      }}
    />
  );
}
```

## Component API

### Props

```typescript
interface TransformationChainViewProps {
  transformations: TransformationStep[];      // Array of steps to display
  onReorder: (from: number, to: number) => void;  // Reorder callback
  onEdit: (index: number) => void;                // Edit callback
  onDelete: (index: number) => void;              // Delete callback
  className?: string;                             // Optional CSS classes
}

interface TransformationStep {
  id: string;                           // Unique identifier
  type: string;                         // Transformation type
  label: string;                        // Display name
  parameters: Record<string, any>;      // Configuration parameters
}
```

### Callbacks

#### onReorder
Fired when user reorders steps via drag-drop or arrow buttons.

```typescript
onReorder={(fromIndex, toIndex) => {
  // fromIndex: Source position
  // toIndex: Destination position
  // Note: Both are 0-indexed
}}
```

#### onEdit
Fired when user clicks the Edit button for a step.

```typescript
onEdit={(index) => {
  // index: Position of step to edit (0-indexed)
  // Typically opens TransformationConfigDialog
}}
```

#### onDelete
Fired when user clicks the Delete button for a step.

```typescript
onDelete={(index) => {
  // index: Position of step to delete (0-indexed)
}}
```

## Features

### Visual Indicators
- **Grip Handle**: Indicates drag capability
- **Chevron**: Click to expand/collapse details
- **Visual Connector**: Line between steps
- **Disabled State**: Gray out unavailable actions
- **Focus Ring**: Blue ring on keyboard focus

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Tab` | Move to next step |
| `Shift+Tab` | Move to previous step |
| `Alt+↑` | Move step up |
| `Alt+↓` | Move step down |
| `Delete` | Remove step |
| `Enter` | Edit step |

### Mobile Features
- Touch-friendly 44px button targets
- Responsive card layout
- Expand/collapse for space efficiency
- No complex drag-and-drop required (buttons always available)

## Styling & Customization

### Using Custom Classes

```typescript
<TransformationChainView
  transformations={steps}
  onReorder={handleReorder}
  onEdit={handleEdit}
  onDelete={handleDelete}
  className="my-custom-class"
/>
```

### Tailwind CSS Integration
The component uses Tailwind utility classes:
- `rounded-lg` - Card rounding
- `border` - Card border
- `shadow-md` - Card shadow
- `cursor-move` - Drag affordance
- `focus:ring-2` - Keyboard focus

Customize via your Tailwind config if needed.

## Accessibility Features

### Screen Reader Support
- **List Navigation**: Use screen reader list navigation commands
- **Step Announcement**: Each step announces its position and type
- **Live Updates**: Changes announced via `aria-live` regions
- **Keyboard Only**: Fully operable without mouse

### Keyboard Navigation
- All buttons reachable via Tab
- Focus visible at all times
- No keyboard traps
- Clear focus management

### Color Contrast
- All text meets WCAG AA (4.5:1 ratio)
- Icons have sufficient stroke weight
- Visual indicators support color-blind users

## Examples

### Basic Setup
```typescript
const [transformations, setTransformations] = useState<TransformationStep[]>([]);

<TransformationChainView
  transformations={transformations}
  onReorder={(from, to) => {
    const newList = [...transformations];
    const [item] = newList.splice(from, 1);
    newList.splice(to, 0, item);
    setTransformations(newList);
  }}
  onEdit={(index) => showDialog(transformations[index])}
  onDelete={(index) => {
    setTransformations(transformations.filter((_, i) => i !== index));
  }}
/>
```

### With Loading State
```typescript
const [isLoading, setIsLoading] = useState(false);

<div className="space-y-4">
  {isLoading && <Spinner />}
  <TransformationChainView
    transformations={transformations}
    onReorder={handleReorder}
    onEdit={handleEdit}
    onDelete={handleDelete}
  />
</div>
```

### With Empty State
```typescript
{transformations.length === 0 ? (
  <div className="text-center py-12">
    <p className="text-muted-foreground">No transformations yet</p>
    <Button onClick={openAddDialog}>Add Transformation</Button>
  </div>
) : (
  <TransformationChainView
    transformations={transformations}
    onReorder={handleReorder}
    onEdit={handleEdit}
    onDelete={handleDelete}
  />
)}
```

### Complete Example
```typescript
'use client';

import { useState } from 'react';
import { TransformationChainView, TransformationStep } from '@/components/transformation/TransformationChainView';
import { TransformationConfigDialog } from '@/components/transformation/TransformationConfigDialog';
import { Button } from '@/components/ui/button';

export function DataPrepPage() {
  const [steps, setSteps] = useState<TransformationStep[]>([
    {
      id: '1',
      type: 'remove_duplicates',
      label: 'Remove Duplicates',
      parameters: { keep: 'first' },
    },
    {
      id: '2',
      type: 'fill_missing',
      label: 'Fill Missing Values',
      parameters: { method: 'mean', columns: [] },
    },
  ]);

  const [editingStep, setEditingStep] = useState<TransformationStep | null>(null);
  const [editIndex, setEditIndex] = useState<number | null>(null);

  const handleReorder = (from: number, to: number) => {
    const newSteps = [...steps];
    const [removed] = newSteps.splice(from, 1);
    newSteps.splice(to, 0, removed);
    setSteps(newSteps);
  };

  const handleEdit = (index: number) => {
    setEditingStep(steps[index]);
    setEditIndex(index);
  };

  const handleSaveEdit = (updated: TransformationStep) => {
    if (editIndex !== null) {
      const newSteps = [...steps];
      newSteps[editIndex] = updated;
      setSteps(newSteps);
    }
    setEditingStep(null);
    setEditIndex(null);
  };

  const handleDelete = (index: number) => {
    setSteps(steps.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Data Preparation</h2>
        <Button onClick={() => setEditingStep({ id: '', type: '', label: '', parameters: {} })}>
          Add Step
        </Button>
      </div>

      <TransformationChainView
        transformations={steps}
        onReorder={handleReorder}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      {editingStep && (
        <TransformationConfigDialog
          isOpen={true}
          transformation={editingStep}
          availableColumns={['age', 'salary', 'name']}
          onSave={handleSaveEdit}
          onCancel={() => setEditingStep(null)}
        />
      )}
    </div>
  );
}
```

## Testing

### Running Tests
```bash
cd apps/frontend
npm test -- __tests__/components/transformation/TransformationChainView.test.tsx
```

### Testing Your Integration
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { TransformationChainView } from '@/components/transformation/TransformationChainView';

it('should reorder steps', () => {
  const mockReorder = jest.fn();

  render(
    <TransformationChainView
      transformations={[
        { id: '1', type: 'fill', label: 'Fill', parameters: {} },
        { id: '2', type: 'scale', label: 'Scale', parameters: {} },
      ]}
      onReorder={mockReorder}
      onEdit={jest.fn()}
      onDelete={jest.fn()}
    />
  );

  const moveDownButtons = screen.getAllByRole('button', { name: /move down/i });
  fireEvent.click(moveDownButtons[0]);

  expect(mockReorder).toHaveBeenCalledWith(0, 1);
});
```

## Performance Tips

### For Large Lists
If you have >100 steps, consider:
1. Limiting visible steps with pagination
2. Using virtualization (`react-window`)
3. Lazy-loading step details

### Optimization Example
```typescript
import { useMemo } from 'react';

const visibleSteps = useMemo(
  () => steps.slice(pageIndex * 10, (pageIndex + 1) * 10),
  [steps, pageIndex]
);

<TransformationChainView
  transformations={visibleSteps}
  onReorder={(from, to) => handleReorderGlobal(pageIndex * 10 + from, pageIndex * 10 + to)}
  onEdit={(index) => handleEdit(pageIndex * 10 + index)}
  onDelete={(index) => handleDelete(pageIndex * 10 + index)}
/>
```

## Troubleshooting

### Buttons Not Responding
- Check parent component is properly handling callbacks
- Ensure no event.stopPropagation() in parent
- Verify component is not in read-only mode

### Screen Reader Not Announcing
- Verify browser supports `aria-live` (all modern browsers)
- Check announcements appear in browser DevTools
- Test with NVDA/JAWS instead of browser built-in reader

### Drag-and-Drop Not Working
- Ensure CSS doesn't disable `pointer-events`
- Check for `e.preventDefault()` in parent handlers
- Verify dataTransfer object is accessible

### Focus Not Visible
- Check Tailwind focus styles are not overridden
- Ensure browser's focus mode is enabled
- Test without CSS customizations first

## Related Components

- **TransformationConfigDialog**: Opens to configure step parameters
- **TransformationPipeline**: ReactFlow-based visual editor
- **PreparePageContent**: Container that orchestrates both views
- **ColumnSelector**: Sidebar for column selection

## Browser Support

| Browser | Support |
|---------|---------|
| Chrome 90+ | ✅ Full |
| Firefox 88+ | ✅ Full |
| Safari 14+ | ✅ Full |
| Edge 90+ | ✅ Full |
| Mobile Safari | ✅ Touch support |
| Chrome Mobile | ✅ Touch support |

## File Size

| File | Size |
|------|------|
| Component | 407 lines |
| Tests | 571 lines |
| Total | 978 lines |

## Next Steps

1. Integrate with `PreparePageContent` wrapper
2. Add E2E tests with Playwright
3. Implement in production data prep interface
4. Gather user feedback on UX

---

**Last Updated**: 2025-12-17
**Component Version**: 1.0.0
**Status**: Production Ready
