# Issue #279 — [P2.2] APIKey.key_hash unindexed; redundant per-request writes + lost-update counter

**Plan source:** self-authored (issue had no plan comment). No architectural fork → autonomous.

## Problem
`verify_api_key` (production.py) and `RateLimitMiddleware` each `find_one({key_hash})` per
production request, but `key_hash` has **no index** → two collection scans on the hottest
auth path. `verify_api_key` also does read-modify-write `total_requests += 1; save()`
(lost-update race + full-document save can revert a concurrent revoke) plus a per-request
`last_used_at` write. `model_storage.load_model` similarly full-document-`save()`s
`last_used_at` (cache-miss only post-#265, but same clobber risk).

## Acceptance criteria
- [ ] AC1: Add a (unique) `key_hash` index.
- [ ] AC2: Use atomic `$inc` for `total_requests` / `$set` for `last_used_at`.
- [ ] AC3: Throttle / fire-and-forget `last_used_at` off the request path.

## Steps
1. **`app/models/api_key.py`** — add unique `IndexModel([("key_hash", ASCENDING)], unique=True)`
   to `Settings.indexes` (pattern from `version.py` #276). Serves both `find_one({key_hash})`
   callers (verify_api_key + rate-limit middleware). *(AC1)*
2. **`app/api/routes/production.py`** — replace the `save()` in `verify_api_key` with a
   fire-and-forget atomic update: `Inc({total_requests: 1})` + `Set({last_used_at: now-UTC})`,
   scheduled via `asyncio.create_task` (tracked in a module set + done-callback discard,
   like batch_prediction). Add `flush_usage_tracking()` for test/shutdown determinism.
   Timestamp is timezone-aware (`datetime.now(UTC)`). *(AC2, AC3)*
3. **`app/services/model_storage.py`** — cache-miss `last_used_at`: full-document `save()`
   → atomic single-field `ml_model.set({MLModel.last_used_at: now})` (removes clobber risk;
   already off the hot path). *(AC2)*

## Tests
- `tests/test_models/test_api_key.py` — assert `key_hash` is a declared **unique** index.
- `tests/test_api/test_production.py` (integration, real Mongo):
  - usage recorded atomically: N verifications → `total_requests == N`, `last_used_at` set + tz-aware.
  - non-clobber: concurrent atomic revoke (`is_active=False`) survives the usage write; count still bumped.
  - `verify_api_key` schedules off the request path (task created, response not blocked on it).
- `tests/test_services/test_model_storage_cache.py` — update `_mock_ml_model` (`.set` AsyncMock
  instead of `.save`); existing cache-dedup tests still green.

## Assumptions / notes
- Unique index safe: `key_hash` is SHA-256 of a random key → collision-free by construction
  (mirrors #276's documented beta limitation; fails at startup only on pre-existing dup data).
- Fire-and-forget only for the per-request APIKey write; MLModel write stays awaited (rare, cache-miss).
