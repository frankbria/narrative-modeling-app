# ColumnSelector Test Structure Guide

## File Organization

```
apps/frontend/
├── __mocks__/
│   └── react-window.tsx                    # Mock for virtualized list
├── __tests__/
│   └── components/
│       └── transformation/
│           └── ColumnSelector.test.tsx     # Main test suite (53 tests)
├── components/
│   └── transformation/
│       ├── ColumnSelector.tsx              # Component implementation
│       └── ColumnSelector.test.tsx         # Placeholder (moved to __tests__)
├── lib/
│   └── hooks/
│       └── useDebounce.ts                  # Debounce hook used in component
└── jest.setup.js                           # Test configuration
```

## Test Suite Structure

### Top-Level Test Groups

```typescript
describe('ColumnSelector', () => {
  // Mock data setup
  const mockColumns = [...]
  const mockApiResponse = { columns: mockColumns, data: [] }

  beforeEach(() => {
    jest.clearAllMocks()
    (global.fetch as jest.Mock).mockResolvedValue(...)
  })

  // 13 describe blocks organized by feature
  describe('Rendering and Loading States', () => {...})
  describe('Error Handling', () => {...})
  describe('Column Selection', () => {...})
  describe('Search and Filter Functionality', () => {...})
  describe('Select All / Deselect All', () => {...})
  describe('Keyboard Navigation', () => {...})
  describe('Column Type Indicators', () => {...})
  describe('Missing Values Display', () => {...})
  describe('API Integration', () => {...})
  describe('Accessibility', () => {...})
  describe('Props and Customization', () => {...})
  describe('Edge Cases', () => {...})
  describe('Integration Scenarios', () => {...})
})
```

## Test Naming Convention

All tests follow a consistent pattern:

```
✓ should [expected behavior]
✓ should [handle | display | render | support | accept | ...] [specific scenario]
```

Examples:
- `should display loading state initially`
- `should render all columns after loading`
- `should handle columns with special characters in names`
- `should accept custom className prop`

## Mock Data Structure

### Mock Columns (5 columns total)
```typescript
{
  name: string                    // Column name
  type: 'numeric' | 'categorical' | 'datetime' | 'text'
  unique_count: number            // Number of unique values
  null_count: number              // Number of missing values
  total_rows: number              // Total rows in dataset
}
```

### Mock Response
```typescript
{
  columns: Column[]               // Array of column objects
  data: any[]                     // Not used in tests, but part of API response
}
```

## Testing Patterns

### 1. Basic Component Rendering
```typescript
render(
  <ColumnSelector
    datasetId="dataset-1"
    selectedColumns={new Set()}
    onSelectionChange={jest.fn()}
  />
)

await waitFor(() => {
  expect(screen.getByText('age')).toBeInTheDocument()
})
```

### 2. Async Operations (API Calls)
```typescript
// Wait for component to load data
await waitFor(() => {
  expect(global.fetch).toHaveBeenCalled()
})
```

### 3. Debounce Testing (300ms)
```typescript
fireEvent.change(searchInput, { target: { value: 'age' } })

// Wait for debounce to complete
await waitFor(
  () => {
    expect(screen.queryByText('category')).not.toBeInTheDocument()
  },
  { timeout: 400 }  // 300ms debounce + 100ms buffer
)
```

### 4. User Interactions
```typescript
// Checkbox click
fireEvent.click(
  screen.getByRole('checkbox', { name: /Select age/i })
)

// Button click
fireEvent.click(
  screen.getByRole('button', { name: /Select all/i })
)

// Text input
fireEvent.change(searchInput, { target: { value: 'test' } })

// Keyboard event
fireEvent.keyDown(element, { key: 'ArrowDown' })
```

### 5. Callback Verification
```typescript
const onSelectionChange = jest.fn()

// After user action...

expect(onSelectionChange).toHaveBeenCalledWith(
  new Set(['age', 'category'])
)
```

### 6. DOM Element Queries
```typescript
// By role (preferred)
screen.getByRole('checkbox', { name: /Select age/i })
screen.getByRole('button', { name: /Select all/i })
screen.getByRole('textbox', { name: /Search columns/i })

// By text content
screen.getByText('age')
screen.getByText(/5% missing/)

// By container
container.querySelector('[role="option"]')
container.querySelectorAll('[role="option"]')

// Scoped within element
within(element).getByText('Numeric')
```

## Mock Setup

### Before Each Test
```typescript
beforeEach(() => {
  jest.clearAllMocks()
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: jest.fn().mockResolvedValue(mockApiResponse),
  })
})
```

### Custom Mocks for Specific Tests
```typescript
// Mock API error
(global.fetch as jest.Mock).mockRejectedValue(
  new Error('Network error')
)

// Mock invalid response
(global.fetch as jest.Mock).mockResolvedValue({
  ok: true,
  json: jest.fn().mockResolvedValue({ invalid: 'structure' }),
})

// Mock API failure
(global.fetch as jest.Mock).mockResolvedValue({
  ok: false,
  statusText: 'Unauthorized',
})

// Mock authentication failure
const mockGetAuthToken = require('@/lib/auth-helpers').getAuthToken as jest.Mock
mockGetAuthToken.mockResolvedValueOnce(null)
```

