# TransformationConfigDialog Component Documentation

## Overview

The `TransformationConfigDialog` is a modal dialog component for configuring transformation parameters with dynamic form rendering. It provides a flexible interface for handling multiple parameter types, validation, and keyboard navigation with full accessibility support.

## Usage

### Basic Example

```typescript
import { useState } from 'react';
import { TransformationConfigDialog, TransformationConfig } from '@/components/transformation/TransformationConfigDialog';

export function MyTransformationUI() {
  const [dialogOpen, setDialogOpen] = useState(false);

  const parametersSchema = {
    column: {
      type: 'string',
      title: 'Column',
      description: 'Select column to fill',
      required: true,
    },
    method: {
      type: 'string',
      title: 'Fill Method',
      enum: ['mean', 'median', 'mode', 'forward', 'backward'],
      required: true,
    },
  };

  const handleAddTransformation = (config: TransformationConfig) => {
    console.log('Added transformation:', config);
    // Add to pipeline
  };

  return (
    <>
      <button onClick={() => setDialogOpen(true)}>
        Configure Transformation
      </button>

      <TransformationConfigDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        transformationType="fill_missing"
        transformationLabel="Fill Missing Values"
        transformationDescription="Replace missing values with specified method"
        parametersSchema={parametersSchema}
        availableColumns={['id', 'name', 'email', 'age']}
        datasetId="dataset-123"
        onAdd={handleAddTransformation}
      />
    </>
  );
}
```

### With Preview and Delete

```typescript
<TransformationConfigDialog
  open={dialogOpen}
  onOpenChange={setDialogOpen}
  transformationType="fill_missing"
  transformationLabel="Fill Missing Values"
  transformationDescription="Replace missing values with specified method"
  parametersSchema={parametersSchema}
  availableColumns={availableColumns}
  datasetId={datasetId}
  onAdd={handleAddTransformation}
  onPreview={async (config) => {
    // Call preview API
    const response = await fetch('/api/transformations/preview', {
      method: 'POST',
      body: JSON.stringify({
        dataset_id: datasetId,
        transformations: [config],
      }),
    });
    // Handle preview response
  }}
  onDelete={() => {
    // Handle deletion
  }}
  existingConfig={selectedTransformation}
/>
```

## Props

### Required Props

| Prop | Type | Description |
|------|------|-------------|
| `open` | `boolean` | Controls dialog visibility |
| `onOpenChange` | `(open: boolean) => void` | Callback when dialog open state changes |
| `transformationType` | `string \| null` | Type identifier for the transformation |
| `transformationLabel` | `string` | Display name for the transformation |
| `transformationDescription` | `string` | Description of what the transformation does |
| `parametersSchema` | `Record<string, any>` | JSON schema defining transformation parameters |
| `availableColumns` | `string[]` | List of columns available for selection |
| `datasetId` | `string` | ID of the dataset being transformed |
| `onAdd` | `(config: TransformationConfig) => void` | Callback when transformation is added |

### Optional Props

| Prop | Type | Description |
|------|------|-------------|
| `onPreview` | `(config: TransformationConfig) => Promise<void>` | Callback for preview button |
| `existingConfig` | `TransformationConfig \| null` | Pre-fill dialog for editing existing config |
| `onDelete` | `() => void` | Callback for delete button |

## Parameter Schema Definition

### Schema Types

The `parametersSchema` uses JSON Schema format to describe parameters:

#### String Input

```typescript
{
  column_name: {
    type: 'string',
    title: 'Column Name',
    description: 'Name of the column',
    required: true,
  }
}
```

Renders as: Text input

#### Number Input

```typescript
{
  threshold: {
    type: 'number',
    title: 'Threshold',
    description: 'Threshold value',
    minimum: 0,
    maximum: 1,
    required: true,
  }
}
```

Renders as: Number input with min/max constraints

#### Boolean Checkbox

```typescript
{
  remove_duplicates: {
    type: 'boolean',
    title: 'Remove Duplicates',
    required: false,
  }
}
```

