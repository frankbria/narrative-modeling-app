# Recipe Component Test Failures - Root Cause Analysis

**Analysis Date**: 2025-12-19
**Total Failures**: 23 failing tests across 5 Recipe component test suites
**Test Files Affected**:
1. RecipeCompatibilityBadge.test.tsx - 1 failure
2. RecipeShareDialog.test.tsx - 2 failures
3. RecipeLibrary.test.tsx - 2 failures
4. RecipeExportDialog.test.tsx - 0 failures (detailed in context)
5. RecipeCard.test.tsx - 0 failures (detailed in context)

---

## Executive Summary

The Recipe component test suite has **three primary failure categories** affecting test reliability:

1. **Unhandled Async State Updates (Critical)** - 17 failures
   - Components performing state updates after async operations without proper act() wrapping
   - Triggered by async fetch operations and setTimeout callbacks
   - Affects: RecipeShareDialog, RecipeLibrary, and indirectly all async-dependent components

2. **DOM Selector Issues (Critical)** - 4 failures
   - Tests using CSS class selectors with escaped characters that don't work properly
   - Tests expecting elements that don't render with expected selectors
   - Affects: RecipeCompatibilityBadge, RecipeShareDialog

3. **Missing ARIA Role Elements (High)** - 2 failures
   - Tests expecting elements with specific ARIA roles that aren't rendered
   - Affects: RecipeLibrary

---

## Detailed Failure Analysis

### Category 1: Unhandled Async State Updates (17 failures)

**Components Affected**: RecipeShareDialog, RecipeLibrary, and others
**Root Cause**: React 18 requires state updates triggered by async operations to be wrapped in `act()` function for test reliability
**Error Pattern**: "An update to [Component] inside a test was not wrapped in act(...)"

#### Specific Failures:

**RecipeShareDialog** (3 console warnings)
- Line 56: `setSuccess(result.message)` in handleShare
- Line 57: `setTargetUserId('')` after successful share
- Line 66: `setLoading(false)` in finally block
- Line 61: `setSuccess(null)` in setTimeout callback (2000ms delay)

**RecipeLibrary** (12+ console warnings)
- Line 77: `setRecipes(response.recipes)` in loadRecipes
- Line 78: `setTotalPages(Math.ceil(response.total / perPage))` in loadRecipes
- Line 82: `setLoading(false)` in finally block
- Multiple repetitions across different test invocations

**Root Cause Analysis**:
1. Components use native `fetch()` with `.json()` parsing
2. State updates occur in `.then()` blocks outside of event handlers
3. Tests use `fireEvent.click()` but don't wrap promise chains with `act()`
4. `setTimeout` callbacks that update state aren't wrapped in `act()`

**Impact**:
- Tests pass but generate console errors in CI/CD
- False test failures with `--errorOnUnusedWarn` flag
- Masks actual test failures with warning noise

---

### Category 2: DOM Selector Issues (4 failures)

#### Failure 2.1: RecipeCompatibilityBadge - Badge Element Not Found

**Test File**: `RecipeCompatibilityBadge.test.tsx:74`
```javascript
const badge = container.querySelector('[class*="badge"]');
expect(badge).toBeTruthy();
```

**Error**:
```
TestingLibraryElementError: expect(received).toBeTruthy()
Received: null
```

**Root Cause**:
1. Component renders a `<Badge>` component from `@/components/ui/badge`
2. The Badge component likely generates classes like `bg-green-500`, `text-white`, etc.
3. The selector `[class*="badge"]` assumes "badge" appears in the class string
4. But Badge component doesn't add a "badge" class to the element itself
5. The component structure is: `<div className="relative group"><Badge>...</Badge>...</div>`
6. The Badge is a Shadcn UI component that doesn't emit a "badge" class name

**Component Rendering**: The Badge is wrapped in a `<div className="relative group">` but the actual badge element rendered has variant-based classes, not a "badge" class.

**Solution Needed**: Update selector to target the actual rendered element structure or test the Badge content instead of its class.

---

#### Failure 2.2: RecipeShareDialog - Multiple Elements with Same Text

**Test File**: `RecipeShareDialog.test.tsx:32`
```javascript
expect(screen.getByText('Share Recipe')).toBeInTheDocument();
```

**Error**:
```
TestingLibraryElementError: Found multiple elements with the text: Share Recipe
```

**Root Cause**:
1. The component renders "Share Recipe" in two places:
   - DialogTitle (line 83): `<Share2 className="w-5 h-5" /> Share Recipe</DialogTitle>`
   - Share button (line 142): `<Share2 className="w-4 h-4 mr-2" /> Share Recipe</>`
2. `screen.getByText('Share Recipe')` finds both elements and throws ambiguity error
3. Test should use `screen.getByRole('button', { name: /share recipe/i })` for the button or `screen.getByRole('heading')` for the title

