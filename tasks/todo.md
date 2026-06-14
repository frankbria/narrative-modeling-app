# Issue #155 — Fix client-side crash on /datasets/{id}/prepare

> Previous plan (issue #87 — backend workflow persistence) was **completed** and merged in PR #193
> (commit ea58249); see `git log tasks/todo.md`.

## Verify-before-fix finding
Reproduced live against current `main`: the prepare page **already renders without crashing**.
The crash described in the issue was fixed by intervening PRs (notably **#166**, which corrected the
`TransformationConfigDialog` props contract). The CodeRabbit plan's "Phase 1: fix dialog props" is a
no-op today, and the dialog never rendered on initial load anyway (`editingIndex` is `null`).

Confirmed working in browser (churn.csv dataset, seeded `data_loading`+`data_profiling`):
- h1 "Prepare Data" + metadata + Visual/Chain toggles render
- both view modes render; chain view lists transformations
- edit dialog (`TransformationConfigDialog`) opens cleanly — the path CodeRabbit flagged

## Adapted plan (done)
1. [x] **Re-enable the two `test.fixme` @smoke tests** (removed `.fixme` + the
   "Disabled pending #155" comments).
2. [x] **Add a defensive guard** on the edit-dialog render block (page.tsx) so the IIFE
   only runs when `transformations[editingIndex]` exists.
3. [x] **Repair the whole data-preparation spec** — re-enabling the tests surfaced two
   classes of pre-existing breakage, both fixed:
   - **#87 gating regression**: the backend became the hydration source of truth, so a
     localStorage-only seed no longer grants access. Added a `seedPreparationWorkflow`
     helper that seeds the real backend workflow (live API, no mocking) + localStorage
     fallback, applied to all three `describe` blocks.
   - **Masked broad locators**: while the page crashed/redirected these never ran. Fixed
     `toContain('default')` → `toContain('bg-primary')` (active Button variant), scoped
     bare `h1`/`text=/rows/`/`text=/No transformations/` and `.first()`'d the
     link-wrapping-button Back controls, fixed the invalid comma `text=` OR.
4. [x] **Verified**: `chromium-smoke` @smoke (2 passed) and full `chromium-full` spec
   (16 passed); type-check clean; eslint clean; 313 transformation jest tests pass.

## Acceptance criteria
- [x] `/datasets/{id}/prepare` renders (h1 "Prepare Data", view-mode toggles) for a valid dataset
- [x] The two fixme'd smoke tests are re-enabled and pass

## Deviation from original (CodeRabbit) plan
- Original Phase 1 (fix dialog props `onSave`→`onAdd`, add missing props, metadata helper) is
  **already implemented** by #166 — dropped.
- Keeping only CodeRabbit's "Task 2" defensive guard + the test re-enable + verification.