Renders as: Checkbox

#### Enum Select Dropdown

```typescript
{
  method: {
    type: 'string',
    title: 'Method',
    enum: ['mean', 'median', 'mode'],
    required: true,
  }
}
```

Renders as: Select dropdown

#### Array/Multi-Select

```typescript
{
  columns: {
    type: 'array',
    items: { type: 'string' },
    title: 'Columns',
    description: 'Select columns to transform',
    required: true,
  }
}
```

Renders as: Multi-select dropdown with searchable list

### Schema Properties

- `type`: `'string' | 'number' | 'integer' | 'boolean' | 'array'`
- `title`: Human-readable field name (optional, falls back to formatted key)
- `description`: Placeholder text or field description
- `required`: Whether field is required (default: `true` if not specified with default)
- `default`: Default value (marks field as optional)
- `enum`: Array of allowed values (for enum fields)
- `minimum` / `maximum`: Constraints for numeric fields
- `items`: Schema for array items (for array fields)

## Validation

The component performs automatic validation:

1. **Required Fields**: Ensures required fields have values
2. **Type Validation**: Validates values match their schema type
3. **Enum Validation**: Ensures enum values are in allowed list
4. **Range Validation**: Checks numeric values against min/max
5. **Array Validation**: Ensures arrays aren't empty when required

Error messages display inline below each field with red text and an alert icon.

### Custom Validation

To add custom validation logic:

```typescript
const customValidate = (parameters: Record<string, any>) => {
  const errors: Record<string, string> = {};

  if (parameters.column === 'id' && parameters.method === 'delete') {
    errors.column = 'Cannot delete ID column';
  }

  return errors;
};
```

## Keyboard Navigation

### Supported Shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Move to next field |
| `Shift+Tab` | Move to previous field |
| `Escape` | Close dialog |
| `Enter` | (from button) Submit form |
| `Space` | Toggle checkbox or select option |

### Focus Management

- **Initial Focus**: First form field receives focus when dialog opens
- **Focus Trap**: Tab/Shift+Tab cycles through dialog content only
- **Restore Focus**: Focus returns to trigger element when dialog closes
- **Last Interactive Element**: Tracks for focus wrapping

## Accessibility Features

### ARIA Attributes

- `role="dialog"` on dialog container
- `aria-labelledby` links to dialog title
- `aria-describedby` links to dialog description
- `aria-invalid="true"` on invalid fields
- `aria-describedby` on error messages
- `aria-multiselectable="true"` on multi-select listbox

### Screen Reader Support

- Form fields have associated labels
- Error messages linked via aria-describedby
- Required field indicators visible
- Field types announced (e.g., "text input", "checkbox")
- Dialog is properly announced as modal

### Visual Indicators

- Required fields marked with red asterisk
- Focus indicators visible on all interactive elements
- Error messages displayed with alert icon
- Disabled buttons during loading states

## Examples

### Example 1: Remove Duplicates

```typescript
const schema = {
  columns: {
    type: 'array',
    items: { type: 'string' },
    title: 'Columns to Consider',
    description: 'Select columns for duplicate detection',
    required: true,
  },
  keep_strategy: {
    type: 'string',
    title: 'Keep Strategy',
    enum: ['first', 'last', 'none'],
    required: true,
  },
};

<TransformationConfigDialog
  {...props}
  transformationType="remove_duplicates"
  transformationLabel="Remove Duplicates"
  parametersSchema={schema}
/>
```

### Example 2: Scale/Normalize

```typescript
const schema = {
  columns: {
    type: 'array',
    items: { type: 'string' },
    title: 'Columns',
    required: true,
  },
  method: {
    type: 'string',
    title: 'Scaling Method',
    enum: ['minmax', 'standard', 'robust'],
    required: true,
  },
  feature_range_min: {
    type: 'number',
    title: 'Min Value',
    default: 0,
    required: false,
  },
  feature_range_max: {
    type: 'number',
    title: 'Max Value',
    default: 1,
    required: false,
  },
};
```