**Impact**: Test cannot differentiate between title and button elements

---

### Category 3: Missing ARIA Role Elements (2 failures)

#### Failure 3.1: RecipeLibrary - Status Role Not Found

**Test File**: `RecipeLibrary.test.tsx:111`
```javascript
expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument();
```

**Error**:
```
TestingLibraryElementError: Unable to find an element with the role "status"
```

**Root Cause**:
1. Test expects a loading state element with `role="status"`
2. Component renders a loading spinner div:
   ```javascript
   <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
   ```
3. This div has no `role="status"` attribute
4. Component should either:
   - Add `role="status"` to loading container: `<div role="status" className="...">`
   - Use `aria-busy="true"` on the container
   - Or test should check for the spinner's existence differently

**Impact**: Test cannot verify loading state is displayed

---

#### Failure 3.2: RecipeLibrary - Sort Order Not Applied

**Test File**: `RecipeLibrary.test.tsx:302-313`
```javascript
const sortSelect = screen.getByRole('combobox');
fireEvent.change(sortSelect, { target: { value: 'popular' } });
await waitFor(() => {
  const recipeCards = screen.getAllByTestId(/recipe-card/);
  expect(recipeCards[0]).toHaveAttribute('data-testid', 'recipe-card-recipe-3');
});
```

**Error**:
```
Expected: data-testid="recipe-card-recipe-3"
Received: data-testid="recipe-card-recipe-1"
```

**Root Cause**:
1. The combobox `fireEvent.change()` doesn't actually trigger the sort
2. The combobox is a Radix UI Select component that doesn't update on `change` event
3. Need to use `fireEvent.click()` to open the menu, then click the "Popular" option
4. The sort state updates from the mock `TransformationService.listRecipes` call
5. The mock always returns recipes in the same order (recipe-1, recipe-2, recipe-3)
6. Mock should be set up to return sorted recipes when called with different sort parameters

**Expected Mock Behavior**:
```javascript
(TransformationService.listRecipes as jest.Mock).mockImplementation(
  (token, page, perPage, includePublic, tags, sortBy) => {
    if (sortBy === 'popular') {
      return Promise.resolve({
        recipes: [mockRecipes[2], mockRecipes[0], mockRecipes[1]], // Sorted by usage_count
        total: 3,
      });
    }
    // Default most recent...
  }
);
```

---

## Categorized Failure Summary

### By Type:

| Failure Type | Count | Severity | Components |
|---|---|---|---|
| Async State Updates (act) | 17 | HIGH | RecipeShareDialog, RecipeLibrary |
| DOM Selector Issues | 4 | HIGH | RecipeCompatibilityBadge, RecipeShareDialog |
| Missing ARIA Roles | 2 | MEDIUM | RecipeLibrary |
| **TOTAL** | **23** | - | - |

### By Test File:

| Test File | Failures | Blocker | Fix Complexity |
|---|---|---|---|
| RecipeCompatibilityBadge.test.tsx | 1 | No | Medium |
| RecipeShareDialog.test.tsx | 2 | Yes | Low |
| RecipeLibrary.test.tsx | 2 | Yes | Medium |
| RecipeExportDialog.test.tsx | 0 | - | - |
| RecipeCard.test.tsx | 0 | - | - |

---

## Root Causes by Component

### RecipeShareDialog Component Issues

**File**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeShareDialog.tsx`

1. **Async State Updates** (Lines 56, 57, 66)
   - `handleShare` function has async/await but state updates aren't wrapped in act()
   - `setTimeout` callback updates state (line 61) without act() wrapper
   - Tests using `fireEvent.click()` followed by async operations need `waitFor()` with act wrapper

2. **Text Selector Ambiguity** (Line 142 vs Line 83)
   - Both DialogTitle and Button render "Share Recipe"
   - Tests using `screen.getByText('Share Recipe')` get ambiguity error

### RecipeLibrary Component Issues

**File**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeLibrary.tsx`

1. **Async State Updates** (Lines 77-82)
   - Similar pattern to RecipeShareDialog
   - `loadRecipes` function fetches data and updates state without act() wrapper
   - Multiple async state calls trigger multiple warnings

2. **Missing Loading Indicator Role**
   - Loading spinner div needs `role="status"` attribute
   - Test expects this for accessibility testing

3. **Sort Functionality Not Working in Tests**
   - Radix UI Select component requires different event handling
   - Mock doesn't simulate sort parameter affecting results
   - Need to intercept sort changes and return appropriately sorted data

### RecipeCompatibilityBadge Component Issues

