# Issue #275 — Data-prep pipeline keyboard a11y (WCAG 2.1.1)

**Plan source:** self-authored (no plan comment). No architectural fork → proceeding autonomously.

## Context
`/prepare` (the DATA_PREPARATION workflow stage, `app/prepare/page.tsx`) renders only
`TransformationPipeline` — a React Flow canvas where the *only* way to add a step is
HTML5 drag-and-drop from `TransformationSidebar` (drag-only `<div>` cards). Keyboard-only /
motor-impaired users cannot add, order, or configure steps → WCAG 2.1.1 failure.
The accessible `TransformationChainView` (keyboard reorder/edit/delete already built) is not
reachable from `/prepare`.

## Approach (AC's preferred option: default to accessible Chain view; both reachable; + kbd test)
Fix at the root inside `TransformationPipeline` (owns the node state) + make the sidebar
keyboard-operable. One data model (React Flow `nodes`), two views over it.

## Steps
1. **TransformationSidebar.tsx** — keyboard add:
   - Add optional `onAdd?: (type: string) => void` prop.
   - Change each draggable card `<div>` → `<button type="button">` (keep `draggable` +
     `onDragStart` for mouse) with `onClick={() => onAdd?.(t.type)}` and `aria-label="Add <label>"`.
   - Update footer hint text to "Click or drag a transformation to add it."

2. **TransformationPipeline.tsx** — both views + keyboard path:
   - Extract `addTransformation(type)` from `onDrop` (append node; column layout so visual
     still looks fine); `onDrop` calls it (dedupe). Pass `onAdd={addTransformation}` to sidebar.
   - `viewMode` state default **`'chain'`**; accessible toggle `<button>`s (Visual | Chain,
     `aria-pressed`) in the toolbar. Both views always reachable.
   - Chain view = `TransformationChainView` fed from `nodes.map(...)` → `TransformationStep[]`.
     Wire `onReorder` (splice nodes array), `onDelete` (drop node + touching edges),
     `onEdit` → open `TransformationConfigDialog`.
   - Reuse the config-dialog wiring pattern from `app/datasets/[id]/prepare/page.tsx`:
     fetch `/transformations/available` (types+schema) and `/data/{id}/preview` (columns),
     on save update the node's `data.parameters` via `setNodes`. Degrades gracefully
     (empty schema → "No parameters needed") if the fetch fails.

3. **Test** — `__tests__/components/transformation/TransformationPipeline.a11y.test.tsx`:
   - Default view is Chain; Visual/Chain toggle present + keyboard-operable (both reachable).
   - Keyboard add: focus a sidebar "Add <label>" button, press Enter → step appears as a
     chain `listitem`.
   - Keyboard reorder: Alt+ArrowDown on a step changes order / announces.
   - Stub `global.fetch` per jest.setup contract (default rejects).

## Acceptance criteria
- [ ] Default to the accessible Chain view on `/prepare`
- [ ] Labeled keyboard "Add step" affordance (sidebar buttons)
- [ ] Both views always reachable (keyboard-operable toggle)
- [ ] Keyboard-navigation test added
- [ ] `npm test` + `type-check` + `lint` green

## Deviations / assumptions
- **FeatureBuilder out of scope:** it is not imported by any route (unreachable dead code;
  `/features` renders an AI-suggestion button list). Fixing its drag-only palettes can't be
  demoed and is pure YAGNI. Documented in PR Known Limitations.
- Chain "order" = React Flow node array order (visual node positions don't auto-reflow on
  reorder — acceptable; the chain view is the ordered source of truth for apply).
