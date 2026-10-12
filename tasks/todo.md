# #862 — the Prepare pipeline runs its steps in the order drawn (P2.59)

Self-authored plan.

## The model (AC3)
One order, `planOrder(nodes, edges)` in `components/transformation/runOrder.ts`:
- arrows drawn on the canvas, when there are any: they must make one chain through every
  step, and that chain is the order;
- no arrows: the order the steps are listed in.

Everything that sends or shows steps reads it: Preview, Apply, recipe save, Export Code,
the Chain view's list, and the steps dropped after a part-way apply.

## Decisions made here
- **Refuse, do not guess.** A fork, a merge, a loop or a step left unconnected has no
  single order. Preview and Apply show the reason and send nothing.
- **The Chain view edits the run order.** A reorder or delete there is made on the run
  order, becomes the listed order, and redraws the arrows if any were drawn.
- **A step added while arrows exist joins the end of the chain.** Otherwise a user who
  loaded a recipe (which draws arrows) and added a step from the Chain view would be told
  it is "not connected" on a canvas they never opened.
- An arrow whose step is gone is ignored.

## Steps
- [x] `runOrder` / `planOrder` with unit tests for each shape.
- [x] Component tests with the canvas replaced by one button per possible arrow.
- [x] Wire the component: `plan`, `pipelineSteps`, the chain handlers, add, drop-applied.
- [ ] Gate, cross-family review, PR, demo, CI, merge.
