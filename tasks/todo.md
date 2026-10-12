# #841 — the training page shows what was left out and can retrain keeping it (P2.53)

Self-authored plan. Also closes #919 (P0.46), found by this issue's own demo.

## Decisions made here
- The issue names `components/ModelTrainingButton.tsx`, which no page renders. The live
  form is `app/model/page.tsx`, so the work is there and the dead component is deleted.
- The panel reads the model report (`excluded_identifier_columns`, `excluded_date_columns`,
  `excluded_empty_columns`), so it appears after a run. Identifiers and dates can be kept;
  an empty column has nothing to learn from and is listed without a checkbox.
- "Retrain keeping N columns" reruns the same target and mode with
  `feature_config.keep_columns` = everything kept so far plus the ticked ones.
- The page was one component at CRAP 41. It is now a shell over `useTrainingRun`,
  `useTrainingOptions`, `TrainingSetup`, `TrainingRunView` and `ExcludedColumnsPanel`.
- #919: the target list read `GET /datasets/{id}` → `data_schema`, which is a 404 for an
  upload's id and always `[]` for a `/datasets` upload. It now reads the upload's own
  record first (`columns`, else `data_schema[].field_name`), then `/datasets/{id}`.

## Steps
- [x] Split the page; jest for the moved branches.
- [x] Panel + retrain; jest incl. the request body and the union on a second retrain.
- [x] #919: failing jest per id-space, the loader fix, a real-stack `@smoke` spec that
      picks a target from the list and starts a run through the form.
- [x] Real-stack demo: panel, tick, retrain, `keep_columns` on the wire.
- [ ] Gate, cross-family review, PR, CI, merge.
