# #858 — the transformation reader reads JSON and Excel datasets as what they are (P2.56)

Self-authored plan.

## Decisions made here
- **By the bytes, at the one reader.** The issue asks for dispatch on the stored
  `file_type`. 14 call sites reach the reader through `get_dataframe_from_s3` with no
  type, most inside large legacy functions, and a stored type that lags the bytes would
  turn a working transformation into a `FormatMismatchError`. The untyped path now reads
  what the file is: Parquet by its magic (head and footer), `.xlsx` by the zip header,
  `.xls` by the OLE header, JSON by a leading `[` or `{`, otherwise CSV. No call site
  changes, and the next caller is covered too.
- A file that opens with a bracket but is not JSON falls back to CSV (a header like
  `[id],name`). Malformed JSON cannot be in storage: both upload routes parse the file
  before storing it.
- `"excel"` is a declared type the typed path reads. `/upload/secure` stores it for a
  workbook, and the typed readers answered "Unsupported file type: excel".
- `_TRANSFORMABLE` widens to JSON and Excel (AC3). TSV stays refused: it reads as one
  column, and neither upload route accepts it as such anyway.
- `_read_dataframe` was one function at cc 14; it is now `_kind_of`, four one-line
  readers, `_require_matching_bytes` (#524, unchanged) and `_read_by_content`.

## Steps
- [x] Reader tests: JSON (records, columns, BOM), xlsx, xls header, CSV with a bracket
      header, row limit for every kind, `"excel"` declared.
- [x] The reader; `_TRANSFORMABLE`; twin tests.
- [x] LocalStack: a JSON `/datasets/upload` and an Excel `/upload/secure` transformed,
      then read back the way training reads.
- [ ] Gate, cross-family review, PR, demo, CI, merge.
