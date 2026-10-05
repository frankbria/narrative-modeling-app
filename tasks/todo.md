# #806 — AutoML one-hot encodes per-row identifier columns (P0.39)

Plan self-authored (no plan on the issue). One fork, resolved by the owner mid-run:
numeric IDs need an ID-like name, and `feature_config.keep_columns` overrides.

## Rules
- Text/category column with nunique / rows >= 0.95 → identifier.
- Numeric column → identifier only if ID-named (`id`, `customerId`, `row_number`,
  `order_no`, `Unnamed: 0`, …), no nulls, unique, integral, and monotone in the
  original row order (`sort_index()`, since the training split shuffles).
- `keep_columns` is never excluded. All features identifiers → classified ValueError.

## Steps
1. RED: FE exclusion/keep/legacy-pickle tests; standalone parity; AC3 sample run;
   report JSON + markdown; train task persists `training_config.excluded_identifier_columns`;
   `job_failures` classification; `FeatureConfigRequest.keep_columns` mapping.
2. GREEN: `FeatureEngineer.excluded_features` (fit drops, transform drops if present,
   `getattr` default for old pickles); same in `_standalone_fe.py` + `feature_engineer_state`.
3. Report: engine `TrainingEvent`; `DatasetSection.excluded_columns`; frontend type + page.
4. Docs: CLAUDE.md training/export bullets.

## Acceptance criteria
- [ ] AC1 excluded at fit, reported (log + report); numeric monotone IDs too
- [ ] AC2 absent from feature_names, form contract, both exports; standalone parity
- [ ] AC3 customer_id added → same features and score
- [ ] AC4 pre-fix models keep serving
