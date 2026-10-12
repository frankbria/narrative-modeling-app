# Issue #962: the first transformation on a dataset cannot be undone

## Problem
The history has no position for "the dataset before any step". `current_position` is 0
after the first step and undo moves to `position - 1`, which must be a step. So undo
works from the second step back to the first and never further.

## Design
Position -1 becomes reachable when, and only when, the version the dataset was at before
its first step is known for certain:

- `TransformationConfig.base_version_id`: set when the first step of a history is
  recorded, to that step's parent version, if the dataset had never moved before
  (`source_s3_url` unset). Then the parent is the upload itself. If the dataset had
  already been moved by an edit the history holds no step for, the latest version is not
  the file being transformed, and nothing is recorded: the first step stays not undoable.
- `can_reach(-1)`: the base is known and no outside edit has closed the history.
- `_close_history` at position -1 (an outside edit after undoing to the start) forgets
  the base and drops every step: none of them describes the edited file.
- Undo to -1 restores the base version through the same `_move_to_step` as any other
  undo; redo from -1 is the existing code.

## Plan
- [ ] RED: model tests, a `_close_history` test, and a LocalStack test through the
      routes (upload, one step, undo, redo, watching the box plot's median).
- [ ] Model, service, `dataset_link`, the apply path.
- [ ] Existing tests that pin "position 0 cannot be undone".
