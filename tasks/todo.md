# #615 — Retire the pre-#581 legacy root-key allowance (P1.39)

Ops half was done on staging on 2026-10-01 and posted on the issue. Root objects: 156. Dry run found 0 moves.
Staging's DB has never held a dataset. The owners sit in two legacy DBs that no deployed service reads.
Production does not exist (#476), and it will start after #581, so no deployed environment reads a root key.

## Plan (self-authored, no architectural fork)
1. RED: rewrite the legacy-allowance tests so they assert refusal:
   - `test_utils/test_s3.py`: validate_object_key, resolve_validated_object, get_file_from_s3
   - `test_services/test_s3_write_contract.py`: delete_file, get_file_size, download_file_bytes
   - drop the legacy case from `test_feature_store_service.py`'s location-shape parametrize
2. GREEN: delete `_LEGACY_ROOT_KEY` and the `allow_legacy_root` parameter. Drop the kwarg at all 5 call sites
   (utils/s3.py get_file_from_s3, s3_service download_file_bytes/get_file_size/delete_file, feature_store_service).
3. Docs: update CLAUDE.md where it mentions the allowance and #615.

## Acceptance (from the issue's DoD)
- [x] Dry-run output and root-object count posted (apply was a no-op: 0 attributable)
- [x] Orphan count posted, with a recommendation. The delete decision belongs to the owner, and nothing was deleted.
- [x] Readers refuse a bare root key, with a test (plus an erasure residual test)
- [x] `_LEGACY_ROOT_KEY` deleted
