# Issue #937: a PII-confirmed upload is stored with no file_type

## Problem
`POST /upload/confirm-pii-upload` builds its `UserData` without `file_type`, so training
(`_parse_dataset(bytes, None)`) raises. With masking, the masked copy is CSV bytes under a
key that keeps the upload's extension, so by-name helpers call a masked workbook Excel.

## Plan
- [ ] RED: `tests/test_api/test_pii_confirmed_upload_type.py`: CSV and workbook through the
      route, masked and not; the stored type, the key's extension, and the written bytes
      read by training's parser and by the explore page's processor.
- [ ] Handler: store `csv` for a masked copy (key ends `.csv`), the upload's extension
      otherwise. Split it (`_read_confirmed`, `_store_confirmed`) to end under CRAP 6.
- [ ] Rows already stored with no type: `_parse_dataset` reads by content through
      `s3_service._read_dataframe` when no type is declared.
- [ ] `dataset_link._file_type_of`: a `masked_` object is CSV whatever its name says, so the
      audit script and twin creation do not type a legacy masked workbook as xlsx.
- [ ] CLAUDE.md, gate, review, demo (main against branch), PR.

## Out of scope
- Backfilling legacy untyped rows (they train by content; the audit script now names them csv/by extension).
- `/secure`'s and chunked `complete`'s own type detection.
