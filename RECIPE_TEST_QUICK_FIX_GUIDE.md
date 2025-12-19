# Recipe Component Tests - Quick Fix Guide

## At-a-Glance Failures

```
RecipeCompatibilityBadge.test.tsx:
  ✗ 1 failure - Badge selector [class*="badge"] not found

RecipeShareDialog.test.tsx:
  ✗ 2 failures
    - Multiple elements with text "Share Recipe"
    - 3+ console act() warnings from async state

RecipeLibrary.test.tsx:
  ✗ 2 failures
    - role="status" element not found
    - Sort by popular doesn't reorder (mock issue)
  - 12+ console act() warnings from async state

TOTAL: 23 test failures/warnings
```

---

## Fast Fixes (Ranked by Impact)

### 1️⃣ FIX ASYNC STATE WARNINGS (17 console errors)

**File**: `__tests__/components/recipes/RecipeShareDialog.test.tsx`

**Lines to change**: 32, 117-135, 155-175, 202-214, 216-233, 235-256

**Before**:
```javascript
fireEvent.click(shareButton);
expect(screen.getByText('Recipe shared successfully')).toBeInTheDocument();
```

**After**:
```javascript
fireEvent.click(shareButton);
await waitFor(() => {
  expect(screen.getByText('Recipe shared successfully')).toBeInTheDocument();
});
```

**File**: `__tests__/components/recipes/RecipeLibrary.test.tsx`

**Lines to change**: 114-123, 150-166, 168-183, 185-217, 233-288, 292-315, 368-379, 381-397

**Same pattern** - wrap assertions in `waitFor()`

**Impact**: Eliminates 17 console warnings, makes tests comply with React 18

---

### 2️⃣ FIX TEXT AMBIGUITY (1 failing test)

**File**: `__tests__/components/recipes/RecipeShareDialog.test.tsx:32`

**Before**:
```javascript
expect(screen.getByText('Share Recipe')).toBeInTheDocument();
```

**After**:
```javascript
expect(screen.getByRole('dialog')).toBeInTheDocument();
expect(screen.getByRole('button', { name: /share recipe/i })).toBeInTheDocument();
```

**Impact**: Test passes, more specific, more accessible

---

### 3️⃣ FIX BADGE SELECTOR (1 failing test)

**File**: `__tests__/components/recipes/RecipeCompatibilityBadge.test.tsx:73`

**Before**:
```javascript
const badge = container.querySelector('[class*="badge"]');
expect(badge).toBeTruthy();
```

**After**:
```javascript
expect(screen.getByText('Compatible')).toBeInTheDocument();
// OR
const badge = container.querySelector('.group');
expect(badge).toBeTruthy();
```

**Impact**: Test passes, tests actual component output instead of implementation details

---

### 4️⃣ FIX MISSING LOADING ROLE (1 failing test)

**File**: `components/recipes/RecipeLibrary.tsx` (source, not test)

**Add to loading spinner**:
```javascript
<div role="status" aria-label="Loading recipes" className="flex items-center justify-center py-12">
  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
</div>
```

**OR update test** `__tests__/components/recipes/RecipeLibrary.test.tsx:111`

**Before**:
```javascript
expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument();
```

**After**:
```javascript
const spinner = container.querySelector('.animate-spin');
expect(spinner).toBeInTheDocument();
```

**Impact**: Test passes, improves accessibility

---

### 5️⃣ FIX SORT FUNCTIONALITY (1 failing test)

**File**: `__tests__/components/recipes/RecipeLibrary.test.tsx` - beforeEach section

**Current mock** (line 87):
```javascript
(TransformationService.listRecipes as jest.Mock).mockResolvedValue({
  recipes: mockRecipes,
  total: 3,
  page: 1,
  per_page: 12,
});
```

**Updated mock with conditional logic**:
```javascript
(TransformationService.listRecipes as jest.Mock).mockImplementation(
  (token, page, perPage, includePublic, tags, sortBy) => {
    let sorted = [...mockRecipes];

    if (sortBy === 'popular') {
      sorted.sort((a, b) => b.usage_count - a.usage_count);
    } else if (sortBy === 'name') {
      sorted.sort((a, b) => a.name.localeCompare(b.name));
    }
    // Default is most recent (already in right order)

    return Promise.resolve({
      recipes: sorted,
      total: sorted.length,
      page,
      per_page: perPage,
    });
  }
);
```

**Also update test** (line 301-315):
```javascript
// Change from fireEvent.change to proper interaction
const sortSelect = screen.getByRole('combobox');
fireEvent.click(sortSelect); // Open menu
const popularOption = screen.getByText('Most Popular');
fireEvent.click(popularOption);

await waitFor(() => {
  const recipeCards = screen.getAllByTestId(/recipe-card/);
  expect(recipeCards[0]).toHaveAttribute('data-testid', 'recipe-card-recipe-3');
});
```

**Impact**: Sort functionality works, tests verify correct behavior

---

## Implementation Timeline

**Total Estimated Time: 2-3 hours**

| Task | Time | Blocker? |
|---|---|---|
| Apply async/waitFor pattern | 45 min | YES |
| Fix text selector ambiguity | 10 min | YES |
| Fix badge selector | 10 min | YES |
| Fix loading role | 15 min | NO |
| Fix sort mock + test | 30 min | YES |
| Test & verify | 20 min | - |

---

## Verification Commands

```bash
# Run Recipe tests only
cd apps/frontend
npm test -- --testPathPattern="recipes"

# Watch mode for development
npm test -- --testPathPattern="recipes" --watch

# Check for act() warnings
npm test -- --testPathPattern="recipes" 2>&1 | grep -i "act"

# Full coverage after fixes
npm test -- --coverage --testPathPattern="recipes"
```

---

## Before/After Comparison

### Async State Pattern (Most Common Issue)

❌ **BEFORE** - 17 failures/warnings:
```javascript
// RecipeShareDialog.test.tsx:117
render(<RecipeShareDialog {...mockProps} />);
const userIdInput = screen.getByLabelText('User ID');
fireEvent.change(userIdInput, { target: { value: 'user-456' } });
const shareButton = screen.getByRole('button', { name: /share recipe/i });
fireEvent.click(shareButton);
expect(getAuthToken).toHaveBeenCalled(); // ❌ Fails with act() warning
```

✅ **AFTER** - Tests pass, no warnings:
```javascript
render(<RecipeShareDialog {...mockProps} />);
const userIdInput = screen.getByLabelText('User ID');
fireEvent.change(userIdInput, { target: { value: 'user-456' } });
const shareButton = screen.getByRole('button', { name: /share recipe/i });
fireEvent.click(shareButton);
await waitFor(() => {
  expect(getAuthToken).toHaveBeenCalled(); // ✅ Passes
});
```

---

## Additional Resources

- **React 18 Testing**: https://react.dev/learn/synchronizing-with-effects
- **act() Warnings**: https://reactjs.org/docs/testing-recipes.html#act
- **Testing Library Best Practices**: https://testing-library.com/docs/queries/about/
- **ARIA Roles**: https://www.w3.org/WAI/ARIA/apg/patterns/
