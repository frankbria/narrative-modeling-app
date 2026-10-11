# #801 — capture at training time what the model report has to call "not recorded" (P1.64)

Self-authored plan (the issue lists four items and four acceptance criteria).

## Decisions made here
- **Seed and winner hyperparameters go in `MLModel.training_config`**
  (`random_seed`, `winner_hyperparameters`), the channel #806 already uses for
  `excluded_identifier_columns`. No new `MLModel` field, so `save_model` (cc 11) is not
  touched and the `sample_ml_model` fixture needs no change (AC4 does not arise).
- **The dataset version is matched by content.** `_link_trained_version` finds the twin
  by `(user_id, s3_url)` at training time and the `DatasetVersion` whose `content_hash`
  equals the hash of the bytes training read. The issue's other option, "the latest
  version of the dataset", can name a version of different bytes after an undo or a
  transformation that wrote no version. A dataset with no version of those bytes records
  none, and the report keeps its caveat. It is passed to `save_model` explicitly, which
  already prefers an explicit id over its own (broken) lookup.
- **`save_model`'s "latest version" fallback is removed** (cross-family review). Since #850
  keys a UI upload's twin by the upload's own id, that fallback can match, and it would
  name the dataset's latest version whenever training found no version of the bytes it
  read. `save_model` was cc 11, so its two best-effort JSON uploads move to
  `_upload_json_artifact`.
- The matched version gets the model id in `used_in_training` (`$addToSet`), which the
  issue notes nothing ever wrote.
- **Item 3, the preprocessing applied, is closed without capture, for a recorded
  reason:** `pipeline/apply`, bulk transformations and data-issue fixes move a dataset
  without writing a history step (#851), so a list read from the history would be
  incomplete and stated as fact. The module docstring says so, and #851 gets a comment.
- **Per-figure provenance:** `seed_provenance` and `hyperparameters_provenance` beside
  the two new figures, because their sections already carry real stored numbers.
- **The frontend page is split.** `ModelReportPage` was cc 24, and the seed sentence
  lived in it, so editing it meant splitting it: one component per section in
  `components/model-report/ReportSections.tsx`, plus `useModelReport`, `ReportStatus`,
  `ReportHeader`, `saveMarkdown` and `useModelId` in the page.

## Acceptance criteria (from the issue)
- [x] AC1: each of the four items is captured, or closed with a recorded reason
      (seed, dataset version and hyperparameters captured; preprocessing closed, #851).
- [x] AC2: the report stops disclaiming what is captured, its provenance is STORED, and a
      test asserts the real value reaches the report.
- [x] AC3: nothing new is required: a model trained before this validates and the report
      says `not_recorded` for it.
- [x] AC4: no `MLModel` field was added, so the `sample_ml_model` fixture is unchanged.
