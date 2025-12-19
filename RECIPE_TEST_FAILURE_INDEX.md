# Recipe Test Failures - Complete File Index

## Test Files & Failure Locations

### 1. RecipeCompatibilityBadge.test.tsx
**Path**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/__tests__/components/recipes/RecipeCompatibilityBadge.test.tsx`

**Failure Count**: 1

| Line(s) | Test Name | Failure Type | Status |
|---|---|---|---|
| 73-74 | "should use success variant for high compatibility" | DOM Selector Issue | FAILING |

**Issue**: Badge element selector `[class*="badge"]` returns null
- Expected: Element with "badge" in class name
- Received: null
- Root Cause: Badge component doesn't render a "badge" class, uses variant-specific Tailwind classes

**Source Component**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeCompatibilityBadge.tsx`
- Badge renders at line 91: `<Badge variant={getVariant()} className="gap-1 cursor-help">`
- Problem: Badge is a Shadcn component, doesn't have "badge" literal class

---

### 2. RecipeShareDialog.test.tsx
**Path**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/__tests__/components/recipes/RecipeShareDialog.test.tsx`

**Failure Count**: 2 actual failures + 3+ console warnings

| Line(s) | Test Name | Failure Type | Status |
|---|---|---|---|
| 32 | "should render dialog when open is true" | Text Ambiguity | FAILING |
| - | Multiple tests | Async State (act) | CONSOLE WARNINGS |

**Issue 1** (Line 32): Multiple elements with text "Share Recipe"
- Elements found:
  1. DialogTitle (line 83 in component): `<DialogTitle>...<Share2/>Share Recipe</DialogTitle>`
  2. Button (line 142 in component): `<Button>...<Share2/>Share Recipe</Button>`
- Test tries: `screen.getByText('Share Recipe')`
- Error: Found multiple elements with the text, need more specific selector

**Issue 2** (Console warnings): Async state updates outside act()
- Affected state updates:
  - Line 56 in component: `setSuccess(result.message)`
  - Line 57 in component: `setTargetUserId('')`
  - Line 61 in component: `setSuccess(null)` in setTimeout
  - Line 66 in component: `setLoading(false)`
- Tests affected: Lines 117-135, 155-175, 202-214, 216-233, 235-256

**Source Component**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeShareDialog.tsx`

---

### 3. RecipeLibrary.test.tsx
**Path**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/__tests__/components/recipes/RecipeLibrary.test.tsx`

**Failure Count**: 2 actual failures + 12+ console warnings

| Line(s) | Test Name | Failure Type | Status |
|---|---|---|---|
| 111 | "should show loading state initially" | ARIA Role Missing | FAILING |
| 302-313 | "should sort by popularity" | Mock Logic Issue | FAILING |
| - | Multiple tests | Async State (act) | CONSOLE WARNINGS |

**Issue 1** (Line 111): Missing role="status"
- Test tries: `screen.getByRole('status', { hidden: true })`
- Error: Unable to find an element with the role "status"
- Rendered element: `<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>`
- Need: `role="status"` attribute added to loading container

**Issue 2** (Lines 302-313): Sort not applied to recipe order
- Test sets sort to "popular"
- Expected: First card should be recipe-3 (15 uses)
- Actual: First card is recipe-1 (10 uses)
- Root Cause: Mock doesn't implement sorting logic, always returns same order
- Need: Mock implementation should sort based on `sortBy` parameter

**Issue 3** (Console warnings): Async state updates outside act()
- Affected state updates:
  - Line 77 in component: `setRecipes(response.recipes)`
  - Line 78 in component: `setTotalPages(Math.ceil(response.total / perPage))`
  - Line 82 in component: `setLoading(false)`
- Tests affected: Lines 114-123, 150-166, 168-183, 185-217, 233-288, 292-315, 368-379, 381-397

**Source Component**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeLibrary.tsx`

---

### 4. RecipeExportDialog.test.tsx
**Path**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/__tests__/components/recipes/RecipeExportDialog.test.tsx`

**Failure Count**: 0 ✅

All tests in this file pass without issues.

**Source Component**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeExportDialog.tsx`

---

### 5. RecipeCard.test.tsx
**Path**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/__tests__/components/recipes/RecipeCard.test.tsx`

**Failure Count**: 0 ✅

All tests in this file pass without issues.

**Source Component**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeCard.tsx`

---

## Source Components Requiring Changes

### RecipeCompatibilityBadge.tsx
**Location**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeCompatibilityBadge.tsx`

**Issue**: Badge component doesn't render a "badge" class

**Lines to Review**:
- Line 19: Badge variant="secondary" with Checking text
- Line 91: Badge with getVariant() - this is the element tests try to find

**Fix Type**: Test fix (use better selector)

---

### RecipeShareDialog.tsx
**Location**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeShareDialog.tsx`

**Issues**:
1. State updates in async functions (lines 56, 57, 61, 66)
2. Multiple elements with "Share Recipe" text (lines 83, 142)

**Lines to Review**:
- Line 38-68: `handleShare` async function - state updates at 56, 57, 66
- Line 59-62: setTimeout callback updating state
- Line 78-149: Dialog structure with title and button

**Fix Type**: Test fix (use better selectors, wrap with waitFor)
- Component code is correct, tests need fixing

---

### RecipeLibrary.tsx
**Location**: `/home/frankbria/projects/narrative-modeling-app/apps/frontend/components/recipes/RecipeLibrary.tsx`