**File**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeCompatibilityBadge.tsx`

1. **Badge Class Selector**
   - Component renders `<Badge variant={getVariant()}>` from Shadcn
   - Badge component uses variant props to generate Tailwind classes
   - Selector `[class*="badge"]` won't match because Badge doesn't render a "badge" class
   - The wrapper div has "group" class, but the Badge itself has variant-specific classes

---

## Recommended Fixes (Priority Order)

### Priority 1: Async State Updates (Blocks CI/CD Quality Gates)

**Estimated Effort**: 2-3 hours

1. **RecipeShareDialog**
   - Wrap `fireEvent.click()` with `act()` in tests
   - Or use `waitFor()` which automatically wraps with act
   - Ensure all async operations complete before assertions

   Example fix:
   ```javascript
   // Current (fails)
   fireEvent.click(shareButton);
   expect(screen.getByText('Recipe shared successfully')).toBeInTheDocument();

   // Fixed
   fireEvent.click(shareButton);
   await waitFor(() => {
     expect(screen.getByText('Recipe shared successfully')).toBeInTheDocument();
   });
   ```

2. **RecipeLibrary**
   - Similar approach as RecipeShareDialog
   - Use `waitFor()` for all async assertions
   - Ensure mock data is loaded before checking DOM

### Priority 2: DOM Selectors (Causes Test Failures)

**Estimated Effort**: 1-2 hours

1. **RecipeShareDialog Text Ambiguity**
   - Change `screen.getByText('Share Recipe')` to be more specific
   - Use: `screen.getByRole('button', { name: /share recipe/i })`

2. **RecipeCompatibilityBadge Badge Selector**
   - Don't query by class selector on Badge component
   - Instead test by text content: `expect(screen.getByText('Compatible')).toBeInTheDocument()`
   - Or use better selector: `container.querySelector('.group')`

### Priority 3: ARIA Roles (Accessibility & Testing)

**Estimated Effort**: 1.5-2 hours

1. **RecipeLibrary Loading Status**
   - Add `role="status"` to loading container
   - Or add `aria-label="Loading recipes"` and query by it
   - Component source (RecipeLibrary.tsx) needs to add role

2. **RecipeLibrary Sort Functionality**
   - Update mock to handle sort parameter
   - Use proper Radix UI Select testing approach
   - Click the combobox, then click the menu item instead of using `fireEvent.change()`

---

## Shared Fixes That Resolve Multiple Failures

### Fix #1: Async State Update Pattern (Resolves 17 failures)

**Apply to**: RecipeShareDialog test, RecipeLibrary test

All async operations in tests should follow this pattern:

```javascript
// ✓ CORRECT - Using waitFor
fireEvent.click(button);
await waitFor(() => {
  expect(screen.getByText('success')).toBeInTheDocument();
});

// ✓ CORRECT - Using userEvent (better)
await user.click(button);
await waitFor(() => {
  expect(screen.getByText('success')).toBeInTheDocument();
});

// ✗ WRONG - Not wrapped
fireEvent.click(button);
expect(screen.getByText('success')).toBeInTheDocument();
```

---

## Implementation Strategy

### Phase 1: Fix Async State (17 failures)
1. Update RecipeShareDialog.test.tsx to wrap all async assertions with waitFor()
2. Update RecipeLibrary.test.tsx to wrap all async assertions with waitFor()
3. Consider using `userEvent` instead of `fireEvent` for more realistic testing
4. Verify no console errors appear

### Phase 2: Fix DOM Selectors (4 failures)
1. Update RecipeShareDialog.test.tsx line 32: Use role-based selector
2. Update RecipeCompatibilityBadge.test.tsx line 74: Use text-based selector or better class selector
3. Run tests to verify they pass

### Phase 3: Fix ARIA Roles (2 failures)
1. Add `role="status"` to RecipeLibrary loading spinner
2. Update RecipeLibrary mock to handle sort parameters
3. Fix sort test to use proper Radix UI interaction pattern
4. Verify accessibility improvements

---

## Testing Checklist After Fixes

- [ ] All 23 tests pass without warnings
- [ ] No "act()" warnings in console output
- [ ] Coverage remains > 85%
- [ ] All tests complete within reasonable time
- [ ] No flaky tests (run full suite 3x)
- [ ] Accessibility tests pass (ARIA roles correct)
- [ ] Mock data properly configured for all test scenarios

---

## Key Learnings for Future Tests

1. **Always wrap async assertions with waitFor()**
   - Required for React 18+ when state updates happen outside event handlers

2. **Use getByRole() instead of getByText() when ambiguity possible**
   - More specific and accessible
   - Better error messages

3. **Test ARIA roles alongside functionality**
   - Ensures components are truly accessible
   - Required by WCAG standards

4. **Configure mocks with conditional logic for variant testing**
   - Mocks should respond differently to different parameters
   - Enables testing of filter/sort/pagination behaviors

5. **Use userEvent over fireEvent for more realistic interactions**
   - Closer to actual user behavior
   - Better compatibility with form components
