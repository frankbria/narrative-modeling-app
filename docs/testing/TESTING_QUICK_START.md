# ColumnSelector Unit Tests - Quick Start Guide

## Test Results
✅ **All 53 Tests Passing**
- Duration: ~4.3 seconds
- Coverage: Comprehensive (rendering, selection, filtering, keyboard, accessibility, API, edge cases)

## Files Created

### Test Implementation
1. **Main Test Suite**
   - Path: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/__tests__/components/transformation/ColumnSelector.test.tsx`
   - Lines: ~1,300
   - Tests: 53
   - All passing

2. **React Window Mock**
   - Path: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/__mocks__/react-window.tsx`
   - Purpose: Mock virtual list for testing without actual virtualization
   - Status: Updated to fix React key warnings

### Documentation
1. **Test Implementation Summary**
   - Path: `/home/frankbria/projects/narrative-modeling-app/TEST_IMPLEMENTATION_SUMMARY.md`
   - Content: Overview of all test categories and organization

2. **Test Structure Guide**
   - Path: `/home/frankbria/projects/narrative-modeling-app/TEST_STRUCTURE_GUIDE.md`
   - Content: Detailed guide on test patterns, utilities, and examples

3. **This Quick Start Guide**
   - Path: `/home/frankbria/projects/narrative-modeling-app/TESTING_QUICK_START.md`

## Running Tests

### Run ColumnSelector Tests Only
```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/frontend
npm test -- __tests__/components/transformation/ColumnSelector.test.tsx --no-coverage
```

### Run All Frontend Tests
```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/frontend
npm test
```

### Run with Coverage Report
```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/frontend
npm test -- __tests__/components/transformation/ColumnSelector.test.tsx --coverage
```

### Run Single Test
```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/frontend
npm test -- __tests__/components/transformation/ColumnSelector.test.tsx -t "should toggle column selection"
```

### Watch Mode
```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/frontend
npm test -- __tests__/components/transformation/ColumnSelector.test.tsx --watch
```

## Test Categories (53 Total)

| Category | Count | Examples |
|----------|-------|----------|
| Rendering & Loading | 6 | Loading state, column display, type indicators |
| Error Handling | 4 | Network errors, invalid responses, auth failure |
| Column Selection | 3 | Toggle, deselect, visual highlighting |
| Search & Filter | 7 | By name, by type, case-insensitive, debounce |
| Select All/Deselect | 5 | Button states, filter respect, disable logic |
| Keyboard Navigation | 4 | Arrow keys, Escape, Space, attributes |
| Column Types | 4 | Numeric, categorical, datetime, text colors |
| Missing Values | 3 | Display percentage, red styling, no missing |
| API Integration | 3 | Fetch calls, headers, empty datasetId |
| Accessibility | 5 | ARIA labels, roles, multiselectable, hint text |
| Props & Customization | 3 | Custom className, defaults, prop updates |
| Edge Cases | 5 | Special chars, long names, many columns, 100% missing |
| Integration | 3 | Multiple selections, filter state, datasetId changes |

## Component Under Test

**ColumnSelector Component**
- Path: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/transformation/ColumnSelector.tsx`
- Purpose: Multi-select column picker with search, filtering, and keyboard navigation
- Key Features:
  - Virtualized list (1000+ columns support)
  - Search with 300ms debounce
  - Type-based color coding
  - Missing value indicators
  - Full keyboard accessibility
  - Select All / Deselect All buttons

## Key Test Patterns

### Async Testing
```typescript
await waitFor(() => {
  expect(screen.getByText('age')).toBeInTheDocument()
}, { timeout: 400 })
```

### User Interactions
```typescript
fireEvent.click(screen.getByRole('checkbox', { name: /Select age/i }))
fireEvent.change(searchInput, { target: { value: 'test' } })
fireEvent.keyDown(element, { key: 'ArrowDown' })
```

### Mocking
```typescript
const onSelectionChange = jest.fn()
expect(onSelectionChange).toHaveBeenCalledWith(new Set(['age']))
```

## Dependencies

```json
{
  "jest": "^30.2.0",
  "@testing-library/react": "^16.3.0",
  "@testing-library/jest-dom": "^6.9.1",
  "react": "^19.2.0",
  "react-window": "^1.8.10"
}
```

## Component Props Tested

```typescript
interface ColumnSelectorProps {
  datasetId: string                          // Dataset ID for API calls
  selectedColumns: Set<string>               // Currently selected columns
  onSelectionChange: (columns: Set<string>) => void  // Selection callback
  className?: string                         // Optional CSS class
}
```

## Mock Data

5 Test Columns:
1. `age` - numeric, 5% missing (95 unique)
2. `category` - categorical, 2% missing (10 unique)
3. `created_at` - datetime, 0% missing (500 unique)
4. `description` - text, 5% missing (800 unique)
5. `score` - numeric, 0% missing (100 unique)

## Common Test Assertions

```typescript
// Element presence
expect(element).toBeInTheDocument()