### Example 3: Date Parsing

```typescript
const schema = {
  column: {
    type: 'string',
    title: 'Date Column',
    required: true,
  },
  format: {
    type: 'string',
    title: 'Date Format',
    enum: ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', 'auto'],
    required: true,
  },
  infer_format: {
    type: 'boolean',
    title: 'Infer Format',
    required: false,
  },
};
```

## Error Handling

### Validation Errors

Displayed inline under each field:

```typescript
// User leaves required field empty
"Column is required"

// User enters invalid number
"Threshold must be a number"

// User enters value outside range
"Threshold must be between 0 and 1"
```

### API Errors

If `onPreview` throws an error:

```typescript
onPreview={async (config) => {
  const response = await fetch('/api/transformations/preview', {
    method: 'POST',
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Preview failed');
  }

  return response.json();
}}
```

Error displays in a red alert box at top of dialog.

## State Management

The component manages its own internal state:

- `parameters`: Form field values
- `errors`: Validation error messages
- `isPreviewLoading`: Loading state during preview
- `isSubmitting`: Loading state during submission

To integrate with external state:

```typescript
const [dialogOpen, setDialogOpen] = useState(false);
const [selectedTransformation, setSelectedTransformation] = useState<TransformationConfig | null>(null);

const handleAddTransformation = (config: TransformationConfig) => {
  // Update parent state
  setPipeline([...pipeline, config]);
  setDialogOpen(false);
};
```

## Testing

### Unit Tests

The component includes comprehensive test coverage:

```bash
npm test -- TransformationConfigDialog.test.tsx
```

Coverage includes:
- Dialog opening/closing
- Form field rendering for all types
- Validation behavior
- Keyboard navigation
- Accessibility compliance
- Error handling
- Preview/delete functionality

### Test Utilities

```typescript
import { render, screen, userEvent } from '@testing-library/react';
import { TransformationConfigDialog } from '@/components/transformation/TransformationConfigDialog';

const props = {
  open: true,
  onOpenChange: jest.fn(),
  transformationType: 'fill_missing',
  transformationLabel: 'Fill Missing Values',
  transformationDescription: 'Replace missing values',
  parametersSchema: { /* ... */ },
  availableColumns: ['col1', 'col2'],
  datasetId: 'dataset-123',
  onAdd: jest.fn(),
};

render(<TransformationConfigDialog {...props} />);
```

## Performance Considerations

1. **Column Lists**: Multi-select is optimized for 1000+ columns
2. **Lazy Validation**: Validation only runs on submit or when fields change
3. **Debounced Search**: Multi-select search is debounced (if implemented)
4. **Memoization**: Form fields memoized to prevent unnecessary re-renders

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari 14+, Chrome mobile 90+)

## Dependencies

- React 18+
- Radix UI (via Shadcn/UI components)
- Tailwind CSS
- lucide-react (for icons)

## Common Issues

### Issue: Dialog doesn't close on Escape

**Solution**: Ensure `onOpenChange` is properly wired:
```typescript
<TransformationConfigDialog
  open={dialogOpen}
  onOpenChange={setDialogOpen}  // <-- Important
  {...props}
/>
```

### Issue: Validation not working

**Solution**: Ensure schema has `required` or `default` properties:
```typescript
parametersSchema: {
  column: {
    type: 'string',
    required: true,  // <-- Add this
  }
}
```

### Issue: Multi-select not showing columns

**Solution**: Pass `availableColumns` array:
```typescript
<TransformationConfigDialog
  availableColumns={['col1', 'col2', 'col3']}  // <-- Add this
  {...props}
/>
```

## Future Enhancements

- [ ] Conditional field visibility based on other field values
- [ ] Custom validation rules via props
- [ ] Field-level error recovery suggestions
- [ ] Transformation preview inline in dialog
- [ ] Field templates for common transformation types
- [ ] Help tooltips with examples
- [ ] Copy/paste button for parameters
