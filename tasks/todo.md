# Issue #616 — [P3.28] [security] erasure _s3_key ignores its bucket_name — a URL naming another bucket has its key deleted from ours

Plan source: self-authored (DoD in the issue). Approved autonomously — the behaviour decision the issue defers (skip + record vs. delete anyway) is answered by its own DoD: skip, record a manifest failure, never delete in the wrong bucket. No fork.

## Findings
- `_s3_key(url_or_key, bucket_name)` parses the URL through `parse_s3_url` and discards the bucket it names; `_delete_s3` then deletes `key` from `self.s3_service.bucket_name`. A stored URL naming another bucket would delete whatever holds that key in ours.
- Both call sites (DatasetMetadata and UserData parents) already hold the `DeletionManifest`.

## Design
1. `_s3_key(url_or_key, bucket_name, manifest=None)`: when the URL names a bucket and it differs from `bucket_name`, append a failure naming both buckets to the manifest and return `None`; a URL naming no bucket (plain https) falls back to the configured one as before; bare keys pass through.
2. Call sites pass the manifest. Docstring loses "kept for the call sites".
3. Tests: matching bucket → key; foreign `s3://` and endpoint-style → `None` + one failure mentioning both buckets; no manifest → still `None`, no crash.

## Steps
- [ ] RED tests
- [ ] _s3_key + call sites
- [ ] gate → PR → demo → CI → merge
