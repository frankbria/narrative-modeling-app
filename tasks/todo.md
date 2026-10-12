# #856 — the bulk routes take a UI upload's id (P2.55)

Self-authored plan.

## Decisions made here
- One resolver for the service, `_owned_dataset(user_id, dataset_id)`, over
  `dataset_link.ensure_metadata_twin`. Select, preview and apply use it; the job
  processor calls `ensure_metadata_twin` itself, since a missing dataset there fails the
  job instead of raising.
- `apply_bulk_transformation` resolves the dataset before creating the job (it did the
  lookup before too). That is where a TSV or JSON upload is refused by type (#857): the
  transformation reader would parse it as junk and the job would overwrite the live file.
- The three functions the issue names are split under the CRAP ceiling:
  `preview_bulk_transformation` -> `_preview_column`, `_preview_summary`, `_failed_preview`;
  `apply_bulk_transformation` -> `_require_valid_request`, `_require_job_slot`;
  `_process_bulk_job` -> `_run_columns`, `_still_wanted`, `_record_progress`,
  `_finish_job`, `_move_dataset`, with `_ColumnRun` holding the running frame and outcomes.
  Behaviour is unchanged, including that an "Invalid columns" refusal in preview is
  reported as the generic sanitised failure.
- Not changed: `_apply_column_transformation`, the job-status routes.

## Steps
- [x] Failing tests on real documents: preview over the route, select, a job that runs
      and moves the upload, another account's upload, a TSV upload.
- [x] Tests for the job endings nothing reached: partial failure, stop_on_error, cancelled
      or deleted mid-run, dataset gone.
- [x] The resolver and the three splits.
- [ ] Gate, cross-family review, PR, demo, CI, merge.
