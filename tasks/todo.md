# #902 — an Excel dataset's file_type is its extension, from every writer (P2.63)

Self-authored plan.

## Decisions made here
- **The stored value is the extension** (`xls` / `xlsx`), as the issue suggests:
  `record_new_file` and the audit script already go by it.
- **Set at the model, not in each route.** `UserData` and `DatasetMetadata` run one
  `model_validator(mode="before")` that turns `"excel"` into the extension (filename
  first, then the object's URL; `xlsx` when nothing says). Every writer builds one of
  these documents, so every route is covered, and so is the next one. The three upload
  handlers that say `"excel"` are not edited (they are well over the complexity ceiling).
- **Rows already stored are covered on read.** Validators run when a document is loaded,
  so a row holding `"excel"` reads back under its extension. That is the "every reader
  accepts it" half of the issue without touching a reader: the feature store, which
  raised on `"excel"`, now receives `xlsx`.
- **The audit reads raw documents.** The model would show it the corrected value and
  hide the very rows it is meant to find. Its fix is a targeted `$set`.
- Found on the way, filed as #937 (P0): `/upload/confirm-pii-upload` stores no
  `file_type`, so those datasets cannot be trained.

## Steps
- [x] Failing tests: both models; a stored `"excel"` row read back; the raw stored value
      after an insert; each reader on such a row with a real workbook; the audit.
- [x] The validator, the audit script on raw documents.
- [x] A route test: `/upload/secure` with a workbook stores `xlsx`.
- [ ] Gate, cross-family review, PR, demo, CI, merge.
