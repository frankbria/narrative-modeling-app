# #838 — predictions flag unseen or missing inputs, and a JSON null is imputed (P1.68)

Self-authored plan. #906 (one-hot key matching) was found while probing this and merged
first, so "unseen" now means the same thing under both encodings.

## Decisions made here
- **A new field, not a forced `low_confidence`.** `input_warnings` is one object per
  record, `{column: "unseen" | "missing"}`, empty for a clean record. Regression has no
  `low_confidence` list at all, and a flag that only says "low" loses which column and why.
  The issue allows either.
- **`FeatureEngineer.input_warnings(X)` is a separate read of the raw frame**, not a
  second return value of `transform`. `transform` keeps its signature (the engine and the
  export call it), and the cached engineer is shared across requests, so stashing a report
  on it would cross requests.
- **"missing" covers numeric inputs too.** A null numeric is filled with the training
  mean exactly as a null categorical is filled with the mode. Flagging one and not the
  other would repeat the complaint in the issue: the flag would depend on the column's
  type and not on the input.
- **`_prepare` is what both `transform` and `input_warnings` read**: booleans coerced,
  identifier columns dropped, and `None` turned into NaN in the categorical columns, which
  is the null fix. Mirrored in `StandaloneFeatureEngineer`; the export does not report
  warnings (not asked for).
- **Routes are split, because both are over the CRAP ceiling** (`predict` cc 14,
  `production_predict` cc 18). The shared pieces move to `require_input_features` and
  `infer_records`; each route keeps its own error wording.
- **Batch attaches the warnings in `_predict_chunk`** (cc 2), after either inference path,
  so the two chunk functions (cc 15 and 17) are not touched. The CSV gets an
  `input_warnings` column (JSON, blank for a clean row), always in the header so it stays
  deterministic. `_csv_header` (9) and `_results_to_dataframe` (10) are split.
- **The batch summary counts flagged rows (`input_warning_count`) and the batch UI points
  at the CSV column.** First planned as a follow-up, to avoid splitting `add` (cc 12) and
  `result` (cc 10). Reversed: the single-prediction form offers only dropdown values and
  requires every field, so a batch file is the one place a UI user meets an unseen or
  blank input, and without the line the flag would sit unread in a downloaded file.
- **Frontend: the whole prediction page is split.** The plan was to move only the
  single-prediction arm. The gate attributes any JSX line in the page to `PredictPage`
  (cc 41), so the page is now a shell over `components/predict/`: `predictionForm.ts`
  (form, context and single-prediction hooks), `useBatchPrediction.ts`,
  `SinglePredictionPanel`, `BatchPredictionPanel`, `PredictionResult` (with the new
  `InputWarnings`) and `PredictChrome`. Seven tests cover batch paths the old page never
  tested (failed job, lost connection, start failure, download).

## Steps
- [x] Engineer tests: a null is imputed like a blank (both encodings, export parity);
      warnings name unseen and missing columns; a form string for a numeric category is clean.
- [x] `_prepare`, `input_warnings` in `FeatureEngineer`; `_prepare` in the export.
- [x] Route tests, then `require_input_features` / `infer_records` and the two routes.
- [x] Batch tests, then `_predict_chunk`, CSV header and rows.
- [x] Frontend type, component tests, extraction, `InputWarnings`.
- [x] Batch summary count and its line in the batch UI.
- [x] Predict page split under the CRAP ceiling.
- [ ] CLAUDE.md, gate, cross-family review, PR, demo through the real routes and UI, CI, merge.
