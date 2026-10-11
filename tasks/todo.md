# #715 — column_stats concurrent cache-miss: loser can serve a partial winner write (P1.60)

Self-authored plan (the issue lists options, no plan and no explicit acceptance criteria).

## Decision made here
- **The loser serves what it computed, not what it re-reads** (the issue's option 2).
  `calculate_and_store_column_stats` already holds the complete in-memory list when its
  `insert_many` collides on `dataset_column_unique`. It catches a duplicate-key-only
  `BulkWriteError` and returns that list, so no reader ever depends on how far the
  winner's non-atomic write has got. No retry loop, no sleep, no transaction (the local
  mongod is standalone). A bulk error that is anything other than a duplicate key still
  raises.
- Both routes' `except (BulkWriteError, DuplicateKeyError)` branches go away: the helper is
  the one place the collision is handled. `recalculate` keeps reporting success.

## Acceptance criteria (derived from the issue)
- [ ] AC1: a GET that loses the recompute race returns every column of the dataset, even
      when the winner has written only some of its rows at the moment of the collision.
- [ ] AC2: a test pins that window with a real duplicate-key error from the real index
      (the issue's repro sketch), and fails on the old code.
- [ ] AC3: the loser still answers 200, not 500, and `recalculate` still reports success on
      a collision.
- [ ] AC4: a bulk write error that is not a duplicate key is not swallowed.

## Steps
1. RED: in `tests/test_api/test_column_stats.py`, replace the full-set race test with one
   that seeds one of two winner rows just before the real `insert_many`; add the
   recalculate collision test and the non-duplicate error test.
2. GREEN: handle the collision in `app/utils/column_stats.py`; delete the two route
   branches and the now-unused import in `app/api/routes/column_stats.py`.
3. Update the #543 paragraph in `CLAUDE.md`.

## Out of scope, to be filed
- A plain reader (no recompute) that arrives while a winner is mid-`insert_many` sees a
  non-empty partial set and serves it as a cache hit. Nothing checks a cached set is
  complete. Different path, same root; needs its own decision on what "complete" is
  measured against.
