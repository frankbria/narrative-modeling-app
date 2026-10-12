# Issue #960: charts keep showing the data from before a transformation

## Problem
The histogram (default bins), box plot and correlation matrix are cached per dataset in
Redis (`viz:{id}:…`) and in the `VisualizationCache` collection, which never expires.
Nothing clears either when the dataset moves to a new file, so after a transformation,
an undo or a data-issue fix the charts answer with the old data for good.

## Plan
- [ ] RED: `tests/test_services/test_moved_dataset_forgets_what_was_computed.py`: a move
      through `record_new_file` drops this dataset's chart rows and Redis keys, and its
      column statistics; another dataset's stay; a failure to clear does not fail the move.
- [ ] `dataset_link.record_new_file` clears them after the move. It is the one place
      every writer that moves a dataset goes through (apply, pipeline, bulk, data-issue
      fixes, undo, redo, jump).
- [ ] LocalStack test through the routes: a box plot before and after a transformation.
- [ ] Column statistics (`ColumnStats`): cleared by the same hook; noted on #889.
