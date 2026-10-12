# Issue #720: the preview presents an approximate row total as exact

## Problem
For a file too large to parse whole (>25 MB), `GET /data/{id}/preview` counts lines
rather than rows and says so: `approximate_total_rows: true` and a `warning`. The count
can be a little high (a quoted newline is counted twice), never low. `DataPreviewTable`
reads neither field, so it prints "of 1203441 rows" and "Page 1 of 24069" as facts.

## Plan
- [ ] RED: tests in `__tests__/components/DataPreviewTable.test.tsx`: with the flag the
      total and the page count read "about N"; the warning is shown; without the flag
      nothing changes.
- [ ] `DataPreviewTable`: read both fields. The component is at cyclomatic complexity 9,
      so the edit is also a split (`unavailable`, `PreviewHeader`, `PreviewPager`).
- [ ] The other `/preview` callers (`prepare/page.tsx`, `ColumnSelector`, `pipelineApi`)
      read only column names, so they have no total to qualify (checked).
