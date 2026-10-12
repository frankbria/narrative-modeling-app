# #851 — every move of a dataset is either a history step or closes the history (P2.54)

Self-authored plan.

## What was wrong
- `POST /transformations/pipeline/apply` moved the dataset with no history step and no
  version. So did the two routes that run through it in-process: auto-clean and recipe
  apply. Undo afterwards restored an earlier step's version and the edit was gone.
- Four more writers move the dataset through `record_new_file` with no step: bulk
  transformations, the two data-issue fix routes, and a feature column added in place.
- Found on the way: a history step refused `fill_missing` with no column named, though
  the engine runs it. `POST /transformations/apply` with that request failed *after*
  writing its file and version.

## Decisions made here
- **Engine transformations record steps.** `TransformationService.apply_pipeline` runs
  every step on the frame first (all or nothing, as before), then records each as its
  own step and version, exactly as a single apply does. `apply_transformation` is now a
  one-step pipeline. The pipeline route, auto-clean and recipe apply all go through it.
- **Two passes, not a kept list.** The dry run discards its frames and the steps run
  again while being recorded: twice the CPU for a multi-step pipeline, never more than
  two frames in memory. A single apply skips the dry run.
- **Everything else closes the history.** `record_new_file` takes `in_history` (default
  False). A move that is not the history's own sets `undo_floor` to just past the current
  step and drops the redo tail, so undo and jump refuse to go back past the edit. The
  default is the safe side: a new writer that says nothing cannot be undone past.
  The other four writers are unchanged; they get this through the default.
- The pipeline route takes either id space now (it resolves through
  `ensure_metadata_twin`), so an id that names nothing is a 404, not a 400.

## Steps
- [x] Undo floor: model, `record_new_file`, undo / jump / listing; tests on real documents.
- [x] `apply_pipeline` + `_record_step`; route rewritten over it; the six mocked route
      tests replaced with real-document ones that read the history back.
- [x] `fill_missing` with no column is a recordable step.
- [x] LocalStack: apply → pipeline → undo twice; undo refused after an outside move.
- [ ] Gate, cross-family review, PR, demo, CI, merge.
