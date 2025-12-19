# TransformationConfigDialog - Quick Reference Guide

## Test Failure Categories

### Category 1: act() Warnings (15-20 tests fail)
**Files Affected**:
- __tests__/transformation/TransformationConfigDialog.test.tsx

**Failing Tests**:
- "renders select dropdown with enum options"
- "selects enum value"
- "shows error when required field is empty"
- "prevents submission with validation errors"
- All user interaction tests

**Quick Fix**:
```typescript
// CHANGE FROM:
await user.click(button);
await waitFor(() => {
  expect(screen.getByText('text')).toBeInTheDocument();
});

// CHANGE TO:
await user.click(button);
expect(await screen.findByText('text')).toBeInTheDocument();
```

**Time**: 30 min | **Difficulty**: Easy

---

### Category 2: Element Not Found (20-25 tests fail)
**Pattern**: `Unable to find an element with role "combobox"`

**Failing Tests**:
- "renders text input for string type parameters"
- "renders select dropdown for enum type parameters"
- "renders number input for numeric type"
- All Select-based field tests

**Quick Fix**:
```typescript
// CHANGE FROM:
const field = screen.getByRole('combobox', { name: /label/i });

// CHANGE TO:
const field = screen.getByTestId('field-select-trigger');

// ADD TO COMPONENT:
<SelectTrigger
  data-testid="field-select-trigger"
  role="combobox"  // Ensure role is present
>
```

**Time**: 90 min | **Difficulty**: Medium

---

### Category 3: Multi-Select Issues (5-8 tests fail)
**Pattern**: Custom component lacks ARIA attributes

**Failing Tests**:
- "renders multi-select for array type with string items"
- "opens and closes multi-select dropdown"
- "selects columns in multi-select"
- "supports select all in multi-select"

**Quick Fix**:
```typescript
// ADD TO MULTISELECT TRIGGER BUTTON:
role="combobox"
aria-label={`Select ${placeholder}`}
data-testid={`${id}-trigger`}

// ADD TO CHECKBOXES:
aria-label={option}

// ADD TO SELECT ALL BUTTON:
aria-label={value.length === filteredOptions.length ? 'Deselect All' : 'Select All'}
data-testid={`${id}-select-all`}
```

**Time**: 120 min | **Difficulty**: High

---

### Category 4: Button Selector Issues (5-8 tests fail)
**Pattern**: `getByRole('button', { name: /regex/ })` doesn't match text

**Failing Tests**:
- "calls onOpenChange with false when close button clicked"
- "calls onAdd with correct parameters on submit"
- Form submission tests

**Quick Fix**:
```typescript
// CHANGE FROM:
screen.getByRole('button', { name: /Add.*to.*pipeline/i })

// CHANGE TO:
screen.getByRole('button', { name: 'Add transformation to pipeline' })
// OR
screen.getByRole('button', { name: /^Add.*to.*pipeline$/i })
```

**Time**: 30 min | **Difficulty**: Easy

---

### Category 5: Async/Timing Issues (8-12 tests fail)
**Pattern**: Component state not updated before assertions

**Failing Tests**:
- Tests involving dropdown opening
- Tests involving form value changes
- Tests with preview functionality

**Quick Fix**:
```typescript
// CHANGE FROM:
await waitFor(() => {
  expect(button).toHaveTextContent('updated text');
});

// CHANGE TO:
expect(await screen.findByText('updated text')).toBeInTheDocument();
// OR use waitFor with explicit timeout:
await waitFor(() => {
  expect(button).toHaveTextContent('updated text');
}, { timeout: 3000 });
```

**Time**: 45 min | **Difficulty**: Easy

---

## File-by-File Change Checklist

### Test File: `__tests__/transformation/TransformationConfigDialog.test.tsx`

#### Lines 333-345: "renders select dropdown with enum options"
```diff
- await waitFor(() => {
-   expect(screen.getByText('Mean')).toBeInTheDocument();
- });
+ expect(await screen.findByText('Mean')).toBeInTheDocument();
```

#### Lines 347-364: "selects enum value"
```diff
- const methodButton = screen.getByRole('combobox', { name: /Fill Method/i });
+ const methodButton = screen.getByTestId('method-select-trigger');

- await waitFor(() => {
-   expect(screen.getByRole('option', { name: /Median/i })).toBeInTheDocument();
- });
+ expect(await screen.findByRole('option', { name: /Median/i })).toBeInTheDocument();

- await waitFor(() => {
-   expect(methodButton).toHaveTextContent('Median');
- });
+ expect(await screen.findByText('Median')).toBeInTheDocument();
```

#### Lines 76-83: "calls onOpenChange with false when close button clicked"
```diff
- const closeButton = screen.getByRole('button', { name: /close/i });
+ const closeButton = document.querySelector('[data-slot="dialog-close-button"]') ||
+   screen.getByRole('button', { name: /close/i });
```

#### Lines 88-92: "renders text input for string type parameters"
```diff
- const fillValueInput = screen.getByLabelText(/Fill Value/i);
+ const fillValueInput = screen.getByRole('textbox', {
+   name: /Fill Value/i
+ });
```

### Component File: `components/transformation/TransformationConfigDialog.tsx`

#### Line 307: SelectTrigger element
```diff
  <SelectTrigger
    id={key}
+   data-testid={`${key}-select-trigger`}
+   role="combobox"
    aria-invalid={!!error}
    aria-describedby={error ? `${key}-error` : undefined}
  >
```

#### Lines 601-621: MultiSelect trigger button
```diff
  <button
    ref={triggerRef}
    type="button"
    onClick={() => setIsOpen(!isOpen)}
    className={...}
+   role="combobox"
    aria-haspopup="listbox"
    aria-expanded={isOpen}
    aria-controls={`${id}-listbox`}
+   aria-label={`Select ${placeholder}`}
+   data-testid={`${id}-trigger`}
  >
```