// User states
expect(checkbox).toBeChecked()
expect(button).toBeDisabled()

// ARIA attributes
expect(element).toHaveAttribute('aria-label')
expect(element).toHaveAttribute('aria-selected', 'true')

// Visual styling
expect(element).toHaveClass('bg-blue-50', 'border-blue-300')

// Callbacks
expect(callback).toHaveBeenCalledWith(new Set(['age']))
```

## Debugging Tips

### See Rendered HTML
```typescript
screen.debug()           // Full page
screen.debug(element)    // Specific element
```

### Check Test Queries
```typescript
// This will show what queries are available
screen.getByText('nonexistent')
```

### Container Access
```typescript
const { container } = render(<Component />)
container.querySelector('[role="option"]')
```

## What's Covered

✅ Component rendering and initialization
✅ Data loading with API calls
✅ Error handling and recovery
✅ Column selection and deselection
✅ Search and filtering with debounce
✅ Select All / Deselect All functionality
✅ Button state management
✅ Keyboard navigation (arrows, space, escape)
✅ Column type indicators and colors
✅ Missing value display and calculations
✅ ARIA attributes and accessibility
✅ Custom props and class names
✅ Edge cases (special chars, long names, many columns)
✅ Integration scenarios (multi-select, filter state, datasetId changes)

## What's NOT Covered (E2E Scope)

- Full data preparation workflow end-to-end
- Actual virtual scrolling performance
- Real API integration
- Multi-user scenarios
- Network latency scenarios

These would be covered by E2E tests using Playwright.

## Test Maintenance

### Adding New Tests
1. Add to appropriate describe block
2. Follow naming pattern: `should [behavior]`
3. Use existing mock data
4. Wrap async with `waitFor`
5. Clean up with `beforeEach`

### Updating Tests
1. Search for test by name
2. Update expectations, not implementation details
3. Keep mock data consistent
4. Verify debounce timeouts (300ms + 100ms buffer)

### Debugging Failures
1. Check async operations have `waitFor`
2. Verify debounce timeout is sufficient (400ms)
3. Check mock setup in `beforeEach`
4. Use `screen.debug()` to see actual DOM
5. Verify test data matches expectations

## CI/CD Integration

Tests ready for CI/CD:
```bash
npm test -- __tests__/components/transformation/ColumnSelector.test.tsx --coverage
```

Expected in CI:
- All 53 tests passing
- Coverage > 85%
- No console errors
- Execution time < 10 seconds

## Performance

- Test Suite Duration: ~4.3 seconds
- Per Test Average: ~80 ms
- Slowest Tests: Large dataset tests (250-350ms)
- Fastest Tests: Rendering checks (3-15ms)

## Next Steps

1. **Optional E2E Tests**: Create Playwright tests for full workflow
2. **Integration Tests**: Test with real backend API
3. **Visual Regression**: Add snapshot tests for column type indicators
4. **Performance Tests**: Benchmark with 1000+ columns
5. **Accessibility Audit**: Use axe-core for detailed accessibility checks

## Support & References

- Jest Docs: https://jestjs.io/docs/getting-started
- React Testing Library: https://testing-library.com/react
- Test Patterns: See TEST_STRUCTURE_GUIDE.md
- Implementation Details: See TEST_IMPLEMENTATION_SUMMARY.md

---

**Created:** December 2025
**Status:** All tests passing (53/53)
**Ready for:** Production use and CI/CD integration
