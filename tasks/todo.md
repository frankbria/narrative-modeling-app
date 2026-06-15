# Issue #153 — Frontend cleanup: CSV export + feature-selection comparison view

**Branch:** `feat/153-frontend-cleanup-csv-comparison`
**Scope:** Frontend-only. Remove two shipped TODO markers by implementing the
features they describe.

## Plan source
Adapted from the CodeRabbit auto-generated plan on the issue. Verified against the
actual code; the plan maps cleanly. Design choices kept: CSV export = transformed
data only (single file); comparison overlap matrix = simple numeric table.

## Steps

### Feature 1 — CSV export for transformation preview
1. `components/transformation/PreviewControls.tsx`
   - Add `onExport?: () => void` to `PreviewControlsProps` (mirror `onRefresh`).
   - Replace stub `handleExport`/`console.log` with `onExport?.()`; remove TODO.
   - Disable Export button when `loading` OR `onExport` is undefined.
2. `components/transformation/TransformationPreview.tsx`
   - Add `handleExport()` that builds an RFC 4180 CSV from
     `previewData.preview_result.transformed_data` (header from union of row keys),
     adapting the escape/Blob/anchor pattern from `SelectedFeatureSet.tsx`.
   - Filename `transformation-preview-{datasetId}.csv`.
   - Pass `onExport={handleExport}` to `PreviewControls` only when preview data exists.
3. Tests: extend `__tests__/components/transformation/PreviewControls.test.tsx`
   (onExport invoked, disabled when undefined/loading) and
   `TransformationPreview.test.tsx` (export wired + Blob/anchor download triggered).

### Feature 2 — Feature-selection comparison view
4. `components/FeatureSelection.tsx`
   - Add `comparisonResult: MethodComparisonResponse | null` state.
   - Rewrite `handleCompare` to store the full response (drop the
     first-result-only transform + TODO); auto-switch to the Comparison tab.
   - Leave `result` (single-method flow) untouched.
   - Add a third "Comparison" tab, disabled when `comparisonResult` is null.
5. `components/MethodComparisonView.tsx` (new)
   - Props: `MethodComparisonResponse`.
   - Side-by-side methods (name, selected features, top scores), consensus
     features, overlap matrix as a numeric table, recommendations text, CSV export.
6. Tests: new `__tests__/components/MethodComparisonView.test.tsx` and
   `__tests__/components/FeatureSelection.test.tsx` (3-tab structure, state, switch,
   service mocked).

## Notes / decisions
- This repo uses `lucide-react` throughout; matching it for consistency (the global
  "never lucide-react" rule targets *new* Nova-template projects, not this app).
- No backend changes — `MethodComparisonResponse` already carries all needed data.

## Acceptance criteria (verified in demo)
- [ ] CSV export downloads the current transformation preview as CSV
- [ ] Feature-selection comparison view shows methods side-by-side (selected
      features + importance scores)
- [ ] TODO comments removed (both files)
- [ ] Component tests for both
- [ ] `npm test` green, `npm run type-check` clean, eslint clean
