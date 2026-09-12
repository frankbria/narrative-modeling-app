# Issue #585 — [P3.18] [security] Upload routes store the client filename verbatim

Plan source: self-authored. Approved autonomously — AC2 asks for a deliberate reject-vs-normalise decision: normalise (Excel/CSV exporters produce odd names; rejection has a real false-positive cost, and a stored-alongside raw copy keeps the trap). No fork.

## Findings
- Writers of `filename`/`original_filename` from client input: `secure_upload.py` (`/secure`, `/confirm-pii-upload`, `/chunked/{id}/complete` via the session's filename), `upload.py:179`, `datasets.py:214` → `UserData` and `DatasetMetadata`. `dataset_s3_key` uses only the extension (#464), so the key is already safe.
- No consumer builds a header or a path from the fields yet; `data_processing.py` echoes `original_filename` in JSON.

## Design
1. `app/utils/filenames.py::sanitize_filename(name, max_length=255)`: basename after `/` and `\`, control characters (incl. CR/LF, NUL) removed, leading dots/whitespace stripped, empty → `upload`, length capped preserving the extension.
2. Enforce at the point every writer meets: `field_validator` on `UserData.filename/original_filename` and `DatasetMetadata.filename/original_filename` — one place covers the three routes named, the two others, and any future writer. The stored name *is* the sanitised one (no raw copy).
3. Tests: unit table for the sanitiser; model round-trip (`../../etc/passwd.csv`, `a\r\nb.csv`, 300-char name) for both documents; chunked complete end-to-end stores the sanitised name.

## Steps
- [x] RED tests
- [x] sanitiser + validators (+ validate_on_save, SafeFilename type, /datasets/upload key component after review)
- [x] gate → PR #647 → demo → CI → merge; follow-up #648 (model_export Content-Disposition)
