# Issue #452 — [P0.9] Any tenant can purge another tenant's cache

## Findings
- `app/api/routes/cache.py` exposes 6 routes to any authenticated user.
  - `DELETE /data/{data_id}`: no owner check; `data_id` reaches `KEYS` globs
    (`data_stats:{id}`, `eda:{id}`, `predictions:{id}:*`) → `data_id="*"` flushes them all.
  - `DELETE /key/{cache_key}` / `GET /key/{cache_key}/exists`: arbitrary key delete + probe,
    including `ratelimit:*` → limiter reset and cross-tenant key-name disclosure.
  - `GET /info`: Redis server internals to any user.
  - `POST /warmup/user/{user_id}`: returns success, does nothing (AC6).
  - `DELETE /user/{user_id}`: self-checked, but `invalidate_user_cache` globs `*:{user_id}*`,
    which matches `ratelimit:<identity containing user_id>` → resets own limiter (AC3).
- **Zero consumers.** No frontend/e2e/service call any `/api/v1/cache/*` route; only
  `apps/backend/REDIS_CACHE.md` documents them.
- Only user-namespaced cache key in the codebase is `user_progress:{user_id}`
  (`onboarding_service`). Every other cached key is dataset/model/hash scoped.

## Plan
1. Reduce the router to one tenant-scoped route: `DELETE /api/v1/cache/me`
   — purges the caller's own entries, identity from the token, no path segment. (AC1/AC4)
2. Delete `/info`, `/data/{data_id}`, `/key/{cache_key}`, `/key/{cache_key}/exists`,
   `/warmup/user/{user_id}`. (AC4, AC6)
3. `RedisCacheService.invalidate_user_cache` → exact-key deletes of the user's own
   namespaced keys; no glob. Drop `invalidate_data_cache` (its only caller is the
   deleted route, and it is the remaining glob builder). (AC2)
4. Rate-limit buckets stay under `ratelimit:` — unreachable now that no route accepts a
   key or a pattern. Test proves it. (AC3)
5. Rewrite `tests/test_api/test_cache.py` for the guarded surface: removed routes 404/405,
   `/me` purges only the caller, tenant B's keys and `ratelimit:*` survive. (AC5)
6. Update `apps/backend/REDIS_CACHE.md`.