#### Lines 666-672: MultiSelect checkboxes
```diff
  <input
    type="checkbox"
    checked={value.includes(option)}
    onChange={() => handleSelect(option)}
    className="w-4 h-4 rounded border border-input"
+   aria-label={option}
  />
```

#### Lines 647-655: Select All button
```diff
  <button
    type="button"
    onClick={handleSelectAll}
    className="w-full p-2 text-sm text-left hover:bg-accent rounded transition-colors mb-1"
+   aria-label={
+     value.length === filteredOptions.length
+       ? 'Deselect All'
+       : 'Select All'
+   }
+   data-testid={`${id}-select-all`}
  >
```

---

## Test Query Mapping

| Element Type | Current Query | New Query | Priority |
|---|---|---|---|
| Select Trigger | `getByRole('combobox')` | `getByTestId('*-select-trigger')` | High |
| Enum Options | `waitFor(() => getByText())` | `findByText()` | High |
| Close Button | `getByRole('button', /close/)` | DOM query or aria-label | Medium |
| Add Button | `getByRole('button', /Add.*/)` | `getByRole('button', { name: 'Add...' })` | Medium |
| MultiSelect Trigger | Text-based | `getByTestId('*-trigger')` | Medium |
| Checkboxes | `getByRole('checkbox')` | `getByRole('checkbox', { name })` | Low |
| Form Errors | `waitFor(() => getByText())` | `findByText()` | High |

---

## Common Patterns to Replace

### Pattern A: waitFor with getBy (appears ~30 times)
```typescript
// Find all occurrences of:
await waitFor(() => {
  expect(screen.getBy[Role|Text|Label](...)).to
})

// Replace with:
expect(await screen.find[Role|Text|Label](...)).to
```

**Regex for find-and-replace**:
```
Find: await waitFor\(\s*\(\)\s*=>\s*\{[^}]*expect\(screen\.(getBy[^(]*)\((.*?)\)\)
Replace: expect(await screen.find$1($2))
```

### Pattern B: getByRole('combobox') (appears ~8 times)
```typescript
// Find all:
screen.getByRole('combobox', { name: /[^/]*/ })

// Replace with logic to check component type and use appropriate selector
```

### Pattern C: getByText with regex in waitFor (appears ~15 times)
```typescript
// Find all:
await waitFor(() => {
  expect(screen.getByText(/[^/]*/) || screen.getByText(/[^/]*/)

// Replace:
expect(
  await screen.findByText(...) || await screen.findByText(...)
).toBeInTheDocument();
```

---

## Testing Strategy Checklist

- [ ] Phase 1: Fix act() warnings (30 min)
  - [ ] Replace all waitFor + getBy patterns
  - [ ] Run tests: `npm test -- TransformationConfigDialog 2>&1 | grep -i "act"`
  - [ ] Verify no act() warnings

- [ ] Phase 2: Fix selectors (90 min)
  - [ ] Add data-testid to SelectTrigger
  - [ ] Add role="combobox" to SelectTrigger
  - [ ] Update all getByRole('combobox') queries
  - [ ] Fix button name matchers
  - [ ] Run tests: verify all pass

- [ ] Phase 3: Enhance MultiSelect (120 min)
  - [ ] Add role, aria-label, data-testid to trigger
  - [ ] Add aria-label to checkboxes
  - [ ] Improve Select All button
  - [ ] Update test selectors
  - [ ] Run tests: verify all pass

- [ ] Phase 4: Verification (30 min)
  - [ ] Full test suite pass
  - [ ] No console warnings
  - [ ] Check other test files for side effects
  - [ ] Performance check

---

## Commands for Testing

### Run TransformationConfigDialog tests
```bash
npm test -- TransformationConfigDialog
```

### Run with verbose output
```bash
npm test -- TransformationConfigDialog --verbose
```

### Watch mode (for development)
```bash
npm test -- TransformationConfigDialog --watch
```

### Check act() warnings specifically
```bash
npm test -- TransformationConfigDialog 2>&1 | grep -i "act"
```

### Coverage report
```bash
npm test -- TransformationConfigDialog --coverage
```

---

## Common Error Messages & Solutions

| Error | Cause | Solution |
|---|---|---|
| "Unable to find an element with role 'combobox'" | SelectTrigger doesn't expose role | Add `role="combobox"` to SelectTrigger |
| "Unable to find an element with the text" inside `waitFor()` | Text not rendered yet | Use `findByText()` instead of `getByText()` |
| "An update to [Component] inside a test was not wrapped in act(...)" | Async operation not awaited | Replace `waitFor(() => getBy*)` with `find*` |
| "Expected element to be in the document" with buttons | aria-label doesn't match | Use exact aria-label text in query |
| "Unable to find an element by that text" with Select | Options in portal, not in DOM | Use `findByRole('option')` not `getByRole('option')` |

---

## Performance Impact

| Change | Performance Impact | User Impact |
|---|---|---|
| Add data-testid | None (hidden attribute) | None |
| Add role="combobox" | Minimal | Positive (better a11y) |
| Add aria-label | None | Positive (screen readers) |
| Update test selectors | Slight improvement (more specific) | None |

---

## Rollback Instructions

All changes can be safely reverted:
1. Test file changes: Remove test updates, revert to original queries
2. Component changes: Remove data-testid, aria-label, role attributes
3. No functional changes to component behavior

---

## Success Metrics

After fixes, you should see:
- [ ] 68/68 tests passing
- [ ] 0 act() warnings
- [ ] 0 console errors
- [ ] Test runtime < 30 seconds
- [ ] All selectors deterministic (not text-based)
