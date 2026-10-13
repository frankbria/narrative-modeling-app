# Issue #983: the upload-time AI summary undoes processing

## Problem
`generate_dataset_summary` (the background task after every upload) reads the dataset,
waits for the model, then `save()`s its whole copy. `POST /data/process`, which the
Explore page calls meanwhile, does the same with its own copy. The later save reverts the
other's fields: `is_processed`/`schema`/`statistics`/`quality_report`, or `aiSummary`.

## Plan
- [x] RED, real documents: processing lands during the model call (both summary paths);
      the summary lands during processing.
- [x] `generate_dataset_summary` and `generate_ai_summary_safe`: `set({aiSummary})`.
- [x] `/data/process`: `set` of the five fields it computes. The handler was at cc 10 and
      is split (`_owned_upload`, `_stored_bytes`, `_processing_results`, `_store_processing`).
- [x] A guard: no `.save(` in those three modules.
- [x] The other writers of a `UserData`: `PUT /user_data/{id}` saves with no await between
      read and write and needs `validate_on_save`; `dataset_service` saves a new document;
      `/ai/summarize` is fixed in #981. Recorded in CLAUDE.md.
