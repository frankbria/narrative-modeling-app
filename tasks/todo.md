# Issue #170 — InteractiveVisualizationDashboard renders sample data instead of real values

**Type:** bug, P1-High, frontend, phase-4
**File (primary):** `apps/frontend/components/InteractiveVisualizationDashboard.tsx`
**Plan source:** CodeRabbit comment (adapted)

## Problem
The dashboard generates chart payloads with `Math.random()` (`sampleChartData` memo ~lines 62–116 for scatter/line/histogram) and a static `sampleBoxPlotData` constant (~188–195). Only the correlation tab uses real backend data. This shows fabricated analytics to users.

## Acceptance Criteria
- [ ] No `Math.random()`/static placeholder data rendered as analytics in the visualizations tab
- [ ] Charts reflect the selected dataset's actual values, or show an explicit empty/unsupported state

## Adapted Plan (TDD)

### Step 1 — Histogram via HistogramChart fetch mode
- Render `<HistogramChart datasetId={datasetId} column={firstSelectedNumericColumn} />` instead of sample `data`. It handles its own loading/error/empty.

### Step 2 — Boxplot, Scatter, Line via real services + local fetch state
- Per-chart local state (`data`/`loading`/`error`) + a `useEffect` fetching when the chart is active and required columns are selected:
  - boxplot → `getBoxPlot(datasetId, column, token)`
  - scatter → `getScatterPlot(datasetId, xCol, yCol, filters, token)` (first 2 numeric cols)
  - line → `getLineChart(datasetId, xCol, yCols, filters, token)` (first col x, rest y)
- Use `getAuthToken()` (HistogramChart pattern). Guard against stale responses (cancel flag in effect cleanup).
- **Deviation from CodeRabbit plan:** uniform local-state fetch for boxplot too (not the `useVisualizations` hook) so all three direct-service charts follow one consistent pattern, instead of mixing an otherwise-unused hook in for a single chart type.

### Step 3 — Empty / unsupported state guards
- In `renderChart()`, guard each case: prompt to select columns when none; unsupported message when selected columns aren't numeric; empty state when fetch returns no data.

### Step 4 — Real-data export
- `handleExportChart` serializes the active chart's fetched data (boxplot/scatter/line local state, histogram fetched data, correlation = `statistics.correlation_matrix`); friendly message when nothing to export.

### Step 5 — Remove all sample-data code
- Delete `sampleChartData` memo and `sampleBoxPlotData` constant; remove now-unused imports/vars; replace simulated `handleRefreshChart` setTimeout with a real refetch trigger.

### Step 6 — Tests
- `__tests__/components/InteractiveVisualizationDashboard.test.tsx`: mock visualization services; assert real fetches drive each chart; assert no random data; assert empty/unsupported states; assert export uses real data.
- Run `npm test`, `npm run type-check`, eslint.

## Notes / risks
- `getAuthToken()` is a placeholder token format (app-wide, out of scope).
- Dashboard `Column.type` vocabulary is `'numeric'|'categorical'|'datetime'|'text'` (distinct from `NUMERIC_DATA_TYPES` in api.ts). Gate numeric charts on `type === 'numeric'`.