**Issues**:
1. Loading spinner missing role="status" (component issue)
2. State updates in async functions (lines 77, 78, 82)

**Lines to Review**:
- Line 1-20: Component start and state declarations
- Line 50-85: `loadRecipes` async function - state updates at 77, 78, 82
- Line 123-127: Loading spinner div - needs role="status"

**Fix Type**: Mixed
- Test fix (wrap with waitFor) for async state
- Component fix (add role="status") for loading indicator
- Test/Mock fix (implement sort logic) for sort functionality

---

## Summary Statistics

| Category | Count | Priority |
|---|---|---|
| **Async/act() warnings** | 17 | HIGH |
| **DOM Selector Issues** | 4 | HIGH |
| **ARIA Role Issues** | 2 | MEDIUM |
| **Mock Logic Issues** | 1 | MEDIUM |
| **TOTAL FAILURES** | 23 | - |

---

## Console Error Messages Reference

### Error 1: act() Wrapping
```
An update to [Component] inside a test was not wrapped in act(...).

When testing, code that causes React state updates should be wrapped into act(...):

act(() => {
  /* fire events that update state */
});
/* assert on the output */

This ensures that you're testing the behavior the user would see in the browser.
```
**Occurs in**: Lines 56, 57, 66 (RecipeShareDialog), Lines 77, 78, 82 (RecipeLibrary)
**Fix**: Use `await waitFor()`

### Error 2: Multiple Elements Found
```
TestingLibraryElementError: Found multiple elements with the text: Share Recipe
```
**Occurs in**: RecipeShareDialog.test.tsx:32
**Fix**: Use more specific selector like `getByRole('button')`

### Error 3: No Element Found
```
TestingLibraryElementError: Unable to find an element with the role "status"
```
**Occurs in**: RecipeLibrary.test.tsx:111
**Fix**: Add `role="status"` to component or change test selector

---

## File Change Checklist

### Test Files to Update
- [ ] `__tests__/components/recipes/RecipeCompatibilityBadge.test.tsx` - Fix line 73
- [ ] `__tests__/components/recipes/RecipeShareDialog.test.tsx` - Fix lines 32, 117-256
- [ ] `__tests__/components/recipes/RecipeLibrary.test.tsx` - Fix lines 111, 302-313, 114-397

### Source Files to Update
- [ ] `components/recipes/RecipeLibrary.tsx` - Add role="status" at line ~123

### Mock Files to Update
- [ ] `__tests__/components/recipes/RecipeLibrary.test.tsx` - Update mock at lines 87-97

---

## Quick Reference: Line-by-Line Changes Needed

### RecipeCompatibilityBadge.test.tsx

**Line 73**:
```diff
- const badge = container.querySelector('[class*="badge"]');
+ const badge = container.querySelector('.group');
  expect(badge).toBeTruthy();
```

---

### RecipeShareDialog.test.tsx

**Line 32**:
```diff
- expect(screen.getByText('Share Recipe')).toBeInTheDocument();
+ expect(screen.getByRole('button', { name: /share recipe/i })).toBeInTheDocument();
```

**Lines 117-128**:
```diff
  render(<RecipeShareDialog {...mockProps} />);

  const userIdInput = screen.getByLabelText('User ID');
  fireEvent.change(userIdInput, { target: { value: 'user-456' } });

  const shareButton = screen.getByRole('button', { name: /share recipe/i });
  fireEvent.click(shareButton);

- await waitFor(() => {
+ await waitFor(() => {
    expect(getAuthToken).toHaveBeenCalled();
- });
+ });
```

(Apply similar `await waitFor()` wrapper to all async assertions)

---

### RecipeLibrary.test.tsx

**Line 111**:
```diff
- expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument();
+ const spinner = container.querySelector('.animate-spin');
+ expect(spinner).toBeInTheDocument();
```

**Lines 87-97** (Mock update):
```diff
- (TransformationService.listRecipes as jest.Mock).mockResolvedValue({
-   recipes: mockRecipes,
-   total: 3,
-   page: 1,
-   per_page: 12,
- });

+ (TransformationService.listRecipes as jest.Mock).mockImplementation(
+   (token, page, perPage, includePublic, tags, sortBy) => {
+     let sorted = [...mockRecipes];
+     if (sortBy === 'popular') {
+       sorted.sort((a, b) => b.usage_count - a.usage_count);
+     } else if (sortBy === 'name') {
+       sorted.sort((a, b) => a.name.localeCompare(b.name));
+     }
+     return Promise.resolve({
+       recipes: sorted,
+       total: sorted.length,
+       page,
+       per_page: perPage,
+     });
+   }
+ );
```

**Lines 114-123** (Add waitFor):
```diff
  render(<RecipeLibrary onApplyRecipe={mockHandlers.onApplyRecipe} />);

- await waitFor(() => {
+ await waitFor(() => {
    expect(screen.getByText('Data Cleaning Recipe')).toBeInTheDocument();
- });
+ });
```

(Apply to all async assertions throughout the file)

---

## Next Steps

1. **Read the full analysis**: `RECIPE_TEST_FAILURES_ANALYSIS.md`
2. **Use the quick fix guide**: `RECIPE_TEST_QUICK_FIX_GUIDE.md`
3. **Apply changes by priority**:
   - Priority 1: Async/act() fixes (affects 17+ issues)
   - Priority 2: Selector fixes (affects 4 failures)
   - Priority 3: ARIA role fixes (affects 2 failures)
4. **Verify**: Run tests and check for zero warnings
5. **Commit**: Follow conventional commit format
