# Issue #565 — [P3.10] [security] ABTest.experiment_id is not unique, so track-prediction's authorization rests on a convention

Plan source: self-authored. Approved autonomously — AC3 offers index-or-scope; do both (the issue says both is better). No fork.

## Findings
- `ABTest.experiment_id: Annotated[str, Indexed()]` — indexed, not unique; ids are `exp_<ObjectId>` from a helper, so duplicates are unreachable through the API but not forbidden by the database.
- Route `/track-prediction` authorizes on `(experiment_id, user_id)` then `ABTestingService.track_prediction` re-fetches by `experiment_id` alone (#559's shape).

## Design
1. `Indexed(unique=True)` on `experiment_id` (Beanie builds it at `init_beanie`).
2. `ABTestingService.track_prediction(..., user_id)` filters the write-side lookup on the owner too; the route passes `current_user_id`.
3. AC2: `scripts/check_ab_test_duplicates.py` — one aggregation listing duplicate `experiment_id`s; run it against a collection before deploying (index build fails at startup otherwise). Local test DB: reported in the PR.
4. Tests: second insert with the same `experiment_id` → `DuplicateKeyError`; service refuses another tenant's experiment even when handed its id.

## Steps
- [ ] RED tests
- [ ] model + service + route + script
- [ ] gate → PR → demo → CI → merge
