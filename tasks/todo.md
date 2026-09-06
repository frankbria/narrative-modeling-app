# Issue #449 — [P0.6] Cached column stats returned cross-tenant

Branch: `fix/449-column-stats-cache-idor`

## Problem
`GET /api/v1/column-stats/dataset/{dataset_id}` reads the `ColumnStats` cache first and
only enters the ownership check inside `if not column_stats:`. On a cache hit it returns
another tenant's distributions, null counts, cardinality and sample values with no
authorization at all.

## What the probe established (not assumed)
1. `ColumnStats.dataset_id` is a `Link[UserData]`, stored as a **DBRef**; the route's
   `== PydanticObjectId(...)` query matched **0 rows**. So the cache never hits via the
   normal write path — the vulnerability is **latent today** and goes live with #543.
2. A raw bare-ObjectId row **does** match and parses cleanly. That is how AC3's
   cache-hit test is seeded ("directly", per the issue), and it is the shape #543 creates.
3. Unreported: the ownership check sits inside `try/except Exception` with no
   `except HTTPException: raise`, so today's 403 is swallowed and surfaces as **500**.

## Plan
1. **RED** — first route tests for this file (AC4):
   - cache hit, foreign dataset → 404 (currently returns the victim's stats)
   - cache miss, foreign dataset → 404 (currently 500, via the swallowed 403)
   - owner, cache hit → 200 with their own stats
   - malformed `dataset_id` → 404, not a 500 from `PydanticObjectId(...)`
   - `POST .../recalculate` on a foreign dataset → 404
2. **GREEN**
   - resolve the dataset and check ownership **unconditionally, before** the cache read,
     and **outside** the `try` so it cannot be swallowed into a 500 (AC1)
   - add `user_id` to `ColumnStats` (optional, indexed), set it on write, and filter the
     cache read by it — so a foreign row cannot be returned even if AC1 is later
     refactored away (AC2). Optional/defaulted so pre-existing rows simply miss the
     cache and get recomputed, per the repo's degrade-gracefully convention.
   - 403 → 404 on ownership mismatch in **both** handlers: 403 confirms the dataset
     exists, and AC3 fixes 404 as the expected answer for this file.
3. Docs: add both routes to `SECURITY_OWNERSHIP_CHECKS.md`.

## Deliberately NOT fixed here
The DBRef-vs-bare-ObjectId mismatch is #543 (P2.20). The issue says to land this first;
fixing the cache so it hits, before the authorization is fixed, would turn a latent hole
into a live one.

## Acceptance criteria
- [ ] AC1 ownership check runs unconditionally, before the cache lookup
- [ ] AC2 the cache read itself is scoped
- [ ] AC3 route test seeds `ColumnStats` for tenant B so the cache hits; A gets 404
- [ ] AC4 first route tests for `column_stats.py`
