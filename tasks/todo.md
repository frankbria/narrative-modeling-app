# #840 — date columns are excluded from the features and reported (P1.69)

Self-authored plan (the issue gives three acceptance criteria and allows either
expanding a date into numeric parts or excluding and reporting it).

## Decisions made here
- **Exclude and report, do not expand.** A date leaves the features through the mechanism
  #806 built for identifiers: `excluded_features` on the fitted engineer, which `transform`
  and the export drop, and which `required_input_features` and the form never list. So AC2
  and AC3 hold by construction, and a model fitted before this keeps its own fitted state.
  Expanding into year / month / day-of-week needs a date parser at serving and in the
  export, a date field in the form and a decision per column about which parts mean
  anything. That is a feature, not this fix.
- **A date is recognised by shape and then by parsing.** `dateutil` alone reads "Jan",
  "Mon" and "1/2" as dates, which would remove real categoricals. A value must first look
  like a full date (year, month and day, numeric or with a month name, optional time), and
  95% of a sample must then parse. `datetime64` columns (Parquet) are dates outright:
  today they are in neither feature list and reach the estimator as they are.
- **Dates are reported apart from identifiers**: `excluded_dates` on the engineer,
  `excluded_date_columns` in the fit metadata, in `training_config` and in the model
  report, and its own line in the training log. A date that is also nearly unique is
  reported as a date.
- `feature_config.keep_columns` keeps a date in, as it keeps an identifier in.
- `AutoMLEngine.run` and `train_model_task` each gain a line (the log line and the
  `training_config` key). Both are over the CRAP ceiling under the standing exemption
  (#842) and are named in the PR.

## Steps
- [x] Detection tests: what is a date and what is not.
- [x] Engineer tests: excluded at fit, dropped at serving, export parity, keep override,
      an older pickle, all-columns-excluded message.
- [x] `_is_date_column`, `_date_columns`, exclusion and metadata; training log line.
- [x] `training_config`, model report (JSON, Markdown, page), failure wording.
- [ ] CLAUDE.md, gate, cross-family review (codex: opencode is out of quota), PR, demo, CI, merge.
