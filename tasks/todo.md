# Issue #648: a model's name reaches the export download header unescaped

## Problem
Eight routes in `model_export.py` (four GET, four through `POST …/export/{format}`) build
`Content-Disposition: attachment; filename={filename}` from the model's name. Quotes and
CR/LF pass through, and a name outside latin-1 cannot be encoded as a header at all, so
that model cannot be exported (the encode error is a `ValueError`, answered 400).
`batch_prediction.py` builds the same header from the job's `output_format`.

## Plan
- [x] RED: a hostile name on every export route; a Cyrillic name; the builder itself.
- [x] `attachment_disposition(name)` in `app/utils/filenames.py`: normalise, then both
      RFC 6266 forms. The report route already did this inline; it moves there.
- [x] `model_export.py`: `_download` for the header, `_export` for the format dispatch
      (`export_model_custom` was at cc 11).
- [x] `batch_prediction.download_results` uses it too (cc 6: the media-type chain becomes
      a lookup).
- [x] A guard: no `attachment; filename` literal in `app/` outside the builder. It found a
      fourth site on its first run: the presigned export URL's `ResponseContentDisposition`
      in `s3_service.py` (already escaped, by its own rule). It uses the builder now.
- [x] `MLModel.name` is not given a filename validator: it is a display name ("v2 / churn",
      a trailing dot, any script), and changing what users typed to make one header safe
      is the wrong end to fix.
