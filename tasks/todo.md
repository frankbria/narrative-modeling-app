# Issue #185 — WorkflowBar overflow + scrolling Progress counter

**Branch**: `fix/185-workflowbar-overflow` | **File**: `apps/frontend/components/WorkflowBar.tsx`
**Plan source**: CodeRabbit comment on issue, adapted (one significant deviation — see below)

## Adapted Plan

1. **[TDD] Write Jest tests first** — `apps/frontend/__tests__/components/WorkflowBar.test.tsx` (new)
   - Mock `useWorkflow` (pattern: existing component tests); render with various completed/current states
   - Assert: progress indicator is NOT a descendant of the `overflow-x-auto` element
   - Assert: exactly one scroll container exists and it wraps only the stage strip
   - Assert: no connector carries `w-8`/`sm:w-12` (slim connectors)
   - Assert: full stage name renders only for the current stage; other stages render icon + number, with `title` attr for hover
   - Assert: disabled stages have `disabled`; clicking accessible stage calls `setCurrentStage`; clicking disabled does not
2. **Restructure scroll hierarchy** (Task 1.1 as planned)
   - `<nav>` → `flex items-center justify-between` without `overflow-x-auto`
   - New inner wrapper `overflow-x-auto scrollbar-hide flex-1 min-w-0` around the stage strip
   - Progress indicator becomes `shrink-0` sibling outside the scroll wrapper
3. **Slim connectors** (Task 1.2 as planned)
   - Line `w-8 sm:w-12` → `w-2 sm:w-3`; keep chevron, `-ml-1`, color logic, `scaleX` animation
4. **Stage names: current-stage-only** (Task 1.3 — DEVIATION, see below)
   - Current stage button: icon + full name; all other stages: icon + number
   - Add `title={stage.name}` on every button (hover/AT discoverability)
   - Remove the `sm:`-based name/number swap on buttons (mobile indicator at the bottom is untouched)
5. **Define `scrollbar-hide` utility** in `app/globals.css` — it's referenced in the component today but defined nowhere (no-op). The new scroll wrapper relies on it.
6. **Verify behavior unchanged** (Task 1.4) — covered by tests in step 1 + demo at 1280/1536/narrow widths

## Deviation from the CodeRabbit plan (step 4)

The plan said raise name visibility from `sm:` to `lg:`/`xl:`. **The math doesn't work**: the bar
lives in a `max-w-7xl` (1280px) container, so content width is ~1216px at every viewport ≥1280.
Eight full names ≈ 870px of text + 8 buttons' padding/icons ≈ 480px + 7 connectors + progress
≈ 1700px+ total — full names can never fit, so `lg:inline`/`xl:inline` would still fail the
"no horizontal scroll at 1280–1536" criterion. Showing the full name only on the current stage
(standard stepper pattern) fits comfortably (~950px) and keeps stages identifiable via icon,
number, and title tooltip.

## Acceptance criteria (from issue)

- [ ] At 1280–1536 px the bar fits without horizontal scrolling
- [ ] "Progress: n / 8" never scrolls; stays pinned right
- [ ] When viewport is genuinely too narrow, only the stage strip scrolls
- [ ] Stage click-through/disabled behavior unchanged

## Test strategy

- Jest/RTL structural tests (step 1) → criteria 2 (DOM hierarchy), 4 (handlers/disabled)
- Demo via agent-browser at 1280, 1536, and ~800px widths with `scrollWidth <= clientWidth`
  measurements → criteria 1, 3
