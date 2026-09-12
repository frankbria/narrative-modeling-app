# Issue #622 — [P3.31] [security] Finish the one-bucket contract

Plan source: self-authored (DoD in the issue). Approved autonomously — no architectural fork: the contract (#621's `configured_bucket()` / `validate_object_key()`) exists; this extends it to the writers and the versioning service.

## Findings
- `versioning_service.bucket_name = settings.S3_BUCKET` — a third precedence (`S3_BUCKET` first), fixed at import; the only consumer of `settings.S3_BUCKET`.
- `S3Service.upload_file_obj / delete_file / get_file_size / generate_presigned_url` take a raw key against `self.bucket_name` (fixed at construction); `download_file_bytes` already validates the key and resolves `allowed_bucket()` per call.
- Every current writer builds a namespaced key (`datasets/`, `transformed/`, `models/`, `batch-jobs/`, `exports/`); erasure may still delete pre-#581 legacy-root keys.

## Design
1. `app/config.py`: `resolve_configured_bucket()` = the readers' expression (`AWS_S3_BUCKET` first, then the historical names); `utils.s3._allowed_bucket` delegates to it; the `Settings.S3_BUCKET` field is removed (env `S3_BUCKET` stays honoured through the resolver).
2. `VersioningService.bucket_name` becomes a property → `configured_bucket() or <its legacy default>`; the writes/reads inside it need no change.
3. The four `S3Service` write methods validate their key (`validate_object_key(..., allow_legacy_root=True)` — erasure still deletes pre-#581 root keys) and use `allowed_bucket()` per call; `self.bucket_name` stays for URL building / mock detection.
4. `validate_object_key` docstring: hygiene, not per-tenant authorization.
5. Tests: registry gains an agreement test (three env names, three values → every resolver, `S3Service`, `VersioningService` agree); write-method tests: traversal/foreign-namespace key refused before boto3 is called, legacy-root admitted for delete, live bucket honoured after an env change.

## Steps
- [ ] RED tests
- [ ] config resolver + versioning property + S3Service writes + docstring
- [ ] gate → PR → demo → CI → merge
