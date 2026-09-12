# Issue #531 — [P3.2] [slop] Consolidate the two divergent get_file_from_s3 implementations (+ #567 two allowlists)

Plan source: self-authored. Judgment call, not an architectural fork: keep every existing read working during the transition to prefixed keys (#615) via one explicit, tested allowance instead of breaking production reads.

## Design
- **One validated core in `app/utils/s3.py`**: `allowed_bucket()` (the single resolver; fail closed), `validate_object_key(key, *, allow_legacy_root=False)` (URL-decode; refuse `..` and a leading `/`; require `{datasets|transformed}/{user}/{file}`; the transitional legacy root shape `^(masked_)?{uuid}\.{ext}$` — exactly what #615 reconciles — only when asked), `resolve_validated_object(s3_url, *, allow_legacy_root=False) -> (bucket, key)` (parse → allowlist → key validation), and one `MAX_DOWNLOAD_BYTES`.
- `parse_s3_url` learns the regional virtual-host shape (`bucket.s3.<region>.amazonaws.com`) so the utils reader's host-label fallback can go.
- **Exactly one `get_file_from_s3`** (utils, BytesIO) = core (legacy root allowed, because viz/preview read `UserData.s3_url`, which still points at root objects in production) + size check + `download_fileobj`. `download_file_from_s3` (service, temp file) = the same core, strict, + size check + `download_file`. The async `s3_service.get_file_from_s3(file_key)` alias is deleted; its two callers use `s3_service.download_file_bytes`, which validates the key through the core.
- `column_stats.py`'s two sites stop parsing/fetching themselves and call `get_file_from_s3` (#567 AC1).
- **Registry test (#567 AC3)**: the only raw boto3 download calls in `app/` live in the two core modules; every public entry point refuses a foreign bucket, traversal, and an out-of-namespace key; exactly one `def get_file_from_s3` and one `def download_file_from_s3` exist (#531 AC4).

## Steps
1. [ ] Tests first: core unit tests (allowlist, key validation incl. legacy allowance, regional URL), entry-point foreign-bucket/traversal tests, registry test, updated utils tests (root non-uuid key now refused — contract change).
2. [ ] Core in utils/s3.py; get_file_from_s3 on it; parse_s3_url regional.
3. [ ] s3_service: download_file_from_s3 + download_file_bytes on the core; delete the async alias; fix 2 callers.
4. [ ] column_stats.py onto get_file_from_s3.
5. [ ] Docs: CLAUDE.md gotcha; require_allowed_bucket docstring.

## Acceptance criteria
- [ ] #531 AC1 one implementation with bucket allowlist + tenant-prefix validation
- [ ] #531 AC2 every call site uses it; duplicate deleted
- [ ] #531 AC3 the temp-file variant wraps the same core
- [ ] #531 AC4 grep test: no second definition
- [ ] #567 AC1–4 one allowlist, strictest behaviour, call-site registry test, resolve_s3_bucket the single resolver
