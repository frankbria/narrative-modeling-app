# #888 — version objects hold parquet under the upload's `.csv` name (P1.59)

Self-authored plan (the issue has a definition of done, no plan).

## Decisions made here
- **A new version object is named for what it holds.** `create_transformation_version`
  keys parquet content as `…/versions/{version_id}/data.parquet`. The name is decided
  from the bytes, not assumed: `POST /datasets/{id}/versions` hands the same function a
  copy of the latest version, which can be the CSV upload. That content keeps the
  dataset's filename, as today.
- **For a version object whose name does not say parquet, the bytes decide.** This is the
  pre-#888 population. `record_new_file` is the one place that stamps `file_type` from a
  location, so the check lives there (one download, only for such a URL; every forward
  writer hands it a `.parquet` URL and pays nothing). Undo, redo and jump all go through
  it, so `history_service` does not change.
- **The audit script uses the same rule**, so it repairs a dataset already sitting on a
  mis-named version instead of confirming `csv`. A download it cannot make is
  `undetermined` and the row is left alone.
- No re-keying of existing objects: the row's `file_type` is made true, the name stays.
  `column_stats` dispatched on the name alone, so its loader now takes the parquet
  branch on the bytes it already holds (cross-family review).
- `create_transformation_version` was cc 12 and the naming line is inside it, so the
  CRAP gate required splitting it (`_duplicate_of`, `_upload_version`, `_schema_hash`,
  `_insert_version`).

## Acceptance criteria (the issue's definition of done)
- [x] AC1: a test reproduces it first (CSV upload, two steps, undo, read the way a
      training-stage reader does) and fails on main.
- [x] AC2: a new version object's key extension matches its content.
- [x] AC3: a dataset restored to, or already sitting on, a mis-named version still loads:
      the restore stamps `parquet`, and the audit script corrects an existing row.
- [x] AC4: undo, then train, works on a CSV upload, against real bytes in LocalStack.
- [x] AC5: column stats on a restored (new-style) version return every column.

## Steps
1. Tests first, in `tests/test_integration/test_transformation_history_localstack.py`:
   undo then read (AC1, AC2, AC4, AC5); a version re-keyed to the old shape, then undo
   (AC3); the audit script on a row a pre-#888 undo left as `csv` (AC3).
2. `app/utils/s3.py::holds_parquet(content)`: PAR1 at both ends, the #524 rule.
3. `versioning_service.create_transformation_version`: name by content.
4. `dataset_link.file_type_at(url)` used by `record_new_file` and the audit script.
5. Unit tests for the non-integration gate: key naming, the bytes-decide branch with the
   downloader stubbed, the script's undetermined case.
6. CLAUDE.md: the `file_type` paragraph.
