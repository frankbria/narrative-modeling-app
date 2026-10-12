# #906 — one-hot serving matches a value on its label key (P0.45)

Self-authored plan. Found while probing #838, whose "unseen" flag would otherwise fire
on values the form itself offered.

## Decisions made here
- **`_one_hot` builds the block from `_label_keys`** in `FeatureEngineer` and, identically,
  in `StandaloneFeatureEngineer`. The fitted `OneHotEncoder` is still what fit uses and what
  supplies `categories_` and `encoded_columns`; only its `transform` is no longer called at
  serving. Mapping each sent value back to the fitted type and then calling the encoder was
  the other option: it leaves a mixed-type column for the encoder to sort.
- **Linear in rows:** a key-to-position dict per column, not a rows x categories comparison
  of object arrays (50k rows, 201 one-hot features: 0.12 s).
- **`_categorical_options` returns the keys** (`"1"`, not `"1.0"`, for a float category), so
  every option the form offers is one serving matches. It was cc 9, so the lookup moves to
  `_fitted_category_keys`.
- **`_match_keys`, from the cross-family review:** the label key alone made a blank and the
  text `"nan"` one key (two categories when no imputer was fitted, so serving lit a different
  column than fit), and dropped the fitted encoder's occasional reading of `"1.0"` as `1`.
  A missing value now carries a flag beside its key, and a column fitted on numbers reads
  numeric text as the number.
- Fit is not changed. A boolean column with blanks is still fitted with bool categories;
  serving now matches `"True"` and `true` to them either way.

## Steps
- [x] Failing tests: a value selects its category whatever type it is sent as (platform and
      export), every offered option is matched, a null in one record leaves the others alone,
      training rows encode exactly as fit did, the predict route serves the form's string.
- [x] `_one_hot` in both engineers; `_categorical_options` through the keys.
- [x] CLAUDE.md convention.
- [ ] Gate, cross-family review, PR, demo through the real routes, CI, merge.