## Key Test Helpers

### Finding Elements
```typescript
// Find by role (most reliable)
screen.getByRole('checkbox', { name: 'Select age' })

// Find by label text
screen.getByLabelText('Search columns')

// Find by text content
screen.getByText('age')

// Find by regex
screen.getByText(/5% missing/)

// Find all matching elements
screen.getAllByText('Numeric')  // Multiple numeric columns

// Query without throwing
screen.queryByText('nonexistent')  // Returns null if not found
```

### Assertions
```typescript
// Element presence
expect(element).toBeInTheDocument()
expect(element).not.toBeInTheDocument()

// Element state
expect(checkbox).toBeChecked()
expect(checkbox).not.toBeChecked()
expect(button).toBeDisabled()
expect(button).not.toBeDisabled()

// Element attributes
expect(element).toHaveAttribute('aria-label')
expect(element).toHaveAttribute('role', 'option')
expect(element).toHaveAttribute('aria-selected', 'true')

// Element classes
expect(element).toHaveClass('bg-blue-50')
expect(element).toHaveClass('bg-blue-50', 'border-blue-300')

// Text content
expect(element).toHaveTextContent('age')
expect(element).toHaveValue('search term')

// Callback calls
expect(callback).toHaveBeenCalled()
expect(callback).toHaveBeenCalledWith(expectedArg)
expect(callback).toHaveBeenCalledTimes(2)
expect(callback).toHaveBeenNthCalledWith(1, arg1)
expect(callback).toHaveBeenNthCalledWith(2, arg2)
```

### Async Helpers
```typescript
// Wait for condition
await waitFor(() => {
  expect(screen.getByText('age')).toBeInTheDocument()
}, { timeout: 400 })

// Render with rerender
const { rerender } = render(<Component {...props} />)
rerender(<Component {...newProps} />)

// Get container
const { container } = render(<Component />)
container.querySelector('[role="option"]')
container.querySelectorAll('[role="option"]')
```

## Component Props Used in Tests

```typescript
interface ColumnSelectorProps {
  datasetId: string
  selectedColumns: Set<string>
  onSelectionChange: (columns: Set<string>) => void
  className?: string
}
```

## Example Test Template

```typescript
describe('Feature Name', () => {
  it('should [expected behavior]', async () => {
    // Setup
    const onSelectionChange = jest.fn()

    // Render
    render(
      <ColumnSelector
        datasetId="dataset-1"
        selectedColumns={new Set()}
        onSelectionChange={onSelectionChange}
      />
    )

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('age')).toBeInTheDocument()
    })

    // User interaction
    const ageCheckbox = screen.getByRole('checkbox', {
      name: /Select age/i,
    })
    fireEvent.click(ageCheckbox)

    // Assertion
    expect(onSelectionChange).toHaveBeenCalledWith(new Set(['age']))
  })
})
```

## Debugging Tips

### View Rendered HTML
```typescript
screen.debug()           // Print entire document
screen.debug(element)    // Print specific element
```

### Check Test Queries
```typescript
// These won't work - will show you the queries available
screen.getByText('nonexistent')  // Shows: "Unable to find..."
```

### Wait Debugging
```typescript
await waitFor(
  () => {
    console.log('Checking condition...')
    expect(screen.getByText('age')).toBeInTheDocument()
  },
  { timeout: 5000 }  // Longer timeout to see what's happening
)
```

### Container DOM
```typescript
const { container } = render(<Component />)
console.log(container.innerHTML)  // See full DOM structure
```

## Common Issues and Solutions

### Issue: "Unable to find element"
**Cause:** Component hasn't finished loading
**Solution:** Wrap in `waitFor(() => { ... })`

### Issue: "Multiple elements found"
**Cause:** Multiple columns have same type indicator
**Solution:** Use `getAllByText()` or scope with `within()`

### Issue: Debounce tests failing
**Cause:** Timeout too short
**Solution:** Use `{ timeout: 400 }` for 300ms debounce

### Issue: Callback not called
**Cause:** Event handler not properly triggered
**Solution:** Verify event listeners are on correct element

### Issue: Mock not working
**Cause:** Mock cleared by next test
**Solution:** Ensure `beforeEach()` clears mocks

## Performance Considerations

- Tests run in ~4-5 seconds total
- Async operations properly awaited
- Debounce tests include adequate timeout buffers
- Virtual list rendering limited to 100 items in tests
- No unnecessary re-renders or async waits

## CI/CD Integration

Tests can be run in CI pipelines:

```bash
npm test -- __tests__/components/transformation/ColumnSelector.test.tsx --coverage
```

Expected output:
- 53 tests passing
- Coverage > 85% for component
- No console errors or warnings
