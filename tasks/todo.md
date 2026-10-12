# #722 — `download_file_from_s3` reuses the shared S3 client (P2.52)

Self-authored plan. One function, one line.

## Decisions made here
- `get_s3_client() or create_s3_client()`. The shared client is built once and rebuilt
  when the credentials, endpoint or region change (#519). It is `None` only when the
  credentials are missing; then the downloader builds one as it always did, so the
  failure a caller sees in that case is the one boto3 raised before.
- No change to the size check, the allowlist or the circuit breaker around the function.

## Steps
- [x] Tests: three downloads build one client; a rotated secret builds a second; with no
      credentials the per-call build is kept.
- [x] The one-line change; CLAUDE.md's "known residual" sentence.
- [ ] Gate, cross-family review, PR, demo against LocalStack, CI, merge.
