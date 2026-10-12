# #911 — a file with an entirely empty column trains (P1.70)

Self-authored plan (the issue has five acceptance criteria). Found in review of #840.

## Decisions made here
- **An empty column is a third kind of column left out of the features**, beside
  identifiers (#806) and dates (#840): `excluded_empty` on the engineer, in
  `excluded_features` (what `transform` and the export drop), reported in the training
  log, `training_config["excluded_empty_columns"]` and the model report. Serving, the
  form and the export then agree with the fit with no new code on those paths.
- **`keep_columns` does not keep an empty column.** There is no value to encode, and
  keeping it is what crashed. An all-blank date is reported as empty, not as a date.
- **`_handle_missing_values` loses both of its recovery branches.** One dropped every
  categorical column when the imputer returned fewer columns than it was given, which is
  what turned one empty column into a `KeyError` (and would otherwise have trained a
  model with no categoricals, in silence). The other swallowed a `ValueError` and left
  the blanks in. With empty columns gone before imputation, neither can be reached.
- "Empty" is judged on the rows the engineer is fitted on (the training split), which is
  the frame the imputer sees.
- **The three `training_config` keys are written by one helper**, `_recorded_exclusions`,
  so `train_model_task` (over the CRAP ceiling, standing exemption) loses two statements
  and gains one, and a fourth kind would not touch it.

## Steps
- [x] Engineer tests: an empty numeric-read column, an empty text column, an all-blank
      date kept by the caller, other categoricals intact, all-empty frame message,
      serving and export, an older pickle.
- [x] `_empty_columns`, `_find_unlearnable`, simplified `_handle_missing_values`.
- [x] Persistence helper, model report (JSON, Markdown, page), failure wording.
- [ ] CLAUDE.md, gate, cross-family review, PR, demo through the real routes, CI, merge.
